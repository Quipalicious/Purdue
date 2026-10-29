"""
Physical and simulation constants for the Martian Greenhouse Simulation.

Each value has a comment that gives its source or rationale. Instructors may
change the tunable parameters (marked [TUNABLE]) to change the simulation
behaviour without editing the physics model code.
"""

import math

# ===========================================================================
# Martian Environment
# ===========================================================================

#: Length of a Martian solar day (sol) in seconds.
SOL_SECONDS: float = 88_775.0

#: Mars receives approximately 43 % of the solar energy that Earth does.
MARS_SOLAR_FACTOR: float = 0.43

#: Earth clear-sky surface irradiance at noon, rounded for pedagogy (W/m^2).
#: Strictly, the 43 % factor applies to the solar constant above Earth's
#: atmosphere (1361 W/m^2), which gives about 585 W/m^2 above Mars's
#: atmosphere.  Using Earth's surface value is a shortcut: the product,
#: 430 W/m^2, stands in for clear-sky noon at the Martian surface.
SOLAR_CONSTANT_W_M2: float = 1000.0

#: Peak clear-sky solar irradiance at the Martian surface (W/m^2).
I_PEAK_MARS: float = MARS_SOLAR_FACTOR * SOLAR_CONSTANT_W_M2  # ~= 430 W/m^2

# --- Diurnal temperature model (deg C) ---
#: Mean of the diurnal temperature cycle.  = (high + low) / 2
T_MEAN_C: float = (-5.0 + -70.0) / 2.0  # -37.5 deg C

#: Amplitude of the diurnal temperature cycle.  = (high - low) / 2
T_AMPLITUDE_C: float = (-5.0 - -70.0) / 2.0  # 32.5 deg C

#: Phase offset (rad) so that the temperature maximum aligns with local noon
#: (t = SOL_SECONDS / 2).
#:   sin(2pi*(sol/2)/sol - pi/2) = sin(pi - pi/2) = sin(pi/2) = 1
T_PHASE: float = math.pi / 2.0

# --- Dust storm / opacity model ---
#: Atmospheric opacity (Tau) on a clear Martian day.
TAU_CLEAR: float = 0.5

#: Minimum storm-level opacity (Tau).
TAU_STORM_MIN: float = 5.0

#: Maximum storm-level opacity (Tau).
TAU_STORM_MAX: float = 8.5

#: Maximum fractional reduction in solar radiation during a global dust storm.
#: At TAU_STORM_MAX the incident solar drops to (1 - 0.97) = 3 % of clear-sky.
TAU_REDUCTION_MAX: float = 0.97

# ===========================================================================
# Greenhouse Geometry & Structural Properties
# ===========================================================================

#: Cylinder length (m).
CYLINDER_LENGTH_M: float = 5.5

#: Cylinder outer diameter (m).
CYLINDER_DIAMETER_M: float = 2.1

#: Cylinder outer radius (m).
CYLINDER_RADIUS_M: float = CYLINDER_DIAMETER_M / 2.0  # 1.05 m

#: Total geometric volume of the cylinder (m^3).  Descriptive only.
TOTAL_VOLUME_M3: float = (
    math.pi * CYLINDER_RADIUS_M**2 * CYLINDER_LENGTH_M
)  # ~= 19.05 m^3

#: Total structural surface area of the greenhouse (m^2).
SURFACE_AREA_M2: float = 43.2

#: Active mixing air volume V_T, about 73 % of the total volume (m^3).
ACTIVE_VOLUME_M3: float = 14.0

#: Maintained internal pressure against the near-vacuum of Mars (kPa).
#: Descriptive only: the physics model does not use it.
INTERNAL_PRESSURE_KPA: float = 100.0

# ===========================================================================
# Thermodynamic Properties
# ===========================================================================

#: Thermal transmittance of the default (twin-wall polycarbonate) glazing
#: (W/(m^2*K)).  Teams select their own glazing from the hardware menu in
#: ``hardware.py``; this is the value used when no selection is made.
U_VALUE_W_M2_K: float = 0.6

#: Internal air density (kg/m^3).
RHO_AIR_KG_M3: float = 1.2

#: Specific heat capacity of air (J/(kg*K)).
CP_AIR_J_KG_K: float = 1006.0

