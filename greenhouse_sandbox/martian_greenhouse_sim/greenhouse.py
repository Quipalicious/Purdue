"""
Thermodynamic and atmospheric state model for the cylindrical MLGH prototype.

Greenhouse geometry (hard requirements)
---------------------------------------
  Cylinder: 5.5 m long * 2.1 m diameter
  Total volume : 21 m^3   Surface area SA : 43.2 m^2
  Active mixing volume V_T : 14 m^3  (~= 65 % of total)
  Internal pressure : 100 kPa

Thermal dynamics (required equations)
--------------------------------------
Heat loss:
    HL = SA * U * (T_in - T_out)              [Watts]

Temperature update per time step dt:
    dT_in/dt = (-HL + Q_heater + S_i) / C_eff
    T_in <- T_eq + (T_in - T_eq) * exp(-dt / tau)

where:
    C_eff    = rho * V_T * Cp * THERMAL_MASS_MULTIPLIER  (J/K)
    U        = thermal transmittance of wall glazing     (W/(m^2*K))
    Q_heater = total heat input from actuators           (W)
    S_i      = solar radiant energy captured             (W)
    rho      = air density, 1.2 kg/m^3
    Cp       = specific heat of air, 1006 J/(kg*K)

Simplified internal atmosphere dynamics
-----------------------------------------
CO2   : balance of injection, plant uptake (PAR and CO2 dependent), and
        background soil / plant respiration in a sealed atmosphere.
At a fixed 100 kPa internal pressure, 900 ppm = 90 Pa CO2 partial pressure,
so ppm is a valid control variable here.
Constant total pressure is an abstraction; make-up gas and pressure control
are outside this model.
RH    : derived from water-vapour inventory and temperature; transpiration
        and irrigation evaporation supply vapour, while cold-surface
        condensation and slow moisture permeation remove it.
Soil  : finite substrate water inventory supplied by irrigation; loses water
        through evaporation, transpiration and overflow drainage.
PAR   : sum of solar component and supplemental LED contribution.

Water fluxes conserve mass but do not exchange latent heat with the air.
A latent-cooling term was tested and left out to keep the assignment
calibration.  Cold-surface condensate drains away.  The model has no
condensate-recycling loop.
"""

import copy
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .constants import (
    A_PROJ_M2,
    ABSORPTION_EFFICIENCY,
    ACTIVE_VOLUME_M3,
    CO2_BOUNDS_MAX_PPM,
    CO2_COMPENSATION_PPM,
    CO2_HALF_AVAILABILITY_PPM,
    CONDENSATION_SURFACE_FRACTION,
    CONDENSATION_TAU_S,
    CP_AIR_J_KG_K,
    DEFAULT_DT_S,
    HEATER_MAX_W,
    I_PEAK_MARS,
    IRRIGATION_EVAPORATION_FRACTION,
    PAR_SOLAR_MAX_UMOL_M2_S,
    PHOTOSYNTHESIS_HALF_PAR,
    PHOTOSYNTHESIS_MAX_PPM_S,
    REFERENCE_TRANSMITTANCE,
    RHO_AIR_KG_M3,
    SUBSTRATE_EVAPORATION_VWC_S,
    SUBSTRATE_VOLUME_M3,
    SURFACE_AREA_M2,
    THERMAL_MASS_MULTIPLIER,
    TRANSPIRATION_MAX_VWC_S,
    TRANSPIRATION_WET_VWC,
    U_VALUE_W_M2_K,
    VAPOUR_LOSS_TAU_S,
    WATER_DENSITY_KG_M3,
    WATER_VAPOUR_GAS_CONSTANT,
)

if TYPE_CHECKING:
    from .environment import MarsEnvironment


def _saturation_vapour_pa(temp_c: float) -> float:
    """Return Tetens saturation pressure over water (Pa).

    FAO-56 Eq. 11: https://www.fao.org/4/x0490e/x0490e07.htm .
    Temperature is bounded to [-80, 60] for failed-crop numerical states.
    Below freezing, this is a supercooled-water approximation.  It does not
    model ice.
    """
    temp = max(-80.0, min(60.0, temp_c))
    return 610.8 * math.exp(17.27 * temp / (temp + 237.3))


def _vapour_capacity_kg(temp_c: float, surface_c: float) -> float:
    """Mass giving saturation at surface_c in air at temp_c, by pV = mRT."""
    kelvin = max(193.15, min(333.15, temp_c + 273.15))
    return _saturation_vapour_pa(surface_c) * ACTIVE_VOLUME_M3 / (
        WATER_VAPOUR_GAS_CONSTANT * kelvin
    )


