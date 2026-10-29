"""
Hardware menu and launch-mass accounting for the Martian greenhouse.

Each team selects one glazing and one heater for GHU-2.  The selection sets
the physics the controller runs against (wall U-value, light transmittance,
heater rating) and the launch mass the team must justify: glazing, heater,
and the battery that carries the greenhouse through its most energy-hungry
sol.

Declaring a selection
---------------------
A controller package declares its hardware in ``student_controller/hardware.py``::

    GLAZING = "twin_wall"   # a key of GLAZING_OPTIONS
    HEATER_W = 2000         # a key of HEATER_OPTIONS_KG

Battery sizing
--------------
The battery is sized to the worst sol of the simulated mission, assuming the
solar arrays deliver nothing (the dust-storm case)::

    capacity_kwh = worst_sol_kwh / BATTERY_USABLE_FRACTION
    battery_kg   = capacity_kwh * 1000 / BATTERY_SPECIFIC_ENERGY_WH_KG

Electrical load is the heater plus the LED array; the pump, CO2 valve, and
sensors are neglected.
"""

from dataclasses import dataclass
from typing import Dict

from .constants import (
    BATTERY_SPECIFIC_ENERGY_WH_KG,
    BATTERY_USABLE_FRACTION,
    LAUNCH_COST_USD_PER_KG,
    SURFACE_AREA_M2,
)


@dataclass(frozen=True)
class Glazing:
    """One wall-glazing option on the hardware menu."""

    key: str
    name: str
    u_value_w_m2_k: float  #: Thermal transmittance (W/(m^2*K))
    transmittance: float  #: Fraction of outside light reaching the crop [0 to 1]
    areal_mass_kg_m2: float  #: Mass per square metre of wall (kg/m^2)
    material_cost_usd_m2: float  #: Purchase cost per square metre (USD/m^2)

    @property
    def mass_kg(self) -> float:
        """Glazing mass for the full greenhouse surface (kg)."""
        return self.areal_mass_kg_m2 * SURFACE_AREA_M2


GLAZING_OPTIONS: Dict[str, Glazing] = {
    g.key: g
    for g in (
        Glazing("polycarbonate", "Single-layer polycarbonate", 1.8, 0.88, 2.0, 200.0),
        Glazing(
            "twin_wall", "Twin-wall polycarbonate (as built)", 0.6, 0.80, 3.5, 400.0
        ),
        Glazing("aerogel", "Aerogel multi-layer", 0.3, 0.50, 8.0, 1500.0),
        Glazing(
            "vacuum_panel", "Vacuum-insulated panel (opaque)", 0.15, 0.0, 12.0, 4000.0
        ),
    )
}

#: Heater rating (W) -> heater mass (kg).
HEATER_OPTIONS_KG: Dict[int, float] = {2000: 6.0, 3000: 9.0}

DEFAULT_GLAZING: str = "twin_wall"
DEFAULT_HEATER_W: int = 2000


def battery_capacity_kwh(worst_sol_kwh: float) -> float:
    """Rated battery capacity needed to carry *worst_sol_kwh* (kWh)."""
    return worst_sol_kwh / BATTERY_USABLE_FRACTION


def battery_mass_kg(worst_sol_kwh: float) -> float:
    """Battery mass needed to carry *worst_sol_kwh* (kg)."""
    return battery_capacity_kwh(worst_sol_kwh) * 1000.0 / BATTERY_SPECIFIC_ENERGY_WH_KG


@dataclass(frozen=True)
class Hardware:
    """A team's hardware selection.  Raises ``ValueError`` if not on the menu."""

    glazing: str = DEFAULT_GLAZING
    heater_w: int = DEFAULT_HEATER_W

    def __post_init__(self) -> None:
        if self.glazing not in GLAZING_OPTIONS:
            raise ValueError(
                f"GLAZING = {self.glazing!r} is not on the hardware menu. "
                f"Choose one of: {', '.join(GLAZING_OPTIONS)}."
            )
        if self.heater_w not in HEATER_OPTIONS_KG:
            raise ValueError(
                f"HEATER_W = {self.heater_w!r} is not on the hardware menu. "
                f"Choose one of: {', '.join(str(w) for w in HEATER_OPTIONS_KG)}."
            )

    @property
    def glazing_spec(self) -> Glazing:
        """The full :class:`Glazing` record for this selection."""
        return GLAZING_OPTIONS[self.glazing]

    @property
    def glazing_mass_kg(self) -> float:
        return self.glazing_spec.mass_kg

    @property
    def heater_mass_kg(self) -> float:
        return HEATER_OPTIONS_KG[self.heater_w]

    def launch_mass_kg(self, worst_sol_kwh: float) -> float:
        """Configurable launch mass: glazing + heater + battery (kg)."""
        return (
            self.glazing_mass_kg
            + self.heater_mass_kg
            + battery_mass_kg(worst_sol_kwh)
        )

    def launch_cost_usd(self, worst_sol_kwh: float) -> float:
        """Launch cost of the configurable mass (USD)."""
        return self.launch_mass_kg(worst_sol_kwh) * LAUNCH_COST_USD_PER_KG
