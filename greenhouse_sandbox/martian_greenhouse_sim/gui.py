"""Interactive sandbox GUI for the Martian Greenhouse Simulation.

This is the Milestone 2 onboarding tool. Students move the actuator sliders or set up
if/elif rule tables. They watch the sensors respond in real time and see the plants
live or die in a drawing of the greenhouse. They can also trigger a K30 freeze fault
themselves. The sandbox is a step between if/elif control structures and the
controller that teams write in Milestone 3.

Run the sandbox on your own computer. It does not run in Codespaces, because tkinter
needs a real display.

From the folder that contains `run_sandbox.py`, run:

    python run_sandbox.py

To start this module directly, run this command from the same folder:

    python -m martian_greenhouse_sim.gui

Suggested sequence of activities:
  1. Start paused at t=0. Read every label and look at the controls.
  2. Press Play at 60 sim-min/s. With every actuator at zero, the plants freeze.
  3. Drive the heater by hand. Notice that night needs much more heat than day.
  4. Add LED light. Notice that the LEDs also add heat.
  5. Trigger a K30 freeze. Watch the two CO2 sensors diverge.
  6. Trigger a dust storm during a sunny day. Watch the solar input drop.
  7. Switch to Auto mode, add a few if/elif rules, and watch them drive the actuators.
  8. Try to keep the plants alive for 5 sols by tuning the rules by hand. Then move on
     to the controller design in Milestone 3.
"""

import copy
import csv
import math
import random
import sys
import time
import tkinter as tk
from dataclasses import dataclass, field, is_dataclass
from tkinter import filedialog, ttk
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import PatchCollection, PolyCollection
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Polygon, Rectangle

from . import co2_faults
from .actuators import VirtualActuators
from .constants import (
    CO2_TOXIC_PPM,
    LETTUCE_CO2_HIGH_PPM,
    LETTUCE_CO2_LOW_PPM,
    LETTUCE_RH_HIGH_PCT,
    LETTUCE_RH_LOW_PCT,
    LETTUCE_TEMP_DAY_C,
    LETTUCE_TEMP_NIGHT_C,
    M4_SENSOR_FAULTS,
    PLANT_DROUGHT_DURATION_S,
    PLANT_LETHAL_HIGH_DURATION_S,
    PLANT_LETHAL_LOW_DURATION_S,
    PLANT_LOW_LIGHT_DURATION_S,
    PLANT_WATERLOG_DURATION_S,
    SOL_SECONDS,
)
from .environment import DustStorm, MarsEnvironment
from .greenhouse import ActuatorState, Greenhouse
from .hardware import Hardware
from .plants import PlantCohort
from .sensors import VirtualSensors

# ---------------------------------------------------------------------------
# GUI configuration
# ---------------------------------------------------------------------------

WINDOW_TITLE = "Martian Greenhouse -- Sandbox"
MISSIONS = ("m3", "m4")
WINDOW_W = 1280
WINDOW_H = 820

# Tick scheduling.
TICK_INTERVAL_MS = 16  # ~60 Hz outer scheduler
RENDER_EVERY_N = 4  # redraw matplotlib every 4 ticks (~15 fps)
CHART_HISTORY_S = 6 * SOL_SECONDS  # rolling 6-sol chart window
SIM_DT_S = 60.0  # each sim step is one sim minute (matches engine default)

# Speed presets: simulated minutes advanced per wall-clock second. Each label
# states its unit.
SPEED_PRESETS = [
    ("1 sim-min/s", 1),
    ("10 sim-min/s", 10),
    ("60 sim-min/s", 60),
    ("600 sim-min/s", 600),
]
DEFAULT_SPEED = 60

# "Back 60 s" can undo this many steps (two sim hours). Each saved step holds the
# three RNG states, about 75 kB, so the buffer stays under 10 MB.
UNDO_MAX_STEPS = 120

# Color palette.
# Scene palette. The sky follows rover images of Mars: butterscotch by day, and grey
# with a blue glow around the sun at dawn and dusk. Sky entries are (zenith, horizon).
COLOR_SKY_NIGHT = ("#070b1c", "#1c2440")
COLOR_SKY_TWILIGHT = ("#43454d", "#8a8682")
COLOR_SKY_DAY = ("#b8875c", "#e1c29a")
COLOR_SKY_STORM = ("#8f6a4c", "#b99470")
COLOR_SUNSET_GLOW = "#8fb6e8"
COLOR_SUN = "#fff7e8"
COLOR_SUN_HALO = "#fff1d6"
COLOR_RIDGE_SHADE = "#5a2d18"
COLOR_GROUND = "#9a4f2a"
COLOR_GROUND_DARK = "#6e3419"
COLOR_ROCK = "#5c2c16"
COLOR_SUPPORT = "#8a8f96"
COLOR_GREENHOUSE_FRAME = "#eef1f4"
COLOR_HEAT_LOSS = "#ff8a5b"
COLOR_FIXTURE_OFF = "#7d7f82"
COLOR_HEATER_ON = "#cc5a36"
COLOR_HEATER_GLOW = "#ff6a3d"
COLOR_LED_OFF = "#9aa0a6"
COLOR_LED = "#fff6b0"
COLOR_LED_CONE = "#fff3b0"
COLOR_CO2_OFF = "#9aa0a6"
COLOR_CO2_ON = "#8fe3ff"
COLOR_PUMP_WATER = "#4f9be8"
COLOR_TRAY = "#6b4a2a"
COLOR_SENSOR = "#e8f5e9"
COLOR_DUST = "#b8835a"
COLOR_PLANT_HEALTHY = "#3fa84a"
# Lettuce leaf shades: (outer, middle, heart).
COLOR_LEAF_HEALTHY = ("#2e7d32", "#4caf50", "#66bb6a")
COLOR_LEAF_STRESSED = ("#9e8b23", "#c7b22b", "#d8c84a")
COLOR_LEAF_DEAD = ("#7a5634", "#8c6440", "#9c744c")

# Rule-engine vocabulary.
SENSOR_KEYS = [
    "temperature_c",
    "rh_pct",
    "co2_k30_ppm",
    "co2_scd41_ppm",
    "co2_discrepancy",
    "soil_vwc",
    "par_umol",
    "is_daytime",
]
OPERATORS = ["<", "<=", ">", ">=", "≈"]
# Equality is approximate, in each sensor's units (not one universal band).
SENSOR_EQUALITY_TOLERANCES = {
    "temperature_c": 0.2,
    "rh_pct": 1.0,
    "co2_k30_ppm": 20.0,
    "co2_scd41_ppm": 20.0,
    "co2_discrepancy": 20.0,
    "soil_vwc": 0.01,
    "par_umol": 10.0,
    "is_daytime": 0.5,
}
ACTUATOR_KEYS = ["heater", "led", "co2_valve", "pump"]
ACTUATOR_LABELS = {
    "heater": "Heater",
    "led": "LED",
    "co2_valve": "CO2 valve",
    "pump": "Irrigation pump",
}

# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


@dataclass
class Rule:
    """One if-then rule: when `sensor op value` is true, output `output_pct`."""

    sensor: str
    op: str
    value: float
    output_pct: float

    def matches(self, readings: Dict[str, float]) -> bool:
        if self.sensor not in readings:
            return False
        v = float(readings[self.sensor])
        try:
            t = float(self.value)
        except (TypeError, ValueError):
            return False
        if self.op == "<":
            return v < t
        if self.op == "<=":
            return v <= t
        if self.op == ">":
            return v > t
        if self.op == ">=":
            return v >= t
        if self.op == "==":
            return abs(v - t) < SENSOR_EQUALITY_TOLERANCES[self.sensor]
        return False


@dataclass
class RuleSet:
    """An ordered list of rules and a default percentage. The first match wins."""

    rules: List[Rule] = field(default_factory=list)
    default_pct: float = 0.0

    def remove_rule(self, rule: Rule) -> None:
        """Remove this exact rule object, even if another rule has the same fields."""
        for index, candidate in enumerate(self.rules):
            if candidate is rule:
                del self.rules[index]
                return
        raise ValueError("Rule is not in this rule set")

    def evaluate(self, readings: Dict[str, float]) -> float:
        return trace_rule_set(self, readings).requested_pct

    def move_rule(self, index: int, direction: int) -> int:
        """Move one rule up or down by one place and return its new index.

        A move past either end of the list leaves the rule where it is.
        """
        if direction not in (-1, 1) or not 0 <= index < len(self.rules):
            raise ValueError("Select a rule and a direction of -1 or 1")
        target = max(0, min(len(self.rules) - 1, index + direction))
        self.rules.insert(target, self.rules.pop(index))
        return target


@dataclass(frozen=True)
class RuleTrace:
    """The decision that one rule set made from the readings of one step."""

    rule_index: Optional[int]
    sensor: Optional[str]
    sensor_value: Optional[float]
    requested_pct: float
    applied_pct: float


def trace_rule_set(rule_set: RuleSet, readings: Dict[str, float]) -> RuleTrace:
    """Find the first matching rule and record the decision.

    This function does not sample the sensors or change any rule.
    """
    for index, rule in enumerate(rule_set.rules):
        if rule.matches(readings):
            requested = float(rule.output_pct)
            return RuleTrace(
                index, rule.sensor, float(readings[rule.sensor]), requested,
                max(0.0, min(100.0, requested)),
            )
    requested = float(rule_set.default_pct)
    return RuleTrace(None, None, None, requested, max(0.0, min(100.0, requested)))