# ---------------------------------------------------------------------------
# Shared state types
# ---------------------------------------------------------------------------


@dataclass
class ActuatorState:
    """
    Current actuator commands expressed both as 0 to 1 fractions and as the
    corresponding physical output quantities consumed by the physics model.

    Populated by :class:`VirtualActuators`; consumed by :meth:`Greenhouse.update_state`.
    """

    # Normalised fractions [0, 1]
    heater_frac: float = 0.0
    led_frac: float = 0.0
    co2_valve_frac: float = 0.0
    pump_frac: float = 0.0

    # Derived physical outputs (filled by VirtualActuators)
    heater_watts: float = 0.0  #: Heater output (W)
    led_par_umol: float = 0.0  #: Supplemental LED PAR (umol/m^2/s)
    led_heat_watts: float = 0.0  #: LED waste heat (W)
    co2_ppm_s: float = 0.0  #: CO2 injection rate (ppm/s)
    vwc_s: float = 0.0  #: Irrigation rate (VWC/s)


@dataclass
class GreenhouseState:
    """
    Snapshot of the greenhouse internal environment at a single time step.

    All fields are SI-compatible.  Each field comment gives its unit.
    """

    time_s: float = 0.0  #: Simulation time (s)
    temp_c: float = 22.0  #: Internal air temperature (deg C)
    rh_pct: float = 50.0  #: Relative humidity (%)
    co2_ppm: float = 900.0  #: CO2 concentration (ppm)
    soil_vwc: float = 0.40  #: Soil volumetric water content [0 to 1]
    par_umol_m2_s: float = 0.0  #: PAR at crop level (umol/m^2/s)

    # Ancillary / diagnostic fields
    solar_irradiance_w_m2: float = 0.0  #: Incident solar irradiance (W/m^2)
    t_out_c: float = -37.5  #: External Martian temperature (deg C)
    heat_loss_w: float = 0.0  #: Conductive heat loss HL (W)
    solar_gain_w: float = 0.0  #: Solar energy captured S_i (W)

    # Water inventory and flux diagnostics; fluxes are kg during the last step.
    water_vapour_kg: float = 0.0  #: Vapour mass in the mixing volume (kg)
    evaporated_water_kg: float = 0.0  #: Evaporation plus transpiration (kg/step)
    condensed_water_kg: float = 0.0  #: Condensate removed to a drain (kg/step)
    ambient_water_loss_kg: float = 0.0  #: Moisture permeation loss (kg/step)
    drained_water_kg: float = 0.0  #: Substrate overflow to a drain (kg/step)


# ---------------------------------------------------------------------------
# Greenhouse physics model
# ---------------------------------------------------------------------------