#: Effective heat capacity relative to the mixing air alone. [TUNABLE]
#: Covers thermally coupled soil, water, plants and structure over a step.
#: This is a lumped teaching parameter. It does not represent the full mass of
#: the habitat. The value was set by a calibration sweep.
THERMAL_MASS_MULTIPLIER: float = 1.5

#: Effective solar-capture area (m^2).  [TUNABLE] Numerically equal to the
#: circular end cap.  It is not a geometric projection: the cylinder's
#: horizontal silhouette (length x diameter) is 11.55 m^2.  Only its product
#: with ABSORPTION_EFFICIENCY enters the physics, and that product is the
#: calibrated quantity.
A_PROJ_M2: float = math.pi * CYLINDER_RADIUS_M**2  # ~= 3.46 m^2

#: Fraction of incident solar radiation absorbed by the glazing and air mass,
#: for the default (twin-wall) glazing.  [TUNABLE] At Mars noon (~= 430 W/m^2)
#: with A_PROJ = 3.46 m^2, 0.20 yields a passive equilibrium near 10 deg C.
#: The heater then has work to do, and midday temperatures stay below the
#: crop's lethal-high limit.  Other glazings scale this by their light
#: transmittance relative to REFERENCE_TRANSMITTANCE.
ABSORPTION_EFFICIENCY: float = 0.20

#: Light transmittance of the default (twin-wall) glazing.  The solar-gain and
#: solar-PAR constants are calibrated at this transmittance; a glazing with
#: transmittance t receives t / REFERENCE_TRANSMITTANCE of both.
REFERENCE_TRANSMITTANCE: float = 0.80

# ===========================================================================
# PAR (Photosynthetically Active Radiation)
# ===========================================================================

#: Maximum PAR at crop level when Mars solar irradiance is at peak, through the
#: default (twin-wall) glazing (umol/m^2/s).  [TUNABLE]
PAR_SOLAR_MAX_UMOL_M2_S: float = 800.0

#: Maximum supplemental PAR delivered by the LED array at 100 % intensity.
#: [TUNABLE]
LED_PAR_MAX_UMOL_M2_S: float = 300.0

# ===========================================================================
# Actuator Physical Limits
# ===========================================================================

#: Default ceramic heater output (W).  Teams select 2000 W or 3000 W from the
#: hardware menu in ``hardware.py``; this is the value used when no selection
#: is made.
HEATER_MAX_W: float = 2000.0

#: Fraction of LED electrical power dissipated as heat (waste heat).
LED_HEAT_FRACTION: float = 0.35

#: Maximum LED array electrical power draw (W).  [TUNABLE]
LED_MAX_POWER_W: float = 600.0

#: Maximum CO2 injection rate at 100 % valve opening (ppm/s in the mixing volume).
#: Equates to ~= 60 ppm/min.  [TUNABLE]
CO2_MAX_INJECTION_PPM_S: float = 1.0

#: Maximum irrigation pump rate (VWC/s at 100 % speed).
#: Corresponds to +0.02 VWC per hour at 100 %.  [TUNABLE]
PUMP_MAX_VWC_S: float = 0.02 / 3600.0  # ~= 5.56e-6 VWC/s

# ===========================================================================
# Power System and Launch Mass
# ===========================================================================

#: Battery pack specific energy, space-rated lithium-ion (Wh/kg).  [TUNABLE]
BATTERY_SPECIFIC_ENERGY_WH_KG: float = 125.0

#: Fraction of rated battery capacity that may be discharged in one cycle.
#: [TUNABLE]
BATTERY_USABLE_FRACTION: float = 0.80

#: Launch cost to the Martian surface (USD per kg).
LAUNCH_COST_USD_PER_KG: float = 50_000.0

#: Mission Control's ceiling on the configurable launch mass: glazing, heater,
#: and battery together (kg).  [TUNABLE]
LAUNCH_MASS_CEILING_KG: float = 600.0

# ===========================================================================
# Sensor Noise (1-sigma Gaussian)
# ===========================================================================

NOISE_TEMP_C: float = 0.2  # DHT22 temperature noise (deg C)
NOISE_RH_PCT: float = 1.0  # DHT22 humidity noise (%)
NOISE_CO2_PPM: float = 20.0  # K30 / SCD41 CO2 noise (ppm)
NOISE_VWC: float = 0.01  # TEROS 12 soil moisture noise
NOISE_PAR_UMOL: float = 10.0  # SQ-500 PAR noise (umol/m^2/s)