def format_sim_timestamp(time_s: float) -> str:
    """Format a simulation time as the sol number and the local time of day."""
    sol = int(time_s // SOL_SECONDS)
    into_sol = time_s - sol * SOL_SECONDS
    fraction = into_sol / SOL_SECONDS
    total_minutes = fraction * 24.0 * 60.0
    hour = int(total_minutes // 60.0) % 24
    minute = int(total_minutes % 60.0)
    return "Sol {:d}  {:02d}:{:02d} LMST".format(sol, hour, minute)


def parse_target_time(sol_text: str, lmst_text: str) -> Union[float, str]:
    """Convert a sol number and an HH:MM LMST time to simulation seconds.

    Return an error message instead of a time when either field is invalid.
    """
    try:
        sol = int(sol_text.strip())
    except ValueError:
        return "Sol must be a whole number."
    if sol < 0:
        return "Sol must be 0 or more."
    parts = lmst_text.strip().split(":")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        return "LMST must be in the form HH:MM, for example 02:00."
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "LMST must be between 00:00 and 23:59."
    return (sol + (hour * 60 + minute) / (24.0 * 60.0)) * SOL_SECONDS


def achieved_sim_rate(sim_delta_s: float, wall_delta_s: float) -> Optional[float]:
    """Return the simulated minutes per wall-clock second that the loop achieved.

    Return None when the wall-clock interval is zero or negative. On a slow computer
    the loop can run slower than the requested preset. The display shows the measured
    rate so that students can compare runs.
    """
    if wall_delta_s <= 0.0:
        return None
    return (sim_delta_s / 60.0) / wall_delta_s


def format_sim_rate(requested_sim_min_per_s: float,
                    achieved_sim_min_per_s: Optional[float]) -> str:
    if achieved_sim_min_per_s is None:
        return "rate: -- (requested {:g} sim-min/s)".format(requested_sim_min_per_s)
    return "rate: {:.1f} of {:g} sim-min/s".format(
        achieved_sim_min_per_s, requested_sim_min_per_s
    )


def trace_all_rule_sets(
    rule_sets: Dict[str, "RuleSet"], readings: Dict[str, float]
) -> Dict[str, RuleTrace]:
    """Trace every actuator from the same readings, so all panels show one step."""
    return {key: trace_rule_set(rule_sets[key], readings) for key in ACTUATOR_KEYS}


def validate_number(text: str, percentage: bool = False) -> Optional[str]:
    """Return an error message for a field, or None when the field is valid."""
    try:
        number = float(text)
    except (TypeError, ValueError):
        return "Enter a number"
    if not math.isfinite(number):
        return "Enter a finite number"
    if percentage and not 0.0 <= number <= 100.0:
        return "Use 0 to 100%"
    return None


def validate_rule_fields(
    sensor: str, op: str, value: str, output: str
) -> Dict[str, str]:
    """Validate all fields of a rule row together and return the error messages.

    The caller changes the rule only when there are no errors, so an invalid entry
    never changes part of a rule.
    """
    errors = {}
    if sensor not in SENSOR_KEYS:
        errors["sensor"] = "Choose a sensor"
    if op not in OPERATORS + ["=="]:
        errors["op"] = "Choose an operator"
    for name, text, percentage in (("value", value, False), ("output", output, True)):
        error = validate_number(text, percentage)
        if error:
            errors[name] = error
    return errors


def _starter_rule_sets() -> Dict[str, RuleSet]:
    """Return starter rules so that Auto mode drives the actuators from the start.

    The rules are a starting point for students to edit and test.
    """
    return {
        "heater": RuleSet(
            rules=[
                Rule("temperature_c", "<", 15.0, 100.0),
                Rule("temperature_c", "<", 20.0, 60.0),
                Rule("temperature_c", "<", 23.0, 30.0),
            ],
            default_pct=0.0,
        ),
        "led": RuleSet(
            rules=[
                Rule("is_daytime", "==", 1.0, 30.0),
            ],
            default_pct=0.0,
        ),
        "co2_valve": RuleSet(
            rules=[
                Rule("co2_scd41_ppm", "<", 800.0, 40.0),
            ],
            default_pct=0.0,
        ),
        "pump": RuleSet(
            rules=[
                Rule("soil_vwc", "<", 0.30, 100.0),
                Rule("soil_vwc", "<", 0.38, 40.0),
            ],
            default_pct=0.0,
        ),
    }


# ---------------------------------------------------------------------------
# Sensor sampling and fault display
# ---------------------------------------------------------------------------


class SandboxSensors(VirtualSensors):
    """Sensors that use one RNG for measurement noise and another for sensor faults.

    The base class uses one private RNG for both. During tick_faults this class swaps
    in the fault RNG, so the base fault logic runs unchanged and the noise draws and
    fault draws do not affect each other. The swap is safe because the sandbox runs
    on one thread.

    Extra keyword arguments pass through to VirtualSensors. The Milestone 4 mission
    uses this to apply M4_SENSOR_FAULTS. With none given, the sensors are unchanged.
    """

    def __init__(
        self,
        greenhouse: Greenhouse,
        noise_rng: random.Random,
        fault_rng: random.Random,
        **sensor_kwargs,
    ) -> None:
        super().__init__(greenhouse, rng=noise_rng, **sensor_kwargs)
        self._fault_rng = fault_rng

    def tick_faults(self, current_time_s: float, dt_seconds: float) -> None:
        noise_rng = self._rng
        self._rng = self._fault_rng
        try:
            super().tick_faults(current_time_s, dt_seconds)
        finally:
            self._rng = noise_rng


def sample_sensor_readings(
    sensors: VirtualSensors, env: MarsEnvironment
) -> Dict[str, float]:
    """Sample each sensor once for both the rule engine and the display."""
    t, rh = sensors.read_DHT22()
    k30 = sensors.read_K30()
    scd41 = sensors.read_SCD41()
    return {
        "temperature_c": t,
        "rh_pct": rh,
        "co2_k30_ppm": k30,
        "co2_scd41_ppm": scd41,
        "co2_discrepancy": abs(k30 - scd41),
        "soil_vwc": sensors.read_TEROS12(),
        "par_umol": sensors.read_SQ500(),
        "is_daytime": 1.0 if env.is_daytime() else 0.0,
    }


def dust_storm_label(storm: DustStorm) -> str:
    """Describe the scheduled storm using its start and end timestamps."""
    duration_s = storm.end_time_s - storm.start_time_s
    return (
        f"Dust storm scheduled: start sol {storm.start_time_s / SOL_SECONDS:.2f}, "
        f"duration {duration_s / SOL_SECONDS:.1f} sols, tau {storm.peak_tau:.1f}"
    )


# ---------------------------------------------------------------------------
# Data export
# ---------------------------------------------------------------------------

#: Telemetry columns, matching STUDENT_COLUMNS in
#: ``scripts/generate_telemetry_log.py`` (name and order kept in sync by hand,
#: since the scripts directory is not an importable package from here).
TELEMETRY_COLUMNS = [
    "time_s",
    "sol",
    "t_out_c",
    "tau",
    "t_in_c",
    "rh_pct",
    "soil_vwc",
    "par_umol",
    "heater_pct",
    "led_pct",
    "co2_valve_pct",
    "pump_pct",
    "co2_k30_ppm",
    "co2_scd41_ppm",
]

#: Full sandbox log schema: run and clock context first, then the telemetry
#: columns above.
LOG_COLUMNS = ["run", "lmst", "mode"] + TELEMETRY_COLUMNS

#: The log keeps at most this many of the most recent rows, about 20 sols of
#: one-minute steps. A sandbox left running at 600 sim-min/s would otherwise
#: add about 600 rows per wall-clock second without limit.
LOG_MAX_ROWS = 30_000

#: Rows allowed past LOG_MAX_ROWS before a trim, so trimming is not per step.
LOG_TRIM_CHUNK = 1_000


def write_log_csv(rows: List[Dict[str, object]], dest: Union[str, object]) -> int:
    """Write sandbox log rows to CSV. Returns the number of rows written.

    ``dest`` is either a path (``str`` or ``Path``) or an already-open file
    object with a ``write`` method. This function touches no Tk state and no
    simulation state, so tests can call it directly with a list of row dicts.
    Number formatting matches ``write_student_csv`` in
    ``scripts/generate_telemetry_log.py``.
    """

    def _write(f) -> int:
        writer = csv.writer(f)
        writer.writerow(LOG_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    row["run"],
                    row["lmst"],
                    row["mode"],
                    f"{row['time_s']:.0f}",
                    f"{row['sol']:.4f}",
                    f"{row['t_out_c']:.2f}",
                    f"{row['tau']:.2f}",
                    f"{row['t_in_c']:.2f}",
                    f"{row['rh_pct']:.2f}",
                    f"{row['soil_vwc']:.4f}",
                    f"{row['par_umol']:.1f}",
                    f"{row['heater_pct']:.1f}",
                    f"{row['led_pct']:.1f}",
                    f"{row['co2_valve_pct']:.1f}",
                    f"{row['pump_pct']:.1f}",
                    f"{row['co2_k30_ppm']:.1f}",
                    f"{row['co2_scd41_ppm']:.1f}",
                ]
            )
        return len(rows)

    if hasattr(dest, "write"):
        return _write(dest)
    with open(dest, "w", newline="") as f:
        return _write(f)


# ---------------------------------------------------------------------------
# Visual greenhouse panel
# ---------------------------------------------------------------------------


class GreenhouseVisual:
    """Draw the Mars landscape, the GHU-2 capsule, its fixtures, and the crop.

    All artists are on one matplotlib Axes. __init__ creates every artist once, and
    update() changes only their properties (colour, alpha, visibility, vertices, and
    the sky image data). No artist is added or removed after __init__.

    The scene shows no numbers apart from the title. The heat-loss arrows show only
    the size of the inside-outside temperature difference, so students cannot read
    the wall U-value off the drawing.
    """

    PLANT_COUNT = 5
    HULL = (2.2, 1.75, 5.6, 2.5)  # x, y, width, height of the capsule side view
    SKY_EXTENT = (0.0, 10.0, 1.6, 7.0)
    # Rows and columns of the sky image. It is fine enough to draw with nearest
    # sampling, which costs a quarter of the time of a smoothed small image.
    SKY_SHAPE = (96, 160)
    # Leaves of one lettuce rosette: (tilt from vertical in degrees, shade index).
    LEAVES = ((-55.0, 0), (55.0, 0), (-25.0, 1), (25.0, 1), (0.0, 2))
    LEAF_POINTS = 16  # outline points per leaf
    # Heat-loss arrows run from full length at this temperature difference (K).
    ARROW_FULL_DT_K = 90.0

    def __init__(self, ax) -> None:
        self.ax = ax
        ax.set_facecolor(COLOR_SKY_NIGHT[0])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        x, y, w, h = self.HULL
        rgb = {
            name: np.array(to_rgb(color))
            for name, color in (
                ("glow", COLOR_SUNSET_GLOW),
                ("ridge", COLOR_RIDGE_SHADE),
                ("fixture_off", COLOR_FIXTURE_OFF),
                ("heater_on", COLOR_HEATER_ON),
                ("led_off", COLOR_LED_OFF),
                ("led_on", COLOR_LED),
                ("co2_off", COLOR_CO2_OFF),
                ("co2_on", COLOR_CO2_ON),
            )
        }
        self._rgb = rgb
        self._sky_rgb = {
            name: tuple(np.array(to_rgb(c)) for c in pair)
            for name, pair in (
                ("night", COLOR_SKY_NIGHT),
                ("twilight", COLOR_SKY_TWILIGHT),
                ("day", COLOR_SKY_DAY),
                ("storm", COLOR_SKY_STORM),
            )
        }

        # Sky: one gradient image. update() rewrites its pixels for the time of day,
        # the dust, and the blue glow around the sun at dawn and dusk.
        rows, cols = self.SKY_SHAPE
        x0, x1, y0, y1 = self.SKY_EXTENT
        xs = x0 + (np.arange(cols) + 0.5) * (x1 - x0) / cols
        ys = y0 + (np.arange(rows) + 0.5) * (y1 - y0) / rows
        self._sky_x = xs[None, :]
        self._sky_y = ys[:, None]
        self._sky_height = ((ys - y0) / (y1 - y0))[:, None, None]  # 0 low, 1 high
        self.sky = ax.imshow(
            np.zeros((rows, cols, 3), dtype=np.uint8),
            extent=self.SKY_EXTENT,
            origin="lower",
            interpolation="nearest",
            zorder=0,
        )

        # Stars, one collection. Visible at night only.
        rng = random.Random(7)
        stars = []
        star_rgba = []
        for _ in range(40):
            centre = (rng.uniform(0.2, 9.8), rng.uniform(3.2, 6.8))
            stars.append(Circle(centre, rng.choice((0.02, 0.03, 0.04))))
            star_rgba.append((1.0, 1.0, 1.0, rng.uniform(0.4, 0.9)))
        self._star_rgba = np.array(star_rgba)
        self._star_level = -1.0
        self.stars = PatchCollection(
            stars, facecolors=self._star_rgba, edgecolors="none", zorder=1
        )
        ax.add_collection(self.stars, autolim=False)

        # Pale sun with a halo. It sits behind the ridge near the horizon.
        self.sun_halo = Circle(
            (5.0, 5.9), 0.75, facecolor=COLOR_SUN_HALO, edgecolor="none", zorder=1
        )
        self.sun = Circle(
            (5.0, 5.9), 0.32, facecolor=COLOR_SUN, edgecolor="none", zorder=1.1
        )
        ax.add_patch(self.sun_halo)
        ax.add_patch(self.sun)

        # Terrain: a distant ridge (tinted by the sky), then the ground, rocks, and
        # the two saddle supports under the capsule, which never change. The ridge,
        # ground, and dust run past the edges of the view, so that the clipped edge
        # leaves no half-covered pixel column.
        ridge = [(-0.5, 1.6), (-0.5, 2.3), (1.2, 2.6), (2.4, 2.3), (3.8, 2.75),
                 (5.2, 2.4), (6.6, 2.65), (8.1, 2.3), (10.5, 2.6), (10.5, 1.6)]
        self.ridge = Polygon(ridge, closed=True, edgecolor="none", zorder=2)
        ax.add_patch(self.ridge)
        fixed = [
            Rectangle((-0.5, -0.5), 11, 2.25, facecolor=COLOR_GROUND),
            Rectangle((-0.5, -0.5), 11, 0.95, facecolor=COLOR_GROUND_DARK),
        ]
        for rx, ry, rw in ((0.8, 1.2, 0.35), (1.6, 0.8, 0.22), (8.6, 1.0, 0.4),
                           (9.3, 1.4, 0.2)):
            fixed.append(Ellipse((rx, ry), rw, rw * 0.5, facecolor=COLOR_ROCK))
        for sx in (x + 1.3, x + w - 1.3):
            fixed.append(Polygon(
                [(sx - 0.35, 1.55), (sx + 0.35, 1.55), (sx + 0.2, y + 0.15),
                 (sx - 0.2, y + 0.15)],
                facecolor=COLOR_SUPPORT,
            ))
        self.terrain = PatchCollection(fixed, match_original=True, zorder=2.1)
        ax.add_collection(self.terrain, autolim=False)

        # Capsule interior, tinted by the true inside temperature.
        capsule = "round,pad=0,rounding_size={:.3f}"
        self.gh_interior = FancyBboxPatch(
            (x, y), w, h, boxstyle=capsule.format(h / 2),
            facecolor=COLOR_PLANT_HEALTHY, edgecolor="none", alpha=0.28, zorder=4,
        )
        ax.add_patch(self.gh_interior)

        # Heater panel on the left, with a glow that follows the heater output.
        hx, hy = x + 0.45, y + 0.35
        self.heater_glow = Ellipse(
            (hx + 0.18, hy + 0.35), 0.9, 1.0,
            facecolor=COLOR_HEATER_GLOW, edgecolor="none", alpha=0.0, zorder=4.5,
        )
        ax.add_patch(self.heater_glow)
        self.heater_panel = FancyBboxPatch(
            (hx, hy), 0.36, 0.7, boxstyle="round,pad=0.02",
            facecolor=COLOR_FIXTURE_OFF, edgecolor="none", zorder=6,
        )
        ax.add_patch(self.heater_panel)
        nan = float("nan")
        grille_x, grille_y = [], []
        for k in range(3):
            gx = hx + 0.08 + 0.1 * k
            grille_x += [gx, gx, nan]
            grille_y += [hy + 0.08, hy + 0.62, nan]
        (self.heater_grille,) = ax.plot(
            grille_x, grille_y, color="#2b2b2b", linewidth=1, zorder=6.1
        )

        # LED bar under the roof and the light cone it throws on the crop.
        self.led_cone = Polygon(
            [(x + 1.0, y + h - 0.42), (x + w - 1.0, y + h - 0.42),
             (x + w - 0.8, y + 0.45), (x + 0.8, y + 0.45)],
            closed=True, facecolor=COLOR_LED_CONE, edgecolor="none", alpha=0.0,
            zorder=5,
        )
        ax.add_patch(self.led_cone)
        self.led_bar = FancyBboxPatch(
            (x + 1.0, y + h - 0.42), w - 2.0, 0.12, boxstyle="round,pad=0.02",
            facecolor=COLOR_LED_OFF, edgecolor="none", zorder=6,
        )
        ax.add_patch(self.led_bar)

        # Root-zone tray and five lettuce rosettes (all leaves in one collection).
        self.tray = FancyBboxPatch(
            (x + 1.0, y + 0.25), w - 2.0, 0.22, boxstyle="round,pad=0.03",
            facecolor=COLOR_TRAY, edgecolor="none", zorder=5.5,
        )
        ax.add_patch(self.tray)
        step = (w - 2.7) / (self.PLANT_COUNT - 1)
        self._plant_x = x + 1.35 + step * np.arange(self.PLANT_COUNT)
        self._plant_y = y + 0.55
        self._leaf_tilt = np.radians([tilt for tilt, _shade in self.LEAVES])
        self._leaf_shade = [shade for _tilt, shade in self.LEAVES] * self.PLANT_COUNT
        t = np.linspace(0.0, 2.0 * math.pi, self.LEAF_POINTS, endpoint=False)
        self._leaf_cos = np.cos(t)
        self._leaf_sin = np.sin(t)
        self._plant_key = None
        self.plants = PolyCollection(
            self._leaf_polygons(1.0, True), edgecolors="none", zorder=6
        )
        self.plants.set_facecolor(self._leaf_colors(1.0, True))
        ax.add_collection(self.plants, autolim=False)

        # CO2 valve on the right. It lights up while the valve is open.
        vx, vy = x + w - 0.75, y + 0.35
        self.co2_glow = Ellipse(
            (vx + 0.14, vy + 0.25), 0.55, 0.85,
            facecolor=COLOR_CO2_ON, edgecolor="none", alpha=0.0, zorder=5.9,
        )
        ax.add_patch(self.co2_glow)
        self.co2_valve = FancyBboxPatch(
            (vx, vy), 0.28, 0.5, boxstyle="round,pad=0.02",
            facecolor=COLOR_CO2_OFF, edgecolor="none", linewidth=1.2, zorder=6,
        )
        ax.add_patch(self.co2_valve)
        self.co2_label = ax.text(
            vx + 0.14, vy + 0.25, "CO2", fontsize=6, color="#1f2328", ha="center",
            va="center", rotation=90, zorder=6.2,
        )

        # Pump droplet between the tray and the valve, shown while the pump runs.
        self.pump_drop = Polygon(
            self._droplet_points(x + w - 0.95, y + 0.75, 0.085), closed=True,
            facecolor=COLOR_PUMP_WATER, edgecolor="#e8f4ff", linewidth=0.8,
            alpha=0.0, zorder=6,
        )
        ax.add_patch(self.pump_drop)

        # DHT22 sensor on the back wall.
        self.dht22 = Circle(
            (x + w - 1.45, y + h - 0.85), 0.07, facecolor=COLOR_SENSOR,
            edgecolor="none", zorder=6,
        )
        ax.add_patch(self.dht22)

        # Heat-loss arrows out through the wall: start point and outward direction.
        self._arrow_starts = []
        for px, py, dx, dy in ((x + w / 2, y + h, 0.0, 1.0),
                               (x + 1.4, y + h - 0.05, -0.35, 0.94),
                               (x + w - 1.4, y + h - 0.05, 0.35, 0.94),
                               (x - 0.02, y + h / 2, -1.0, 0.0),
                               (x + w + 0.02, y + h / 2, 1.0, 0.0)):
            norm = math.hypot(dx, dy)
            self._arrow_starts.append((px, py, dx / norm, dy / norm))
        self.heat_arrows = PolyCollection(
            self._arrow_polygons(0.15), facecolors=COLOR_HEAT_LOSS,
            edgecolors="none", alpha=0.0, zorder=7,
        )
        ax.add_collection(self.heat_arrows, autolim=False)

        # Capsule hull: twin-wall glazing drawn as an outer and an inner outline.
        self.gh_frame = FancyBboxPatch(
            (x, y), w, h, boxstyle=capsule.format(h / 2), fill=False,
            edgecolor=COLOR_GREENHOUSE_FRAME, linewidth=3, zorder=8,
        )
        ax.add_patch(self.gh_frame)
        self.gh_inner_wall = FancyBboxPatch(
            (x + 0.09, y + 0.09), w - 0.18, h - 0.18,
            boxstyle=capsule.format(h / 2 - 0.09), fill=False,
            edgecolor=COLOR_GREENHOUSE_FRAME, linewidth=1, alpha=0.55, zorder=8,
        )
        ax.add_patch(self.gh_inner_wall)

        # Storm overlay. It covers the whole scene during a storm.
        self.storm = Rectangle(
            (-0.5, -0.5), 11, 8, facecolor=COLOR_DUST, edgecolor="none", alpha=0.0,
            zorder=9,
        )
        ax.add_patch(self.storm)

        # Status text: sol number, mode, outside temperature, and tau.
        self.title = ax.text(
            5, 6.7, "", fontsize=11, color="white", ha="center", va="center",
            zorder=10, family="monospace",
        )

        # imshow resets the view to the image, so set the 10 by 7 view last. The
        # equal aspect leaves a thin strip of figure above the scene; update() paints
        # it the colour of the sky so that it reads as more sky.
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 7)
        ax.set_aspect("equal")
        ax.set_anchor("S")
        self._rgb["dust"] = np.array(to_rgb(COLOR_DUST))

    # ------------------------------------------------------------------ geometry

    def _leaf_polygons(self, scale: float, alive: bool) -> np.ndarray:
        """Leaf outlines for all rosettes, shape (plants * leaves, points, 2).

        A dead rosette is drawn with its leaves splayed flat and drooping.
        """
        tilt = self._leaf_tilt * (1.0 if alive else 1.6)
        droop = 0.0 if alive else -0.1
        length = 0.42 * scale
        half_w = 0.11 * scale
        # Leaf centres relative to the rosette base.
        cx = np.sin(tilt) * length * 0.45
        cy = np.cos(tilt) * length * 0.45 + droop * np.abs(np.sin(tilt))
        # Each leaf is an ellipse, long axis vertical, turned by the tilt.
        lx = half_w * self._leaf_cos
        ly = 0.5 * length * self._leaf_sin
        c, s = np.cos(-tilt)[:, None], np.sin(-tilt)[:, None]
        px = cx[:, None] + lx * c - ly * s  # (leaves, points)
        py = cy[:, None] + lx * s + ly * c
        xs = self._plant_x[:, None, None] + px[None]
        ys = self._plant_y + np.broadcast_to(py, xs.shape)
        return np.stack((xs, ys), axis=-1).reshape(-1, self.LEAF_POINTS, 2)

    def _leaf_colors(self, health: float, alive: bool) -> List[str]:
        """Leaf colours for every leaf. Same health bands as the plant panel."""
        shades = []
        for healthy, stressed, dead in zip(
            COLOR_LEAF_HEALTHY, COLOR_LEAF_STRESSED, COLOR_LEAF_DEAD
        ):
            if not alive:
                shades.append(dead)
            elif health > 0.7:
                shades.append(healthy)
            elif health > 0.3:
                shades.append(
                    self._lerp_color(stressed, healthy, (health - 0.3) / 0.4)
                )
            else:
                shades.append(self._lerp_color(dead, stressed, health / 0.3))
        return [shades[k] for k in self._leaf_shade]

    def _arrow_polygons(self, length: float) -> List[List[tuple]]:
        """Outlines of the heat-loss arrows with a shaft of the given length."""
        shaft, head_w, head_l = 0.025, 0.08, 0.14
        local = [(0.0, -shaft), (length, -shaft), (length, -head_w),
                 (length + head_l, 0.0), (length, head_w), (length, shaft),
                 (0.0, shaft)]
        return [
            [(px + ax_ * ux - ay * uy, py + ax_ * uy + ay * ux) for ax_, ay in local]
            for px, py, ux, uy in self._arrow_starts
        ]

    @staticmethod
    def _droplet_points(cx: float, cy: float, r: float) -> List[tuple]:
        """Water drop outline: round bottom centred on (cx, cy), point on top."""
        tip = 2.2 * r
        side = math.degrees(math.acos(r / tip))  # tangent points, from vertical
        start = math.radians(90.0 + side)
        end = math.radians(450.0 - side)
        pts = [
            (cx + r * math.cos(start + (end - start) * k / 12),
             cy + r * math.sin(start + (end - start) * k / 12))
            for k in range(13)
        ]
        pts.append((cx, cy + tip))
        return pts

    @staticmethod
    def _lerp_color(c0: str, c1: str, t: float) -> str:
        """Blend two hex colors. t = 0 returns c0 and t = 1 returns c1."""
        t = max(0.0, min(1.0, t))
        r0, g0, b0 = int(c0[1:3], 16), int(c0[3:5], 16), int(c0[5:7], 16)
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r = round(r0 + (r1 - r0) * t)
        g = round(g0 + (g1 - g0) * t)
        b = round(b0 + (b1 - b0) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _mix(c0: np.ndarray, c1: np.ndarray, t: float) -> np.ndarray:
        """Blend two RGB arrays. t = 0 returns c0 and t = 1 returns c1."""
        return c0 + (c1 - c0) * max(0.0, min(1.0, t))

    def _sky_colors(self, twilight_d: float, dust: float) -> Tuple[np.ndarray, ...]:
        """Zenith and horizon colours.

        twilight_d is the distance in sols from the nearer of dawn (0.25) and dusk
        (0.75). It is negative on the night side and positive on the day side.
        """
        night, twilight = self._sky_rgb["night"], self._sky_rgb["twilight"]
        day = tuple(
            self._mix(d, s, dust)
            for d, s in zip(self._sky_rgb["day"], self._sky_rgb["storm"])
        )
        if twilight_d < 0.0:
            t = (twilight_d + 0.07) / 0.07
            return tuple(self._mix(n, g, t) for n, g in zip(night, twilight))
        t = twilight_d / 0.08
        return tuple(self._mix(g, d, t) for g, d in zip(twilight, day))

    # -------------------------------------------------------------------- update

    def update(
        self,
        env: MarsEnvironment,
        gh: Greenhouse,
        sensors: VirtualSensors,
        plants: PlantCohort,
        actuators: ActuatorState,
        time_s: float,
        sol_idx: int,
        mode_label: str,
    ) -> None:
        # Sol fraction: midnight 0.0, dawn 0.25, noon 0.5, dusk 0.75.
        sf = (time_s % SOL_SECONDS) / SOL_SECONDS
        twilight_d = sf - 0.25 if sf < 0.5 else 0.75 - sf
        tau = env.get_tau()
        dust = max(0.0, min(1.0, (tau - 0.5) / 6.5))

        # --- Sun on its arc: rises at the left at dawn, sets at the right at dusk ---
        sun_x = 0.5 + 9.0 * (sf - 0.25) / 0.5
        sun_y = 2.0 + 3.9 * math.sin(math.pi * (sf - 0.25) / 0.5)
        if env.is_daytime():
            sun_alpha = max(0.2, 1.0 - tau / 10.0)
            self.sun.center = (sun_x, sun_y)
            self.sun_halo.center = (sun_x, sun_y)
            self.sun.set_alpha(sun_alpha)
            self.sun_halo.set_alpha(0.18 * sun_alpha)
            self.sun.set_visible(True)
            self.sun_halo.set_visible(True)
        else:
            self.sun.set_alpha(0.0)
            self.sun_halo.set_alpha(0.0)
            self.sun.set_visible(False)
            self.sun_halo.set_visible(False)

        # --- Sky: navy at night, butterscotch by day, grey at dawn and dusk with a
        # blue glow around the sun. Dust browns the day sky and hides the glow. ---
        top, horizon = self._sky_colors(twilight_d, dust)
        img = horizon + (top - horizon) * self._sky_height
        glow = 0.9 * max(0.0, 1.0 - abs(twilight_d) / 0.07) * (1.0 - dust)
        if glow > 0.0:
            gx = min(9.7, max(0.3, sun_x))
            gy = max(2.3, sun_y)
            d2 = ((self._sky_x - gx) / 1.8) ** 2 + ((self._sky_y - gy) / 1.4) ** 2
            weight = (glow * np.exp(-d2))[:, :, None]
            img = img + (self._rgb["glow"] - img) * weight
        else:
            img = np.broadcast_to(img, self.SKY_SHAPE + (3,))
        self.sky.set_data((img * 255.0 + 0.5).astype(np.uint8))
        self.ridge.set_facecolor(self._mix(horizon, self._rgb["ridge"], 0.7))

        # Stars fade out toward twilight and behind dust.
        level = round(max(0.0, min(1.0, -twilight_d / 0.1)) * (1.0 - dust), 3)
        if level != self._star_level:
            self._star_level = level
            rgba = self._star_rgba.copy()
            rgba[:, 3] *= level
            self.stars.set_facecolor(rgba)
            self.stars.set_visible(level > 0.0)

        # --- Storm overlay (semi-transparent dust) ---
        storm_alpha = max(0.0, min(0.55, (tau - 0.5) / 8.0))
        self.storm.set_alpha(storm_alpha)
        self.storm.set_visible(storm_alpha > 0.0)
        self.ax.figure.set_facecolor(self._mix(top, self._rgb["dust"], storm_alpha))

        # --- Greenhouse interior tint by temperature ---
        t_in = gh.state.temp_c
        # Tint: blue at 5 C or below, green from 18 to 23 C, orange at 30 C, and
        # red at 40 C or above.
        if t_in < 18.0:
            tint = self._lerp_color(
                "#3a7ec7", COLOR_PLANT_HEALTHY, max(0.0, (t_in - 5.0) / 13.0)
            )
        elif t_in < 30.0:
            tint = self._lerp_color(
                COLOR_PLANT_HEALTHY,
                "#e6a23a",
                (t_in - 23.0) / 7.0 if t_in > 23 else 0.0,
            )
        else:
            tint = self._lerp_color(
                "#e6a23a", "#c43d3d", min(1.0, (t_in - 30.0) / 10.0)
            )
        self.gh_interior.set_facecolor(tint)

        # --- Heat-loss arrows: longer and more opaque as T_in - T_out grows ---
        d_t = max(0.0, t_in - env.get_temperature_c())
        span = min(1.0, d_t / self.ARROW_FULL_DT_K)
        arrow_alpha = (0.25 + 0.6 * span) * min(1.0, d_t / 5.0)
        self.heat_arrows.set_verts(self._arrow_polygons(0.15 + 0.55 * span))
        self.heat_arrows.set_alpha(arrow_alpha)
        self.heat_arrows.set_visible(arrow_alpha > 0.0)

        # --- Actuator fixtures ---
        rgb = self._rgb
        heater = max(0.0, min(1.0, actuators.heater_frac))
        self.heater_glow.set_alpha(0.35 * heater)
        self.heater_glow.set_visible(heater > 0.0)
        self.heater_panel.set_facecolor(
            self._mix(rgb["fixture_off"], rgb["heater_on"], 0.4 + 0.6 * heater)
            if heater > 0.0
            else rgb["fixture_off"]
        )

        led = max(0.0, min(1.0, actuators.led_frac))
        self.led_cone.set_alpha(0.10 + 0.25 * led if led > 0.0 else 0.0)
        self.led_cone.set_visible(led > 0.0)
        self.led_bar.set_facecolor(
            self._mix(rgb["led_off"], rgb["led_on"], 0.4 + 0.6 * led)
            if led > 0.0
            else rgb["led_off"]
        )

        co2 = max(0.0, min(1.0, actuators.co2_valve_frac))
        valve_open = co2 > 0.0
        self.co2_glow.set_alpha(0.25 + 0.35 * co2 if valve_open else 0.0)
        self.co2_glow.set_visible(valve_open)
        self.co2_valve.set_facecolor(
            self._mix(rgb["co2_off"], rgb["co2_on"], 0.5 + 0.5 * co2)
            if valve_open
            else rgb["co2_off"]
        )
        self.co2_valve.set_edgecolor("white" if valve_open else "none")

        pump = max(0.0, min(1.0, actuators.pump_frac))
        self.pump_drop.set_alpha(0.5 + 0.5 * pump if pump > 0.0 else 0.0)
        self.pump_drop.set_visible(pump > 0.0)

        # --- Plants: size and color follow health ---
        # Dead plants are drawn smaller, brown, and wilted flat.
        alive = plants.alive
        health = max(0.0, min(1.0, plants.health))
        scale = 0.4 + 0.6 * health if alive else 0.6
        key = (round(scale, 3), alive, round(health, 3))
        if key != self._plant_key:
            self._plant_key = key
            self.plants.set_verts(self._leaf_polygons(scale, alive))
            self.plants.set_facecolor(self._leaf_colors(health, alive))

        # --- Title text (sol, mode, T_out, tau) ---
        self.title.set_text(
            f"Sol {sol_idx + sf:6.2f}    Mode: {mode_label:>6s}    "
            f"T_out {env.get_temperature_c():+6.1f} C    tau {tau:4.2f}"
        )


# ---------------------------------------------------------------------------
# Time-series chart
# ---------------------------------------------------------------------------


CO2_DEFAULT_LIMITS = (0.0, 1600.0)


def co2_axis_limits(co2_ppm: List[float]) -> Tuple[float, float]:
    """Return the y-axis limits for the CO2 plot.

    Use 0 to 1600 ppm while every reading is at or below 1600 ppm. Otherwise, set the
    top of the axis 10% above the larger of the toxic limit and the peak reading.
    """
    peak = max(co2_ppm, default=0.0)
    if peak <= CO2_DEFAULT_LIMITS[1]:
        return CO2_DEFAULT_LIMITS
    return (0.0, 1.1 * max(CO2_TOXIC_PPM, peak))


class TimeSeriesChart:
    """Four stacked plots (T, CO2, RH, soil VWC) with the target bands shaded."""

    def __init__(self, fig) -> None:
        gs = fig.add_gridspec(4, 1, hspace=0.4)
        self.ax_t = fig.add_subplot(gs[0])
        self.ax_co2 = fig.add_subplot(gs[1], sharex=self.ax_t)
        self.ax_rh = fig.add_subplot(gs[2], sharex=self.ax_t)
        self.ax_soil = fig.add_subplot(gs[3], sharex=self.ax_t)

        for ax in (self.ax_t, self.ax_co2, self.ax_rh, self.ax_soil):
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=7)

        # Lines (initially empty).
        (self.line_t,) = self.ax_t.plot([], [], color="#c43d3d", lw=1.5)
        (self.line_co2,) = self.ax_co2.plot([], [], color="#3a7ec7", lw=1.5)
        (self.line_rh,) = self.ax_rh.plot([], [], color="#2ca74a", lw=1.5)
        (self.line_soil,) = self.ax_soil.plot([], [], color="#8b4513", lw=1.5)

        # Target bands.
        self.ax_t.axhspan(
            LETTUCE_TEMP_NIGHT_C, LETTUCE_TEMP_DAY_C, color="green", alpha=0.10
        )
        self.ax_co2.axhspan(
            LETTUCE_CO2_LOW_PPM, LETTUCE_CO2_HIGH_PPM, color="green", alpha=0.10
        )
        self.ax_rh.axhspan(
            LETTUCE_RH_LOW_PCT, LETTUCE_RH_HIGH_PCT, color="green", alpha=0.10
        )
        self.ax_soil.axhspan(0.30, 0.50, color="green", alpha=0.10)

        # Dashed line at the toxic CO2 level. hlines draws it as a collection,
        # which keeps it separate from the data lines.
        self.ax_co2.hlines(
            CO2_TOXIC_PPM,
            0,
            1,
            transform=self.ax_co2.get_yaxis_transform(),
            color="red",
            lw=1,
            ls="--",
            alpha=0.5,
        )
        (self.co2_overrange,) = self.ax_co2.plot(
            [],
            [],
            "r^",
            transform=self.ax_co2.get_yaxis_transform(),
            clip_on=False,
        )

        self.ax_t.set_ylabel(r"T ($^\circ$C)", fontsize=8)
        self.ax_co2.set_ylabel("CO2 (ppm)", fontsize=8)
        self.ax_rh.set_ylabel("RH (%)", fontsize=8)
        self.ax_soil.set_ylabel("Soil VWC", fontsize=8)
        self.ax_soil.set_xlabel("Sol", fontsize=8)

        self._restore_limits()

    def _restore_limits(self) -> None:
        self.ax_t.set_xlim(0, 0.5)
        self.ax_t.set_ylim(-5, 45)
        self.ax_co2.set_ylim(*CO2_DEFAULT_LIMITS)
        self.ax_rh.set_ylim(0, 100)
        self.ax_soil.set_ylim(0, 1)

    def update(
        self,
        times_s: List[float],
        temps_c: List[float],
        co2_ppm: List[float],
        rh_pct: List[float],
        soil_vwc: List[float],
        latest_co2_ppm: Optional[float] = None,
    ) -> None:
        if not times_s:
            for line in (
                self.line_t,
                self.line_co2,
                self.line_rh,
                self.line_soil,
                self.co2_overrange,
            ):
                line.set_data([], [])
            self._restore_limits()
            return
        sols = [t / SOL_SECONDS for t in times_s]
        self.line_t.set_data(sols, temps_c)
        self.line_co2.set_data(sols, co2_ppm)
        self.line_rh.set_data(sols, rh_pct)
        self.line_soil.set_data(sols, soil_vwc)
        self.ax_co2.set_ylim(*co2_axis_limits(co2_ppm))
        # History keeps one point every 5 sim minutes. If the latest CO2 value is
        # above the axis, mark it with a triangle at the top edge until the next
        # logged point.
        latest = co2_ppm[-1] if latest_co2_ppm is None else latest_co2_ppm
        top = self.ax_co2.get_ylim()[1]
        if latest > top:
            self.co2_overrange.set_data([1.0], [top])
        else:
            self.co2_overrange.set_data([], [])
        x_lo = max(0.0, sols[-1] - CHART_HISTORY_S / SOL_SECONDS)
        x_hi = max(sols[-1], x_lo + 0.5)
        for ax in (self.ax_t, self.ax_co2, self.ax_rh, self.ax_soil):
            ax.set_xlim(x_lo, x_hi)