class Greenhouse:
    """
    Thermodynamic and atmospheric model of the cylindrical MLGH prototype.

    The class tracks the internal state of the greenhouse and advances it
    one time step at a time via :meth:`update_state`.

    Parameters
    ----------
    initial_temp_c : float
        Initial internal air temperature (deg C).
    initial_co2_ppm : float
        Initial CO2 concentration (ppm).
    initial_rh_pct : float
        Initial relative humidity (%).
    initial_soil_vwc : float
        Initial soil volumetric water content [0 to 1].
    u_value : float
        Thermal transmittance of the wall (W/(m^2*K)).  Lower values give
        better insulation. Default 0.6 is the twin-wall polycarbonate glazing.
        Zero represents the perfectly insulated limit.
    transmittance : float
        Fraction of outside light the glazing passes to the crop [0 to 1].
        Scales both solar heat gain and solar PAR relative to the default
        twin-wall glazing (REFERENCE_TRANSMITTANCE).

    Raises
    ------
    ValueError
        If any constructor argument is non-finite, u_value is negative, or
        transmittance is outside [0, 1].

    Notes
    -----
    Hosts may set living_biomass_factor from PlantCohort.health before each
    update (zero for a dead cohort). If the host does not set it, the model
    uses a constant full living crop.  This class does not create a plant
    cohort.
    """

    #: Living crop fraction [0, 1]; host may set from PlantCohort.health.
    #: Defaults to a full crop when the host does not supply a cohort signal.
    living_biomass_factor: float = 1.0

    def __init__(
        self,
        initial_temp_c: float = 22.0,
        initial_co2_ppm: float = 900.0,
        initial_rh_pct: float = 50.0,
        initial_soil_vwc: float = 0.40,
        u_value: float = U_VALUE_W_M2_K,
        transmittance: float = REFERENCE_TRANSMITTANCE,
    ) -> None:
        for name, value in {
            "initial_temp_c": initial_temp_c,
            "initial_co2_ppm": initial_co2_ppm,
            "initial_rh_pct": initial_rh_pct,
            "initial_soil_vwc": initial_soil_vwc,
            "u_value": u_value,
            "transmittance": transmittance,
        }.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if u_value < 0.0:
            raise ValueError("u_value must be >= 0")
        if not 0.0 <= transmittance <= 1.0:
            raise ValueError("transmittance must be in [0, 1]")
        self._u = u_value
        self._transmittance_ratio = transmittance / REFERENCE_TRANSMITTANCE
        self.state = GreenhouseState(
            temp_c=initial_temp_c,
            rh_pct=initial_rh_pct,
            co2_ppm=initial_co2_ppm,
            soil_vwc=initial_soil_vwc,
            water_vapour_kg=max(0.0, min(100.0, initial_rh_pct)) / 100.0
            * _vapour_capacity_kg(initial_temp_c, initial_temp_c),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update_state(
        self,
        env: "MarsEnvironment",
        actuators: ActuatorState,
        dt_seconds: float = DEFAULT_DT_S,
    ) -> GreenhouseState:
        """
        Advance the greenhouse state by one time step *dt_seconds*.

        Implements the required heat-loss and temperature ODE equations:

            HL = SA * U * (T_in - T_out)
            dT_in/dt = (-HL + Q_heater + S_i) / C_eff

        For inputs held constant over the step, write K = SA * U and
        C = rho * V_T * Cp * THERMAL_MASS_MULTIPLIER. The required air-only
        equation is recovered at multiplier 1.  Larger multipliers add the
        effective heat capacity of soil, water, and structure.
        Then C * dT/dt = -K*T + K*T_out + Q_heater + S_i.
        Setting dT/dt = 0 gives T_eq = T_out + (Q_heater + S_i) / K;
        dividing by C gives dT/dt = (T_eq - T) / tau, where tau = C / K.
        The exact solution is T_new = T + (T_eq - T) * (1 - exp(-dt/tau)).
        This preserves the required ODE without forward-Euler overshoot.
        For U = 0, use the exact constant-heating limit Q * dt / C.

        Also updates CO2, relative humidity, soil moisture, and PAR.

        Parameters
        ----------
        env : MarsEnvironment
            Current Mars external conditions.
        actuators : ActuatorState
            Current actuator command state.
        dt_seconds : float
            Time step duration (s).

        Raises
        ------
        ValueError
            If dt_seconds is non-finite or not strictly positive.

        Returns
        -------
        GreenhouseState
            The updated internal state (also stored in ``self.state``).
        """
        if not math.isfinite(dt_seconds) or dt_seconds <= 0.0:
            raise ValueError("dt_seconds must be finite and > 0")
        t_out = env.get_temperature_c()
        t_in = self.state.temp_c
        irradiance = env.get_solar_irradiance_w_per_m2()

        # --- Thermal dynamics ---
        # Heat loss through the structure walls (W), positive when T_in > T_out
        HL = SURFACE_AREA_M2 * self._u * (t_in - t_out)

        # Solar energy captured by the greenhouse glazing (W)
        S_i = irradiance * A_PROJ_M2 * ABSORPTION_EFFICIENCY * self._transmittance_ratio

        # Total heat input from electrical actuators (W)
        Q_heater = actuators.heater_watts + actuators.led_heat_watts

        # Exact solution of the required temperature ODE for this step.
        capacity = (
            RHO_AIR_KG_M3 * ACTIVE_VOLUME_M3 * CP_AIR_J_KG_K
            * THERMAL_MASS_MULTIPLIER
        )
        conductance = SURFACE_AREA_M2 * self._u
        heat_input = Q_heater + S_i
        if conductance == 0.0:
            new_temp = t_in + heat_input * dt_seconds / capacity
        else:
            t_eq = t_out + heat_input / conductance
            tau = capacity / conductance
            new_temp = t_in + (t_eq - t_in) * (-math.expm1(-dt_seconds / tau))

        # --- PAR at crop level ---
        par_solar = (
            (irradiance / I_PEAK_MARS) * PAR_SOLAR_MAX_UMOL_M2_S
            if I_PEAK_MARS > 0.0 else 0.0
        )
        par_solar = max(0.0, par_solar) * self._transmittance_ratio
        new_par = par_solar + actuators.led_par_umol

        # --- CO2 dynamics ---
        # Effective crop compensation threshold for this teaching model.
        # CO2 scarcity reduces uptake smoothly; 900 ppm retains nominal uptake.
        available_co2 = max(0.0, self.state.co2_ppm - CO2_COMPENSATION_PPM)
        nominal_available = 900.0 - CO2_COMPENSATION_PPM
        normalization = (
            nominal_available + CO2_HALF_AVAILABILITY_PPM
        ) / nominal_available
        co2_factor = normalization * available_co2 / (
            available_co2 + CO2_HALF_AVAILABILITY_PPM
        )
        # Diminishing returns: twice the light gives less than twice the uptake.
        light_factor = new_par / (new_par + PHOTOSYNTHESIS_HALF_PAR)
        co2_uptake = min(
            available_co2,
            PHOTOSYNTHESIS_MAX_PPM_S * light_factor * co2_factor
            * self.living_biomass_factor * dt_seconds,
        )  # ppm; uptake cannot exceed the available inventory

        # Background soil / plant respiration (slight CO2 source at night too)
        co2_resp = 0.0015 * dt_seconds  # ppm

        # Actuator injection
        co2_in = actuators.co2_ppm_s * dt_seconds  # ppm

        new_co2 = self.state.co2_ppm + co2_in - co2_uptake + co2_resp
        new_co2 = max(200.0, min(CO2_BOUNDS_MAX_PPM, new_co2))

        # --- Water balance ---
        # Convert VWC to kg so every source and sink conserves actual water.
        water_capacity = SUBSTRATE_VOLUME_M3 * WATER_DENSITY_KG_M3
        irrigation = actuators.vwc_s * dt_seconds * water_capacity
        deficit = max(0.0, 1.0 - self.state.rh_pct / 100.0)
        # Frozen substrate supplies no liquid evaporation in this simple model.
        liquid_factor = max(0.0, min(1.0, t_in / 5.0))
        irrigation_evap = (
            irrigation * IRRIGATION_EVAPORATION_FRACTION * deficit * liquid_factor
        )
        soil_water = max(0.0, self.state.soil_vwc * water_capacity)
        soil_water += irrigation - irrigation_evap
        wetness = min(1.0, soil_water / (water_capacity * TRANSPIRATION_WET_VWC))
        et_rate = (
            SUBSTRATE_EVAPORATION_VWC_S
            + TRANSPIRATION_MAX_VWC_S * light_factor * self.living_biomass_factor
        ) * wetness * deficit * liquid_factor
        transpired = min(soil_water, et_rate * water_capacity * dt_seconds)
        evaporated = irrigation_evap + transpired
        soil_water -= transpired
        drained = max(0.0, soil_water - water_capacity)
        new_vwc = min(1.0, soil_water / water_capacity)

        vapour = self.state.water_vapour_kg + evaporated
        ambient_loss = vapour * (-math.expm1(-dt_seconds / VAPOUR_LOSS_TAU_S))
        vapour -= ambient_loss
        surface_c = new_temp - CONDENSATION_SURFACE_FRACTION * max(
            0.0, new_temp - t_out
        )
        surface_capacity = _vapour_capacity_kg(new_temp, surface_c)
        condensed = max(0.0, vapour - surface_capacity) * (
            -math.expm1(-dt_seconds / CONDENSATION_TAU_S)
        )
        vapour -= condensed
        air_capacity = _vapour_capacity_kg(new_temp, new_temp)
        # Any remaining supersaturation condenses, conserving the inventory.
        excess = max(0.0, vapour - air_capacity)
        condensed += excess
        vapour -= excess
        new_rh = 100.0 * vapour / air_capacity

        # --- Commit updated state ---
        self.state.time_s = env.get_time_s()
        self.state.temp_c = new_temp
        self.state.rh_pct = new_rh
        self.state.water_vapour_kg = vapour
        self.state.evaporated_water_kg = evaporated
        self.state.condensed_water_kg = condensed
        self.state.ambient_water_loss_kg = ambient_loss
        self.state.drained_water_kg = drained
        self.state.co2_ppm = new_co2
        self.state.soil_vwc = new_vwc
        self.state.par_umol_m2_s = new_par
        self.state.solar_irradiance_w_m2 = irradiance
        self.state.t_out_c = t_out
        self.state.heat_loss_w = HL
        self.state.solar_gain_w = S_i

        return self.state

    def get_state(self) -> GreenhouseState:
        """Return a shallow copy of the current state snapshot."""
        return copy.copy(self.state)


# Diagnostic alias kept for backward compatibility.  The humidity model no
# longer uses heater drying.
HEATER_MAX_REF_W: float = HEATER_MAX_W