# ===========================================================================
# Simulation Defaults
# ===========================================================================

#: Default simulation time step (seconds).
DEFAULT_DT_S: float = 60.0

#: Default simulation duration (Martian sols).
DEFAULT_DAYS: int = 30

#: Default random seed for reproducible runs.
DEFAULT_SEED: int = 42

# ===========================================================================
# Lettuce (Lactuca sativa) Crop Setpoints
# ===========================================================================

LETTUCE_TEMP_DAY_C: float = 23.0  # Daytime target (deg C)
LETTUCE_TEMP_NIGHT_C: float = 18.0  # Nighttime target (deg C)

LETTUCE_CO2_LOW_PPM: float = 800.0  # Lower CO2 bound (ppm)
LETTUCE_CO2_HIGH_PPM: float = 1000.0  # Upper CO2 bound (ppm)
LETTUCE_CO2_SETPOINT_PPM: float = 900.0  # PID setpoint (midpoint)

LETTUCE_RH_LOW_PCT: float = 40.0  # Lower RH bound (%)
LETTUCE_RH_HIGH_PCT: float = 60.0  # Upper RH bound (%)
LETTUCE_RH_SETPOINT_PCT: float = 50.0  # PID setpoint (midpoint)

LETTUCE_VWC_SETPOINT: float = 0.40  # Target soil moisture (VWC)

# ===========================================================================
# Safety Thresholds
# ===========================================================================

#: CO2 concentration that is a toxicity limit for the crew (ppm). GHU-2 shares
#: an airlock with crew spaces. The plant model does not evaluate CO2.
CO2_TOXIC_PPM: float = 5000.0

#: Sustained duration at or above CO2_TOXIC_PPM that constitutes a failure (s).
CO2_TOXIC_DURATION_S: float = 1800.0  # 30 minutes

#: K30 freeze profile for the 30-sol mission run by run_simulation (the
#: practice and acceptance tests). The sandbox GUI injects freezes by hand.
MISSION_K30_FREEZE_PROB_PER_STEP: float = 1.5e-4
MISSION_K30_FREEZE_DURATION_RANGE_S: tuple = (1_800.0, 21_600.0)  # 30 min to 6 h

#: Milestone 4 sensor faults, passed to run_simulation as ``sensor_overrides``
#: by the Milestone 4 practice and acceptance tests.  They apply on top of the
#: mission freeze rate above and select the GHU-2 CO2 fault profile (see the
#: GHU-2 commissioning report).  The Milestone 3 tests run without them.
M4_SENSOR_FAULTS: dict = {"fault_profile": "ghu2"}

#: Hard simulation cap on internal CO2 concentration (ppm).
CO2_BOUNDS_MAX_PPM: float = 20_000.0

# ===========================================================================
# Plant Cohort Health: Lethal Exposure Thresholds
# ===========================================================================
# Plants die when a stress accumulator reaches its threshold (seconds of
# sustained exposure).  Only three failure modes are tracked.  The model
# assumes that the controller keeps all other variables in a safe range.

#: Temperature below which exposure is lethal (deg C).
PLANT_LETHAL_LOW_C: float = 5.0

#: Temperature above which exposure is lethal (deg C).
PLANT_LETHAL_HIGH_C: float = 40.0

#: Seconds at PLANT_LETHAL_LOW_C before the cohort dies (2 hours).
PLANT_LETHAL_LOW_DURATION_S: float = 7_200.0

#: Seconds at PLANT_LETHAL_HIGH_C before the cohort dies (1 hour).
PLANT_LETHAL_HIGH_DURATION_S: float = 3_600.0

#: Volumetric water content below which soil is drought-stressed.
PLANT_DROUGHT_VWC: float = 0.10

#: Volumetric water content above which soil is waterlogged.
PLANT_WATERLOG_VWC: float = 0.70

#: Seconds at PLANT_DROUGHT_VWC before the cohort dies (1 sol).
PLANT_DROUGHT_DURATION_S: float = SOL_SECONDS

#: Seconds at PLANT_WATERLOG_VWC before the cohort dies (0.5 sol).
PLANT_WATERLOG_DURATION_S: float = SOL_SECONDS * 0.5

#: PAR below which the light level is insufficient for plant survival.
PLANT_LOW_PAR_UMOL: float = 150.0