# ---------------------------------------------------------------------------
# Rule editor: one Frame per actuator, with rows added and removed at run time
# ---------------------------------------------------------------------------


class RuleRow:
    """One editable row in a rule table: sensor, operator, value, output, buttons."""

    def __init__(
        self,
        parent: tk.Widget,
        rule: Rule,
        on_change: Callable[[], None],
        on_delete: Callable[["RuleRow"], None],
        on_move: Callable[["RuleRow", int], None],
    ) -> None:
        self.frame = tk.Frame(parent)
        self.rule = rule
        self.on_change = on_change
        self.on_delete = on_delete

        self.sensor_var = tk.StringVar(value=rule.sensor)
        self.op_var = tk.StringVar(value="≈" if rule.op == "==" else rule.op)
        self.value_var = tk.StringVar(value=f"{rule.value:g}")
        self.output_var = tk.StringVar(value=f"{rule.output_pct:g}")

        self.order_label = tk.Label(self.frame, text="IF")
        self.order_label.pack(side="left", padx=2)
        ttk.Combobox(
            self.frame,
            textvariable=self.sensor_var,
            values=SENSOR_KEYS,
            width=18,
            state="readonly",
        ).pack(side="left", padx=2)
        ttk.Combobox(
            self.frame,
            textvariable=self.op_var,
            values=OPERATORS,
            width=4,
            state="readonly",
        ).pack(side="left", padx=2)
        self.value_entry = tk.Entry(self.frame, textvariable=self.value_var, width=8)
        self.value_entry.pack(side="left", padx=2)
        tk.Label(self.frame, text="  THEN  output =").pack(side="left", padx=2)
        self.output_entry = tk.Entry(self.frame, textvariable=self.output_var, width=6)
        self.output_entry.pack(side="left", padx=2)
        tk.Label(self.frame, text="%").pack(side="left")
        tk.Button(self.frame, text="X", width=2, command=self._delete).pack(
            side="left", padx=6
        )
        for text, direction in (("Up", -1), ("Down", 1)):
            tk.Button(
                self.frame, text=text,
                command=lambda d=direction: on_move(self, d),
            ).pack(side="left")
        self.feedback = tk.Label(self.frame, text="", anchor="w")
        self.feedback.pack(side="left", padx=4)
        self.errors: Dict[str, str] = {}

        for var in (self.sensor_var, self.op_var, self.value_var, self.output_var):
            var.trace_add("write", lambda *_: self._sync())

    def _sync(self) -> None:
        self.errors = validate_rule_fields(
            self.sensor_var.get(), self.op_var.get(),
            self.value_var.get(), self.output_var.get(),
        )
        if hasattr(self, "feedback"):
            self.feedback.config(text="; ".join(self.errors.values()))
            for name in ("value", "output"):
                getattr(self, name + "_entry").config(
                    background="#ffe0e0" if name in self.errors else "white"
                )
        if self.errors:
            self.on_change()
            return
        op = self.op_var.get()
        self.rule.sensor = self.sensor_var.get()
        self.rule.op = "==" if op == "≈" else op
        self.rule.value = float(self.value_var.get())
        self.rule.output_pct = float(self.output_var.get())
        self.on_change()

    def _delete(self) -> None:
        self.on_delete(self)


class ActuatorRulePanel:
    """The rules table for a single actuator."""

    def __init__(
        self,
        parent: tk.Widget,
        actuator_key: str,
        rule_set: RuleSet,
    ) -> None:
        self.actuator_key = actuator_key
        self.rule_set = rule_set
        self.rows: List[RuleRow] = []

        outer = tk.LabelFrame(
            parent, text=f"{ACTUATOR_LABELS[actuator_key]} rules", padx=6, pady=4
        )
        outer.pack(fill="x", padx=6, pady=4)
        self.outer = outer

        self.rows_frame = tk.Frame(outer)
        self.rows_frame.pack(fill="x")
        self.trace_label = tk.Label(outer, text="No step yet", anchor="w")
        self.trace_label.pack(fill="x")

        # Footer: the ELSE output and the Add rule button.
        footer = tk.Frame(outer)
        footer.pack(fill="x", pady=2)
        tk.Label(footer, text="ELSE output =").pack(side="left")
        self.default_var = tk.StringVar(value=f"{rule_set.default_pct:g}")
        tk.Entry(footer, textvariable=self.default_var, width=6).pack(
            side="left", padx=2
        )
        tk.Label(footer, text="%").pack(side="left")
        self.default_feedback = tk.Label(footer, text="")
        self.default_feedback.pack(side="left", padx=4)
        tk.Button(footer, text="+ Add rule", command=self._add_rule).pack(
            side="right", padx=4
        )
        self.default_var.trace_add("write", lambda *_: self._sync_default())

        for r in rule_set.rules:
            self._add_row_widget(r)

    def _add_row_widget(self, rule: Rule) -> None:
        row = RuleRow(
            self.rows_frame, rule, on_change=self._edited, on_delete=self._delete_row,
            on_move=self._move_row,
        )
        row.frame.pack(fill="x", pady=1)
        self.rows.append(row)
        self._edited()

    def _add_rule(self) -> None:
        new = Rule(sensor="temperature_c", op="<", value=20.0, output_pct=50.0)
        self.rule_set.rules.append(new)
        self._add_row_widget(new)

    def _delete_row(self, row: RuleRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
            try:
                self.rule_set.remove_rule(row.rule)
            except ValueError:
                pass
            row.frame.destroy()
            self._edited()

    def _move_row(self, row: RuleRow, direction: int) -> None:
        index = self.rows.index(row)
        target = self.rule_set.move_rule(index, direction)
        self.rows.insert(target, self.rows.pop(index))
        for item in self.rows:
            item.frame.pack_forget()
            item.frame.pack(fill="x", pady=1)
        self._edited()

    def _sync_default(self) -> None:
        error = validate_number(self.default_var.get(), percentage=True)
        self.default_feedback.config(text=error or "")
        if not error:
            self.rule_set.default_pct = float(self.default_var.get())
        self._edited()

    def _edited(self) -> None:
        self.show_trace(None, "Edited: next step uses last valid field values")

    def show_trace(
        self, trace: Optional[RuleTrace], message: str = "Manual mode"
    ) -> None:
        for index, row in enumerate(self.rows):
            if hasattr(row, "order_label"):
                matched = trace is not None and trace.rule_index == index
                row.order_label.config(
                    text=f"{'>' if matched else ' '} {index + 1} "
                    + ("IF" if index == 0 else "ELIF"),
                    background="#fff0a6" if matched else row.frame.cget("bg"),
                )
        if not hasattr(self, "trace_label"):
            return
        if trace is not None:
            source = "ELSE (no match)"
            if trace.rule_index is not None:
                source = (
                    f"Row {trace.rule_index + 1}: {trace.sensor} = "
                    f"{trace.sensor_value:g}"
                )
            message = (
                f"> {source}; requested {trace.requested_pct:g}% "
                f"-> applied {trace.applied_pct:g}%"
            )
        self.trace_label.config(text=message)


# ---------------------------------------------------------------------------
# Main sandbox application
# ---------------------------------------------------------------------------


class GreenhouseSandbox:
    """Top-level tkinter window holding all panels and the simulation loop."""

    # "m3" is the Milestone 3 sandbox. "m4" applies the Milestone 4 sensor faults.
    mission: str = "m3"

    def __init__(
        self,
        root: tk.Tk,
        seed: int = 42,
        hardware: Optional[Hardware] = None,
        mission: str = "m3",
    ) -> None:
        if mission not in MISSIONS:
            raise ValueError(f"mission must be one of {MISSIONS}, got {mission!r}")
        self.root = root
        self.seed = seed
        self.mission = mission
        self.hardware = hardware or Hardware()
        mission_note = "  |  Milestone 4 faults" if mission == "m4" else ""
        root.title(
            f"{WINDOW_TITLE}  |  {self.hardware.glazing_spec.name}, "
            f"{self.hardware.heater_w} W heater{mission_note}"
        )
        root.geometry(f"{WINDOW_W}x{WINDOW_H}")

        # Run log: one row per simulation step, since launch. Reset bumps
        # ``run`` but never clears ``log``; see ``_reset`` and ``_record_step``.
        self.run: int = 1
        self.log: List[Dict[str, object]] = []

        # Simulation state.
        self.rng = random.Random(seed)
        self.env: MarsEnvironment
        self.gh: Greenhouse
        self.sensors: VirtualSensors
        self.actuators: VirtualActuators
        self.plants: PlantCohort
        self.time_s: float
        self.sol_idx: int
        self.actuator_state: ActuatorState  # last applied actuator state
        self._init_simulation()

        # UI state.
        self.paused = tk.BooleanVar(value=True)
        self.mode_auto = tk.BooleanVar(value=False)
        self.speed = DEFAULT_SPEED
        self.rule_sets: Dict[str, RuleSet] = _starter_rule_sets()

        # Manual slider values (one DoubleVar per actuator).
        self.manual_vars: Dict[str, tk.DoubleVar] = {
            k: tk.DoubleVar(value=0.0) for k in ACTUATOR_KEYS
        }

        # Chart history.
        self.hist_t: List[float] = []
        self.hist_temp: List[float] = []
        self.hist_co2: List[float] = []
        self.hist_rh: List[float] = []
        self.hist_soil: List[float] = []

        # Render counter.
        self._render_counter = 0
        self._step_accumulator = 0.0  # carries fractional steps between ticks

        # Build the UI.
        self._build_ui()

        # Start the tick loop.
        self.root.after(TICK_INTERVAL_MS, self._tick)

    # ------------------------------------------------------------------ init

    def _init_simulation(self) -> None:
        """Create or re-create the simulation state at t=0."""
        self.last_traces: Dict[str, RuleTrace] = {}
        # Saved states for "Back 60 s", newest last. Reset clears them, so the
        # clock never steps back across a Reset.
        self._undo: List[Dict[str, object]] = []
        # Target time (s) for "Run to", or None when no target is set.
        self._run_to_s: Optional[float] = None
        self.rng = random.Random(self.seed)
        self.env = MarsEnvironment(initial_time_s=0.0, rng=self.rng)
        # Schedule a dust storm so that students see one on longer runs.
        self.env.schedule_dust_storm(
            start_time_s=2.0 * SOL_SECONDS,
            duration_s=3.0 * SOL_SECONDS,
        )
        glazing = self.hardware.glazing_spec
        self.gh = Greenhouse(
            initial_temp_c=15.0,
            initial_co2_ppm=900.0,
            initial_rh_pct=50.0,
            initial_soil_vwc=0.40,
            u_value=glazing.u_value_w_m2_k,
            transmittance=glazing.transmittance,
        )
        self.sensors = SandboxSensors(
            self.gh,
            noise_rng=random.Random(f"{self.seed}:sensor-noise"),
            fault_rng=random.Random(f"{self.seed}:sensor-faults"),
            **(M4_SENSOR_FAULTS if self.mission == "m4" else {}),
        )
        # Take one sample now so the display has readings at t=0 while paused.
        # Rendering never takes a new sample.
        self.readings = sample_sensor_readings(self.sensors, self.env)
        self.actuators = VirtualActuators(heater_max_w=self.hardware.heater_w)
        self.plants = PlantCohort()
        self.time_s = 0.0
        self.sol_idx = 0
        # Achieved-rate measurement window (wall clock vs sim clock).
        self._rate_wall_s = time.monotonic()
        self._rate_sim_s = 0.0
        self._achieved_rate = None
        self.actuator_state = ActuatorState()
        self.hist_t = []
        self.hist_temp = []
        self.hist_co2 = []
        self.hist_rh = []
        self.hist_soil = []

    # -------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        # --- Top control bar -------------------------------------------------
        top = tk.Frame(self.root, padx=6, pady=4)
        top.pack(side="top", fill="x")

        tk.Button(top, text="Pause / Play", width=12, command=self._toggle_pause).pack(
            side="left", padx=2
        )
        tk.Button(top, text="Reset", width=8, command=self._reset).pack(
            side="left", padx=2
        )

        tk.Button(
            top, text="Back {:g} s".format(SIM_DT_S), width=10, command=self._step_back
        ).pack(side="left", padx=2)
        tk.Button(
            top, text="Step {:g} s".format(SIM_DT_S), width=10, command=self._step_60s
        ).pack(side="left", padx=2)

        tk.Button(
            top, text="Save data (CSV)", width=16, command=self._save_data
        ).pack(side="left", padx=2)

        tk.Label(top, text="   Speed: ").pack(side="left")
        self.speed_var = tk.IntVar(value=DEFAULT_SPEED)
        for label, val in SPEED_PRESETS:
            tk.Radiobutton(
                top,
                text=label,
                variable=self.speed_var,
                value=val,
                command=self._set_speed,
            ).pack(side="left")

        # The mode checkbox and "Run to" get a second row. With the Back button
        # on the first row, the checkbox ran off the right edge at 1280 px.
        second = tk.Frame(self.root, padx=6)
        second.pack(side="top", fill="x")
        tk.Label(second, text="Mode: ").pack(side="left")
        tk.Checkbutton(
            second, text="Auto (rules drive actuators)", variable=self.mode_auto
        ).pack(side="left", padx=4)

        # "Run to": play at the selected speed and pause on the chosen time.
        tk.Label(second, text="      Run to  Sol").pack(side="left")
        self.run_to_sol = tk.Spinbox(second, from_=0, to=999, width=4)
        self.run_to_sol.pack(side="left", padx=2)
        self.run_to_lmst = tk.Entry(second, width=6)
        self.run_to_lmst.insert(0, "02:00")
        self.run_to_lmst.pack(side="left", padx=2)
        tk.Label(second, text="LMST").pack(side="left")
        tk.Button(second, text="Run to", width=7, command=self._run_to).pack(
            side="left", padx=4
        )
        self.run_to_lmst.bind("<Return>", lambda _event: self._run_to())

        # The clock, rate, and status get their own row. On one row they sat at
        # the right end and were squeezed to nothing at the default width.
        info = tk.Frame(self.root, padx=6)
        info.pack(side="top", fill="x")
        self.clock_label = tk.Label(info, text=format_sim_timestamp(0.0))
        self.clock_label.pack(side="left", padx=2)
        self.rate_label = tk.Label(info, text=format_sim_rate(DEFAULT_SPEED, None))
        self.rate_label.pack(side="left", padx=12)
        self.status_label = tk.Label(info, text="(paused -- press Play)", fg="#666")
        self.status_label.pack(side="left", padx=12)

        # --- Middle row: visual | sensors+plants | chart ---------------------
        middle = tk.Frame(self.root)
        middle.pack(side="top", fill="both", expand=True)

        # Visual greenhouse on the left.
        self.fig_vis = Figure(figsize=(5.5, 4.0), dpi=90)
        self.ax_vis = self.fig_vis.add_subplot(111)
        self.fig_vis.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.visual = GreenhouseVisual(self.ax_vis)
        self.canvas_vis = FigureCanvasTkAgg(self.fig_vis, master=middle)
        self.canvas_vis.draw()
        self.canvas_vis.get_tk_widget().pack(side="left", padx=6, pady=4)

        # Sensor + plant text panel in the middle.
        info = tk.Frame(middle, padx=8, pady=4)
        info.pack(side="left", fill="y")
        self._build_info_panel(info)

        # Chart on the right.
        self.fig_chart = Figure(figsize=(5.0, 4.0), dpi=90)
        self.chart = TimeSeriesChart(self.fig_chart)
        self.canvas_chart = FigureCanvasTkAgg(self.fig_chart, master=middle)
        self.canvas_chart.draw()
        self.canvas_chart.get_tk_widget().pack(
            side="left", fill="both", expand=True, padx=6, pady=4
        )

        # --- Bottom tabs: Actuators / Rules / Faults -------------------------
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(side="bottom", fill="x", padx=6, pady=4)

        actuator_tab = tk.Frame(self.tabs)
        rules_tab = tk.Frame(self.tabs)
        faults_tab = tk.Frame(self.tabs)
        self.tabs.add(actuator_tab, text="Actuators (Manual)")
        self.tabs.add(rules_tab, text="Rules (Auto)")
        self.tabs.add(faults_tab, text="Faults")

        self._build_actuator_tab(actuator_tab)
        self._build_rules_tab(rules_tab)
        self._build_faults_tab(faults_tab)

    def _build_info_panel(self, parent: tk.Widget) -> None:
        # Sensors block.
        sensors_box = tk.LabelFrame(parent, text="Sensors", padx=6, pady=4)
        sensors_box.pack(fill="x", pady=2)
        self.lbl_dht_t = tk.Label(
            sensors_box,
            text="DHT22 T  : --.- deg C",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_dht_rh = tk.Label(
            sensors_box,
            text="DHT22 RH : --.- %",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_k30 = tk.Label(
            sensors_box,
            text="K30 CO2  : ---- ppm",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_scd41 = tk.Label(
            sensors_box,
            text="SCD41    : ---- ppm",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_dco2 = tk.Label(
            sensors_box,
            text="| K30 - SCD41 | = -- ppm",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_teros = tk.Label(
            sensors_box,
            text="TEROS12  : 0.-- VWC",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        self.lbl_sq500 = tk.Label(
            sensors_box,
            text="SQ500    : --- umol",
            anchor="w",
            width=24,
            font=("TkFixedFont",),
        )
        for lbl in (
            self.lbl_dht_t,
            self.lbl_dht_rh,
            self.lbl_k30,
            self.lbl_scd41,
            self.lbl_dco2,
            self.lbl_teros,
            self.lbl_sq500,
        ):
            lbl.pack(anchor="w")

        # Plant cohort block.
        plant_box = tk.LabelFrame(parent, text="Plant cohort", padx=6, pady=4)
        plant_box.pack(fill="x", pady=4)
        self.lbl_alive = tk.Label(
            plant_box, text="Status : ALIVE", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_health = tk.Label(
            plant_box, text="Health : 1.00", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_stress_tlow = tk.Label(
            plant_box, text="cold     :   0 %", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_stress_thigh = tk.Label(
            plant_box, text="heat     :   0 %", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_stress_drought = tk.Label(
            plant_box, text="drought  :   0 %", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_stress_water = tk.Label(
            plant_box, text="waterlog :   0 %", anchor="w", font=("TkFixedFont",)
        )
        self.lbl_stress_light = tk.Label(
            plant_box, text="low_light:   0 %", anchor="w", font=("TkFixedFont",)
        )
        for lbl in (
            self.lbl_alive,
            self.lbl_health,
            self.lbl_stress_tlow,
            self.lbl_stress_thigh,
            self.lbl_stress_drought,
            self.lbl_stress_water,
            self.lbl_stress_light,
        ):
            lbl.pack(anchor="w")

    def _build_actuator_tab(self, parent: tk.Widget) -> None:
        tk.Label(
            parent,
            text=(
                "In MANUAL mode, drag the sliders. In AUTO mode, sliders show "
                "what the rules are commanding."
            ),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=8, pady=4)

        grid = tk.Frame(parent)
        grid.pack(fill="x", padx=10, pady=4)

        self.slider_widgets: Dict[str, tk.Scale] = {}
        for row, key in enumerate(ACTUATOR_KEYS):
            tk.Label(grid, text=ACTUATOR_LABELS[key], width=15, anchor="w").grid(
                row=row, column=0, sticky="w", padx=4, pady=2
            )
            s = tk.Scale(
                grid,
                from_=0,
                to=100,
                orient="horizontal",
                length=420,
                resolution=1,
                variable=self.manual_vars[key],
            )
            s.grid(row=row, column=1, sticky="w")
            self.slider_widgets[key] = s

    def _build_rules_tab(self, parent: tk.Widget) -> None:
        tk.Label(
            parent,
            text=(
                "Configure rules per actuator. In AUTO mode, the first matching "
                "rule wins; otherwise ELSE fires."
            ),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=8, pady=4)

        canvas = tk.Canvas(parent, height=240)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=8)
        scrollbar.pack(side="right", fill="y")

        self.rule_panels: Dict[str, ActuatorRulePanel] = {}
        for key in ACTUATOR_KEYS:
            self.rule_panels[key] = ActuatorRulePanel(
                scroll_frame, key, self.rule_sets[key]
            )

    def _build_faults_tab(self, parent: tk.Widget) -> None:
        tk.Label(
            parent,
            text=(
                "Deliberately inject faults to study controller responses "
                "without waiting for the schedule."
            ),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=8, pady=6)

        btns = tk.Frame(parent)
        btns.pack(fill="x", padx=10, pady=4)
        tk.Button(
            btns,
            text="Inject K30 freeze (5 sim min)",
            width=32,
            command=self._inject_k30_freeze,
        ).pack(side="left", padx=4)
        if self.mission == "m4":
            tk.Button(
                btns,
                text="Start SCD41 drift",
                width=28,
                command=self._inject_scd41_drift,
            ).pack(side="left", padx=4)
        tk.Button(
            btns,
            text="Trigger dust storm now",
            width=24,
            command=self._trigger_dust_storm,
        ).pack(side="left", padx=4)

        self.fault_status = tk.Label(parent, text="", anchor="w", fg="#666")
        self.fault_status.pack(fill="x", padx=10, pady=4)

    # ------------------------------------------------------------- callbacks

    def _step_60s(self) -> None:
        """Advance one SIM_DT_S step and redraw. The simulation stays paused."""
        self.paused.set(True)
        self._run_to_s = None
        self._step_accumulator = 0.0
        self._step_one()
        self.status_label.config(
            text="(stepped {:g} s -- paused)".format(SIM_DT_S), fg="#666"
        )
        self._render_text()
        self._render_full()

    def _step_back(self) -> None:
        """Undo the most recent step and redraw. The simulation stays paused."""
        self.paused.set(True)
        self._run_to_s = None
        self._step_accumulator = 0.0
        if not self._undo:
            self.status_label.config(
                text="(cannot step back further -- start of the run, or {:g} sim "
                "hours back)".format(UNDO_MAX_STEPS * SIM_DT_S / 3600.0),
                fg="#c43d3d",
            )
            return
        self._restore_state(self._undo.pop())
        self.status_label.config(
            text="(stepped back {:g} s -- paused)".format(SIM_DT_S), fg="#666"
        )
        self._render_text()
        self._render_full()

    def _run_to(self) -> None:
        """Play at the selected speed and pause when the clock reaches the target."""
        target = parse_target_time(self.run_to_sol.get(), self.run_to_lmst.get())
        if isinstance(target, str):
            self.status_label.config(text=f"(Run to: {target})", fg="#c43d3d")
            return
        stamp = format_sim_timestamp(target)
        if format_sim_timestamp(self.time_s) == stamp:
            self.paused.set(True)
            self.status_label.config(text=f"(already at {stamp} -- paused)", fg="#666")
            return
        if target < self.time_s:
            self.status_label.config(
                text=f"({stamp} has passed -- press Reset to start the run again)",
                fg="#c43d3d",
            )
            return
        self._run_to_s = target
        self.paused.set(False)
        self.status_label.config(text=f"(running to {stamp})", fg="#2ca74a")

    def _arrive(self) -> None:
        """Pause at the Run to target."""
        self._run_to_s = None
        self.paused.set(True)
        self._step_accumulator = 0.0
        self.status_label.config(
            text="(reached {} -- paused)".format(format_sim_timestamp(self.time_s)),
            fg="#666",
        )

    def _save_data(self) -> None:
        """Write the full run log to a CSV the student picks with a save dialog."""
        default_name = f"ghu2_sandbox_seed{self.seed}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        rows = write_log_csv(self.log, path)
        self.status_label.config(text=f"Saved {rows} rows to {path}", fg="#666")

    def _toggle_pause(self) -> None:
        self.paused.set(not self.paused.get())
        # A manual pause cancels a Run to target.
        if self.paused.get():
            self._run_to_s = None
        self.status_label.config(
            text=("(paused -- press Play)" if self.paused.get() else "(running)"),
            fg=("#666" if self.paused.get() else "#2ca74a"),
        )

    def _reset(self) -> None:
        # A new run starts; the log itself is not cleared (records everything
        # since launch, across every run).
        self.run += 1
        self._init_simulation()
        self.paused.set(True)
        self._step_accumulator = 0.0
        self.fault_status.config(text="")
        self._render_text()
        self.status_label.config(text="(reset -- press Play)", fg="#666")
        # Redraw now so the greenhouse view also resets.
        self._render_full()

    def _set_speed(self) -> None:
        self.speed = self.speed_var.get()

    def _inject_k30_freeze(self) -> None:
        # Starts a freeze through the fault model, with its draws taken from the
        # fault RNG, so a sandbox freeze behaves like a freeze in a mission.
        co2_faults.start_freeze(
            self.sensors._faults, self.sensors._fault_rng, end_time_s=self.time_s + 300.0
        )
        # This method does not overwrite the cached reading. The reading refreshes
        # on the next step through the normal read path, which applies measurement
        # noise. A direct write would either show a value with no noise or draw
        # from the noise RNG outside a step. Drawing outside a step would change
        # the simulation while it is paused.
        self.fault_status.config(text="K30 freeze active for ~5 sim minutes.")

    def _inject_scd41_drift(self) -> None:
        # Starts a drift event through the fault model, with its draw taken from
        # the fault RNG. The normal tick logic then advances and ends it.
        co2_faults.start_drift(self.sensors._faults, self.sensors._fault_rng, self.time_s)
        self.fault_status.config(text="SCD41 drift started.")

    def _trigger_dust_storm(self) -> None:
        storm = self.env.schedule_dust_storm(
            start_time_s=self.time_s + 0.05 * SOL_SECONDS,
            duration_s=2.0 * SOL_SECONDS,
            peak_tau=7.0,
        )
        self.fault_status.config(text=dust_storm_label(storm))

    # ----------------------------------------------------------- simulation

    def _commands_from_rules(self, readings: Dict[str, float]) -> Dict[str, float]:
        """Trace the rules once and build the commands from that one trace.

        The rule panels then show the same decisions that set the commands.
        """
        self.last_traces = trace_all_rule_sets(self.rule_sets, readings)
        return {key: self.last_traces[key].applied_pct for key in ACTUATOR_KEYS}

    def _commands_from_sliders(self) -> Dict[str, float]:
        return {key: float(self.manual_vars[key].get()) for key in ACTUATOR_KEYS}

    def _publish_traces(self) -> None:
        """Show each rule panel the decision that set its actuator on this step."""
        for key, panel in getattr(self, "rule_panels", {}).items():
            panel.show_trace(self.last_traces.get(key))

    def _apply_commands(self, cmds: Dict[str, float]) -> ActuatorState:
        self.actuators.set_heater(cmds["heater"])
        self.actuators.set_LED_lights(cmds["led"])
        self.actuators.inject_CO2(cmds["co2_valve"])
        self.actuators.run_irrigation_pump(cmds["pump"])
        return self.actuators.state

    def _capture_state(self) -> Dict[str, object]:
        """Save everything a step changes, so that "Back 60 s" can restore it.

        A deepcopy of the objects costs about 25 times a step, mostly in the
        three RNGs. Their getstate() tuples and shallow copies of the other
        objects cost a small fraction of that.
        """
        # Every simulation object holds plain values, RNG references, and
        # dataclasses that the step changes in place. Copy the dataclasses.
        objects = []
        for obj in (self.env, self.gh, self.sensors, self.actuators, self.plants):
            fields = {
                k: copy.copy(v) if is_dataclass(v) else v for k, v in vars(obj).items()
            }
            objects.append((obj, fields))
        rngs = (self.rng, self.sensors._rng, self.sensors._fault_rng)
        return {
            "time_s": self.time_s,
            "sol_idx": self.sol_idx,
            "objects": objects,
            "rngs": [(r, r.getstate()) for r in rngs],
            "readings": dict(self.readings),
            "actuator_state": copy.copy(self.actuator_state),
            "last_traces": dict(self.last_traces),
        }

    def _restore_state(self, saved: Dict[str, object]) -> None:
        """Return the simulation to a state saved by ``_capture_state``.

        The log rows and chart points recorded after that state are removed, so
        the saved CSV holds the same rows as a run that never stepped back.
        """
        for obj, fields in saved["objects"]:
            vars(obj).clear()
            vars(obj).update(fields)
        for rng, state in saved["rngs"]:
            rng.setstate(state)
        self.time_s = saved["time_s"]
        self.sol_idx = saved["sol_idx"]
        self.readings = saved["readings"]
        self.actuator_state = saved["actuator_state"]
        self.last_traces = saved["last_traces"]
        self._publish_traces()
        while (
            self.log
            and self.log[-1]["run"] == self.run
            and self.log[-1]["time_s"] > self.time_s
        ):
            self.log.pop()
        while self.hist_t and self.hist_t[-1] > self.time_s:
            for hist in (
                self.hist_t,
                self.hist_temp,
                self.hist_co2,
                self.hist_rh,
                self.hist_soil,
            ):
                hist.pop()
        self._rate_sim_s = self.time_s

    def _step_one(self) -> None:
        """Advance the simulation by one SIM_DT_S step."""
        # 0. Save the state before this step for "Back 60 s".
        self._undo.append(self._capture_state())
        if len(self._undo) > UNDO_MAX_STEPS:
            del self._undo[0]

        # 1. Environment.
        self.env.update(SIM_DT_S)

        # 2. Sensor faults (K30 freeze schedule).
        self.sensors.tick_faults(self.time_s, SIM_DT_S)

        # 3. Compute commands either from rules (Auto) or sliders (Manual).
        self.readings = sample_sensor_readings(self.sensors, self.env)
        if self.mode_auto.get():
            cmds = self._commands_from_rules(self.readings)
            # Mirror computed values into the slider variables so the user sees them.
            for k, v in cmds.items():
                self.manual_vars[k].set(round(v))
        else:
            cmds = self._commands_from_sliders()
            self.last_traces = {}
        self._publish_traces()

        # 4. Apply commands.
        self.actuator_state = self._apply_commands(cmds)

        # 5. Greenhouse physics. Scale photosynthesis and transpiration by plant
        # health, and set both to zero after the crop dies. The sandbox keeps
        # running after crop death. Without this step, a dead crop would still
        # take up CO2 and transpire.
        self.gh.living_biomass_factor = self.plants.health if self.plants.alive else 0.0
        self.gh.update_state(self.env, self.actuator_state, SIM_DT_S)

        # 6. Plant update.
        self.plants.update(
            temp_c=self.gh.state.temp_c,
            soil_vwc=self.gh.state.soil_vwc,
            par_umol=self.gh.state.par_umol_m2_s,
            dt_seconds=SIM_DT_S,
            current_time_s=self.time_s + SIM_DT_S,
        )

        # 7. Advance the clock and the sol counter.
        self.time_s += SIM_DT_S
        if self.time_s >= (self.sol_idx + 1) * SOL_SECONDS:
            self.sol_idx = int(self.time_s // SOL_SECONDS)

        # 8. Append history every 5 sim minutes, so the chart does not store every
        # minute.
        if not self.hist_t or self.time_s - self.hist_t[-1] >= 5 * 60.0:
            self.hist_t.append(self.time_s)
            self.hist_temp.append(self.gh.state.temp_c)
            self.hist_co2.append(self.gh.state.co2_ppm)
            self.hist_rh.append(self.gh.state.rh_pct)
            self.hist_soil.append(self.gh.state.soil_vwc)
            # Trim to the rolling window.
            cutoff = self.time_s - CHART_HISTORY_S
            while self.hist_t and self.hist_t[0] < cutoff:
                self.hist_t.pop(0)
                self.hist_temp.pop(0)
                self.hist_co2.pop(0)
                self.hist_rh.pop(0)
                self.hist_soil.pop(0)

        # 9. Record this step. Reads state already computed above; does not
        # sample any sensor or draw from any RNG.
        self._record_step()

    def _record_step(self) -> None:
        """Append one row to the run log for the step that just completed.

        The row is exactly what the window displays after this step: the
        clock, the sensor readings, the title-bar outside temperature and
        tau, the four applied actuator percentages, and the mode.
        """
        lmst = format_sim_timestamp(self.time_s).split()[2]
        mode = "AUTO" if self.mode_auto.get() else "MANUAL"
        self.log.append(
            {
                "run": self.run,
                "lmst": lmst,
                "mode": mode,
                "time_s": self.time_s,
                "sol": self.time_s / SOL_SECONDS,
                "t_out_c": self.env.get_temperature_c(),
                "tau": self.env.get_tau(),
                "t_in_c": self.readings["temperature_c"],
                "rh_pct": self.readings["rh_pct"],
                "soil_vwc": self.readings["soil_vwc"],
                "par_umol": self.readings["par_umol"],
                "heater_pct": self.actuator_state.heater_frac * 100.0,
                "led_pct": self.actuator_state.led_frac * 100.0,
                "co2_valve_pct": self.actuator_state.co2_valve_frac * 100.0,
                "pump_pct": self.actuator_state.pump_frac * 100.0,
                "co2_k30_ppm": self.readings["co2_k30_ppm"],
                "co2_scd41_ppm": self.readings["co2_scd41_ppm"],
            }
        )
        # Bound memory on long runs at the fastest speed: keep the most recent
        # LOG_MAX_ROWS rows, trimming in chunks so the trim cost is amortized.
        if len(self.log) > LOG_MAX_ROWS + LOG_TRIM_CHUNK:
            del self.log[: len(self.log) - LOG_MAX_ROWS]

    def _tick(self) -> None:
        """Outer scheduler, called every TICK_INTERVAL_MS."""
        try:
            if not self.paused.get():
                # Steps per tick = speed (sim min/wall sec) * (tick interval in sec)
                # = speed * (TICK_INTERVAL_MS / 1000)
                steps_per_tick = self.speed * (TICK_INTERVAL_MS / 1000.0)
                self._step_accumulator += steps_per_tick
                while self._step_accumulator >= 1.0:
                    self._step_one()
                    self._step_accumulator -= 1.0
                    # Stop on the first step at or past the Run to target. A
                    # Mars minute is 61.6 s, so a 60 s step always lands inside
                    # the target minute and the clock shows the target time.
                    if self._run_to_s is not None and self.time_s >= self._run_to_s:
                        self._arrive()
                        break

            self._update_clock_and_rate()

            # Update the text panel every tick (cheap).
            self._render_text()

            # Update the visual + chart every Nth tick.
            self._render_counter += 1
            if self._render_counter >= RENDER_EVERY_N:
                self._render_counter = 0
                self._render_full()
        finally:
            self.root.after(TICK_INTERVAL_MS, self._tick)

    # ---------------------------------------------------------------- render

    def _update_clock_and_rate(self) -> None:
        """Refresh the simulated clock and the measured rate. No sensor is sampled."""
        now = time.monotonic()
        wall_delta = now - self._rate_wall_s
        if wall_delta >= 1.0:
            rate = achieved_sim_rate(self.time_s - self._rate_sim_s, wall_delta)
            self._achieved_rate = 0.0 if self.paused.get() else rate
            self._rate_wall_s = now
            self._rate_sim_s = self.time_s
        if hasattr(self, "clock_label"):
            self.clock_label.config(text=format_sim_timestamp(self.time_s))
            self.rate_label.config(
                text=format_sim_rate(self.speed, self._achieved_rate)
            )

    def _render_text(self) -> None:
        t = self.readings["temperature_c"]
        rh = self.readings["rh_pct"]
        k30 = self.readings["co2_k30_ppm"]
        scd41 = self.readings["co2_scd41_ppm"]
        teros = self.readings["soil_vwc"]
        sq500 = self.readings["par_umol"]

        self.lbl_dht_t.config(text=f"DHT22 T  : {t:5.1f} C")
        self.lbl_dht_rh.config(text=f"DHT22 RH : {rh:5.1f} %")
        frozen = bool(self.sensors.co2_freeze_active)
        self.lbl_k30.config(
            text=f"K30 CO2  : {k30:6.0f} ppm" + ("  [FROZEN]" if frozen else ""),
            fg=("#c43d3d" if frozen else "black"),
        )
        self.lbl_scd41.config(text=f"SCD41    : {scd41:6.0f} ppm")
        self.lbl_dco2.config(text=f"|K30-SCD41| = {abs(k30 - scd41):4.0f} ppm")
        self.lbl_teros.config(text=f"TEROS12  : {teros:5.2f} VWC")
        self.lbl_sq500.config(text=f"SQ500    : {sq500:5.0f} umol")

        # Plant labels.
        if self.plants.alive:
            color = (
                "#2ca74a"
                if self.plants.health > 0.7
                else "#c7b22b"
                if self.plants.health > 0.3
                else "#c43d3d"
            )
            self.lbl_alive.config(text="Status : ALIVE", fg=color)
        else:
            self.lbl_alive.config(
                text=f"Status : DEAD  ({self.plants.failure_cause})",
                fg="#c43d3d",
            )
        self.lbl_health.config(text=f"Health : {self.plants.health:.2f}")

        # Stress accumulators as % of lethal duration.
        def pct(acc: float, lim: float) -> float:
            return 100.0 * acc / lim if lim > 0 else 0.0

        self.lbl_stress_tlow.config(
            text="cold     : "
            f"{pct(self.plants._temp_low_s, PLANT_LETHAL_LOW_DURATION_S):3.0f} %"
        )
        self.lbl_stress_thigh.config(
            text="heat     : "
            f"{pct(self.plants._temp_high_s, PLANT_LETHAL_HIGH_DURATION_S):3.0f} %"
        )
        self.lbl_stress_drought.config(
            text="drought  : "
            f"{pct(self.plants._drought_s, PLANT_DROUGHT_DURATION_S):3.0f} %"
        )
        self.lbl_stress_water.config(
            text="waterlog : "
            f"{pct(self.plants._waterlog_s, PLANT_WATERLOG_DURATION_S):3.0f} %"
        )
        self.lbl_stress_light.config(
            text="low_light: "
            f"{pct(self.plants._low_light_s, PLANT_LOW_LIGHT_DURATION_S):3.0f} %"
        )

    def _render_full(self) -> None:
        mode_label = "AUTO" if self.mode_auto.get() else "MANUAL"
        self.visual.update(
            env=self.env,
            gh=self.gh,
            sensors=self.sensors,
            plants=self.plants,
            actuators=self.actuator_state,
            time_s=self.time_s,
            sol_idx=self.sol_idx,
            mode_label=mode_label,
        )
        self.canvas_vis.draw_idle()

        self.chart.update(
            self.hist_t,
            self.hist_temp,
            self.hist_co2,
            self.hist_rh,
            self.hist_soil,
            latest_co2_ppm=self.gh.state.co2_ppm,
        )
        self.canvas_chart.draw_idle()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    seed: int = 42, hardware: Optional[Hardware] = None, mission: str = "m3"
) -> None:
    root = tk.Tk()
    GreenhouseSandbox(root, seed=seed, hardware=hardware, mission=mission)
    root.mainloop()


if __name__ == "__main__":
    seed_arg = 42
    if len(sys.argv) > 1:
        try:
            seed_arg = int(sys.argv[1])
        except ValueError:
            pass
    main(seed=seed_arg)