#: Cumulative seconds at PLANT_LOW_PAR_UMOL before the cohort dies (2 sols).
PLANT_LOW_LIGHT_DURATION_S: float = SOL_SECONDS * 2.0

# --- Stress recovery time constants (exponential decay, tau = 1/e recovery) ---
# When conditions recover from a stressful band, the accumulated stress decays
# as  s(t) = s_0 * exp(-dt / tau).  A larger tau means slower recovery.
#
# Temperature recovers relatively quickly (0.25 sol ~= 6 h): membrane and
# enzyme damage is partially reversible once temperature is stabilised.
PLANT_RECOVERY_TEMP_TAU_S: float = SOL_SECONDS * 0.25  # ~= 22 194 s

# Soil stress (drought or waterlog) recovers over ~0.5 sol (~= 12 h): root
# tissue and water potential normalise more slowly than air temperature.
PLANT_RECOVERY_SOIL_TAU_S: float = SOL_SECONDS * 0.5  # ~= 44 388 s

# Photosynthetic capacity after a low-light period recovers over ~0.5 sol;
# chloroplast re-orientation and enzyme re-synthesis are relatively slow.
PLANT_RECOVERY_LIGHT_TAU_S: float = SOL_SECONDS * 0.5  # ~= 44 388 s

# --- Scoring ---
#: Number of Martian sols considered a full-credit run.
SCORING_TARGET_SOLS: float = 30.0

#: Gradescope maximum points awarded to the plant survival test.
SCORING_MAX_POINTS: float = 100.0

# ===========================================================================
# Simplified Crop Gas Exchange
# ===========================================================================

#: Effective CO2 scarcity threshold (ppm). [TUNABLE]
#: A conservative teaching abstraction.  It is not a measured lettuce
#: compensation point.  It keeps the finite CO2 inventory well above the
#: 200 ppm lower bound of the CO2 model.
CO2_COMPENSATION_PPM: float = 300.0

#: CO2 above the threshold giving half the availability response. [TUNABLE]
CO2_HALF_AVAILABILITY_PPM: float = 200.0

#: Light level giving half the maximum photosynthetic uptake. [TUNABLE]
PHOTOSYNTHESIS_HALF_PAR: float = 300.0

#: Maximum nominal uptake at 900 ppm and full living biomass (ppm/s). [TUNABLE]
#: Matches the old 0.045 ppm/s at PAR 300, then shows diminishing returns.
PHOTOSYNTHESIS_MAX_PPM_S: float = 0.09

# ===========================================================================
# Water Inventory (Illustrative Small Crop Bed)
# ===========================================================================

#: Bulk substrate volume; VWC * volume * water density is stored water. [TUNABLE]
SUBSTRATE_VOLUME_M3: float = 0.10

#: Liquid water density (kg/m^3).
WATER_DENSITY_KG_M3: float = 1000.0

#: Specific gas constant of water vapour (J/(kg*K)).
WATER_VAPOUR_GAS_CONSTANT: float = 461.5

#: Maximum crop transpiration in wet soil and dry air (VWC/s). [TUNABLE]
#: Light saturation and vapour deficit reduce the actual rate. Set so an
#: unwatered bed dries to the drought threshold in about a week.
TRANSPIRATION_MAX_VWC_S: float = 2.0e-5

#: Slow substrate evaporation in wet soil and dry air (VWC/s). [TUNABLE]
SUBSTRATE_EVAPORATION_VWC_S: float = 5.0e-8

#: Fraction of incoming irrigation exposed to immediate evaporation. [TUNABLE]
IRRIGATION_EVAPORATION_FRACTION: float = 0.02

#: Soil VWC at which the water-availability response reaches one. [TUNABLE]
TRANSPIRATION_WET_VWC: float = 0.30

#: Cold interior surface drop as a fraction of inside/outside delta. [TUNABLE]
#: Higher than the glazing alone (about 0.075 for twin-wall): condensate forms
#: first on the coldest surfaces, the frame and other thermal bridges.
CONDENSATION_SURFACE_FRACTION: float = 0.15

#: Relaxation time of vapour above cold-surface saturation (s). [TUNABLE]
CONDENSATION_TAU_S: float = 300.0

#: Slow vapour-only loss through the envelope (s). [TUNABLE]
#: This represents moisture permeation.  It does not model pressure-driven
#: bulk air leakage.
VAPOUR_LOSS_TAU_S: float = 200_000.0
