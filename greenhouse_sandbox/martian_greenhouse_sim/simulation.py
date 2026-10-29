"""
Main simulation loop for the Martian greenhouse stress test.

The simulation runs for a configurable number of Martian sols at a fixed
time step (default 60 s).  Each run:

  1. Models external Martian conditions (diurnal temperature + solar).
  2. Schedules **one global dust storm** (2 to 5 sols long, random start) to
     test whether the student controller responds to the sudden loss of
     solar heat and light.
  3. Injects K30 CO2 sensor freezes at random.  The SCD41 drift fault and
     the Milestone 4 freeze model are opt-in (``constants.M4_SENSOR_FAULTS``).
  4. Scores plant survival and reports environmental diagnostics.

Usage
-----
Run as a script to execute a 30-sol simulation with the stub controller::

    python -m martian_greenhouse_sim.simulation

Or import and call programmatically::

    from martian_greenhouse_sim.simulation import run_simulation
    from martian_greenhouse_sim.controllers import StudentPIDController

    result = run_simulation(days=30, seed=42)
    print(result.summary())

    # Optional: dump per-step data to CSV
    with open("sim_log.csv", "w") as f:
        f.write(result.to_csv())   # requires log_records=True
"""

import csv
import importlib
import importlib.util
import io
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .actuators import VirtualActuators
from .constants import (
    CO2_TOXIC_DURATION_S,
    CO2_TOXIC_PPM,
    DEFAULT_DT_S,
    DEFAULT_SEED,
    LED_MAX_POWER_W,
    LETTUCE_CO2_HIGH_PPM,
    LETTUCE_CO2_LOW_PPM,
    LETTUCE_CO2_SETPOINT_PPM,
    LETTUCE_RH_HIGH_PCT,
    LETTUCE_RH_LOW_PCT,
    LETTUCE_RH_SETPOINT_PCT,
    LETTUCE_TEMP_DAY_C,
    LETTUCE_TEMP_NIGHT_C,
    LETTUCE_VWC_SETPOINT,
    MISSION_K30_FREEZE_DURATION_RANGE_S,
    MISSION_K30_FREEZE_PROB_PER_STEP,
    SCORING_MAX_POINTS,
    SCORING_TARGET_SOLS,
    SOL_SECONDS,
)
from .controllers import (
    ActuatorCommands,
    SensorReadings,
    Setpoints,
    StudentPIDController,
)
from .environment import MarsEnvironment
from .greenhouse import Greenhouse
from .hardware import Hardware, battery_mass_kg
from .plants import PlantCohort
from .sensors import VirtualSensors

# ---------------------------------------------------------------------------
# Per-step log record
# ---------------------------------------------------------------------------


@dataclass
class SimulationRecord:
    """One row of the per-step simulation log (populated when log_records=True)."""

    time_s: float
    interval_start_s: float
    interval_end_s: float
    sol: float
    t_out_c: float
    tau: float
    t_in_c: float
    rh_pct: float
    co2_ppm: float
    soil_vwc: float
    par_umol: float
    heater_pct: float
    led_pct: float
    co2_valve_pct: float
    pump_pct: float
    co2_k30_reading: float
    co2_scd41_reading: float
    co2_freeze_active: bool
    dust_storm_active: bool
    electrical_w: float = 0.0  #: Heater + LED electrical draw over the interval (W)
    scd41_drift_active: bool = False  #: True while the SCD41 backup is drifting


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    """
    Performance summary returned by :func:`run_simulation`.

    Attributes
    ----------
    mean_temp_error_c : float
        Mean absolute error between the internal temperature and the active
        setpoint (23 deg C day / 18 deg C night), averaged over all time steps.
    co2_in_range_fraction : float
        Fraction of time steps in which CO2 was within [800, 1 000] ppm.
    rh_in_range_fraction : float
        Fraction of time steps in which RH was within [40, 60] %.  RH does
        not affect plant survival or the survival score; the acceptance test
        checks this fraction separately.
    co2_toxic_event : bool
        True if CO2 was at or above 5 000 ppm for 30 or more continuous
        minutes.
    co2_toxic_duration_s : float
        Total, not necessarily consecutive, seconds that CO2 was at or above
        5 000 ppm.
    glazing, heater_w :
        The hardware selection the mission ran with.
    worst_sol_energy_kwh : float
        Electrical energy (heater + LEDs) drawn in the most demanding sol.
        Complete sols only, unless the run ended before the first sol closed.
    mission_energy_kwh : float
        Electrical energy drawn over the whole run.
    battery_mass_kg : float
        Battery mass needed to carry the worst sol with the arrays dark.
    launch_mass_kg : float
        Configurable launch mass: glazing + heater + battery.
    records : list of SimulationRecord
        Per-step log (empty unless ``log_records=True`` was passed to
        :func:`run_simulation`).
    """

    days: int
    dt_seconds: float
    seed: int
    total_steps: int
    steps_run: int = 0

    mean_temp_error_c: float = 0.0
    co2_in_range_fraction: float = 0.0
    rh_in_range_fraction: float = 0.0
    co2_toxic_event: bool = False
    co2_toxic_duration_s: float = 0.0

    # Plant cohort results
    terminated_early: bool = False
    failure_sol: Optional[float] = None
    failure_cause: Optional[str] = None
    failure_snapshot: Optional[Dict[str, Any]] = None
    plant_health: float = 1.0
    sols_survived: float = 0.0

    # Hardware and power system
    glazing: str = ""
    heater_w: int = 0
    worst_sol_energy_kwh: float = 0.0
    mission_energy_kwh: float = 0.0
    battery_mass_kg: float = 0.0
    launch_mass_kg: float = 0.0

    records: List[SimulationRecord] = field(default_factory=list)

    def plant_survival_score(self, max_points: float = SCORING_MAX_POINTS) -> float:
        """Return the survival-only score; RH does not affect it."""
        return round(max_points * min(self.sols_survived / SCORING_TARGET_SOLS, 1.0), 3)

    def failure_report(self) -> str:
        """Return a concise, student-readable failure report (fits in one screen)."""
        if not self.terminated_early:
            return (
                f"Plants survived the full {self.days}-sol mission.\n"
                f"Sols survived : {self.sols_survived:.2f} / {float(self.days):.2f}"
            )
        lines = [
            "PLANT COHORT FAILURE",
            f"  Survived      : {self.sols_survived:.2f} / {float(self.days):.2f} sols",
            f"  Cause         : {self.failure_cause}",
            f"  Failed at sol : {self.failure_sol:.3f}",
        ]
        if self.failure_snapshot:
            snap = self.failure_snapshot
            (lines.append("  Last readings :"),)
            lines.append(
                f"    T_in={snap.get('t_in_c', 0):.1f} deg C  "
                f"VWC={snap.get('soil_vwc', 0):.3f}  "
                f"PAR={snap.get('par_umol', 0):.0f} umol/m^2/s"
            )
            lines.append("  Last commands :")
            lines.append(
                f"    heater={snap.get('heater_pct', 0):.0f}%  "
                f"LED={snap.get('led_pct', 0):.0f}%  "
                f"pump={snap.get('pump_pct', 0):.0f}%"
            )
        lines.append("")
        cause_hint = {
            "TEMP_LETHAL_LOW": (
                "Hint: internal temperature dropped below 5 deg C for over 2 hours."
            ),
            "TEMP_LETHAL_HIGH": (
                "Hint: internal temperature exceeded 40 deg C for over 1 hour."
            ),
            "SOIL_DROUGHT": "Hint: soil VWC stayed below 0.10 for over 1 sol.",
            "SOIL_WATERLOG": "Hint: soil VWC stayed above 0.70 for over 0.5 sol.",
            "LIGHT_INSUFFICIENT": (
                "Hint: PAR accumulated below 150 umol/m^2/s for over 2 "
                "cumulative sols. "
                "Check LED compensation during dust storms."
            ),
        }
        lines.append(cause_hint.get(self.failure_cause, ""))
        return "\n".join(lines)

    def to_gradescope_json(self, output_path: Optional[str] = None) -> dict:
        """
        Return (and optionally write) a Gradescope-compatible summary dict.

        The dict is suitable for ``plant_report.json`` which ``grader/post.py``
        reads to inject a partial-credit plant-survival score.
        """
        data = {
            "sols_survived": self.sols_survived,
            "target_sols": float(self.days),
            "terminated_early": self.terminated_early,
            "failure_cause": self.failure_cause,
            "failure_sol": self.failure_sol,
            "plant_health": self.plant_health,
            "failure_report": self.failure_report(),
        }
        if output_path is not None:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        return data

    def summary(self) -> str:
        """Return a human-readable performance summary string."""
        lines = [
            f"{'=' * 60}",
            f"  Martian Greenhouse Simulation -- {self.days}-sol run",
            f"  dt = {self.dt_seconds:.0f} s  |  seed = {self.seed}",
            f"{'=' * 60}",
            f"  Temperature MAE        : {self.mean_temp_error_c:.2f} deg C",
            f"  CO2 in range           : {self.co2_in_range_fraction:.1%}  "
            f"[target {LETTUCE_CO2_LOW_PPM:.0f} to {LETTUCE_CO2_HIGH_PPM:.0f} ppm]",
            f"  RH in range            : {self.rh_in_range_fraction:.1%}  "
            f"[target {LETTUCE_RH_LOW_PCT:.0f} to {LETTUCE_RH_HIGH_PCT:.0f} %]",
        ]
        if self.co2_toxic_event:
            lines.append(
                f"  CO2 safety             : FAIL -- {self.co2_toxic_duration_s:.0f} s "
                f"at or above {CO2_TOXIC_PPM:.0f} ppm"
            )
        else:
            lines.append("  CO2 safety             : PASS")
        lines.append(
            f"  Hardware               : {self.glazing}, {self.heater_w} W heater"
        )
        lines.append(
            f"  Worst-sol energy       : {self.worst_sol_energy_kwh:.1f} kWh  "
            f"(battery {self.battery_mass_kg:.0f} kg)"
        )
        lines.append(f"  Launch mass            : {self.launch_mass_kg:.0f} kg")
        lines.append("")
        lines.append(self.failure_report())
        lines.append(f"{'=' * 60}")
        return "\n".join(lines)

    def to_csv(self) -> str:
        """
        Serialise per-step records to a CSV string.

        Returns an empty string if ``run_simulation`` was called with
        ``log_records=False`` (the default).
        """
        if not self.records:
            return ""
        buf = io.StringIO()
        fieldnames = list(asdict(self.records[0]).keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for record in self.records:
            writer.writerow(asdict(record))
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build_setpoints(env: MarsEnvironment) -> Setpoints:
    """Return the current Lettuce setpoints based on the diurnal phase."""
    is_day = env.is_daytime()
    return Setpoints(
        temperature_c=LETTUCE_TEMP_DAY_C if is_day else LETTUCE_TEMP_NIGHT_C,
        co2_ppm=LETTUCE_CO2_SETPOINT_PPM,
        rh_pct=LETTUCE_RH_SETPOINT_PCT,
        soil_vwc=LETTUCE_VWC_SETPOINT,
        is_daytime=is_day,
    )


# ---------------------------------------------------------------------------
# Main simulation loop
# ---------------------------------------------------------------------------


def run_simulation(
    days: int = 30,
    dt_seconds: float = DEFAULT_DT_S,
    seed: int = DEFAULT_SEED,
    controller_cls: Type = StudentPIDController,
    log_records: bool = False,
    sensor_overrides: Optional[dict] = None,
    hardware: Optional[Hardware] = None,
) -> SimulationResult:
    """
    Run the Martian greenhouse stress-test simulation.

    Stress events
    -------------
    **Global dust storm.**  A single dust storm is injected at a random sol
    between 2 and ``days - 5``.  Its duration is 2 to 5 sols and its peak Tau
    is drawn from [5.0, 8.5], reducing solar irradiance by about 55 to 97 %.
    Student controllers must ramp up the heater to compensate.

    **K30 CO2 sensor freeze.**  The K30 freezes at random during the mission
    (``MISSION_K30_FREEZE_PROB_PER_STEP``, each freeze lasting 30 min to 6 h),
    reporting a stuck value while it is frozen.
    The SCD41 drift fault stays off unless ``sensor_overrides`` enables it.

    Parameters
    ----------
    days : int
        Simulation duration in Martian sols (default 30).
    dt_seconds : float
        Time step in seconds (default 60 s).
    seed : int
        RNG seed for reproducible storm scheduling, sensor noise, and fault
        injection (default 42).
    controller_cls : type
        Student controller class.  Must expose an
        ``update(readings, setpoints, dt) -> ActuatorCommands`` method.
    log_records : bool
        If True, populate ``SimulationResult.records`` with a per-step log.
        Useful for plotting and debugging; adds memory overhead for long runs.
    sensor_overrides : dict, optional
        Extra keyword arguments forwarded to :class:`VirtualSensors`
        (e.g. ``{"freeze_prob_per_step": 6e-4}``), applied on top of the
        mission freeze profile.  ``None`` (the default) runs the standard
        mission configuration exactly.  The Milestone 4 practice and
        acceptance tests pass ``constants.M4_SENSOR_FAULTS`` here, and
        instructional tooling such as the telemetry-log generators also uses
        this option.
    hardware : Hardware, optional
        The team's glazing and heater selection.  ``None`` (the default) runs
        the twin-wall glazing with the 2000 W heater.

    Returns
    -------
    SimulationResult
        Performance summary and optional step-by-step log.
    """
    if not math.isfinite(days) or days <= 0.0:
        raise ValueError(f"days must be finite and greater than zero; got {days!r}")
    if not math.isfinite(dt_seconds) or dt_seconds <= 0.0:
        raise ValueError(
            "dt_seconds must be a finite, positive time step; "
            f"got {dt_seconds!r}"
        )

    total_sim_s = days * SOL_SECONDS
    total_steps = int(total_sim_s / dt_seconds)
    if total_steps < 1:
        raise ValueError(
            "dt_seconds must not exceed the mission duration; "
            f"got {dt_seconds!r} s for a {total_sim_s!r} s mission"
        )

    # Separate seeds so storm schedule and sensor noise are independent
    env_rng = random.Random(seed)
    sensor_rng = random.Random(seed + 1)

    # --- Initialise subsystems ---
    hardware = hardware or Hardware()
    glazing = hardware.glazing_spec
    env = MarsEnvironment(rng=env_rng)
    greenhouse = Greenhouse(
        u_value=glazing.u_value_w_m2_k, transmittance=glazing.transmittance
    )
    actuators = VirtualActuators(heater_max_w=hardware.heater_w)
    sensor_kwargs = {
        "freeze_prob_per_step": MISSION_K30_FREEZE_PROB_PER_STEP,
        "freeze_duration_range_s": MISSION_K30_FREEZE_DURATION_RANGE_S,
    }
    sensor_kwargs.update(sensor_overrides or {})
    sensors = VirtualSensors(greenhouse, rng=sensor_rng, **sensor_kwargs)
    controller = controller_cls()

    # --- Schedule one guaranteed global dust storm ---
    # Storm starts at a random sol in [2, days-5] (clamped so it fits)
    storm_start_sol = env_rng.uniform(2.0, max(3.0, float(days) - 5.0))
    storm_duration_sol = env_rng.uniform(2.0, 5.0)
    storm = env.schedule_dust_storm(
        start_time_s=storm_start_sol * SOL_SECONDS,
        duration_s=storm_duration_sol * SOL_SECONDS,
    )

    # --- Initialise plant cohort ---
    plants = PlantCohort()

    # --- Evaluation accumulators ---
    temp_error_sum = 0.0
    co2_in_range_count = 0
    rh_in_range_count = 0
    co2_toxic_total_s = 0.0
    co2_toxic_consecutive_s = 0.0
    co2_toxic_event = False
    sol_energy_j: Dict[int, float] = {}  # sol index -> electrical energy (J)
    records: List[SimulationRecord] = []
    steps_run = 0

    # Snapshot of the last tick's conditions (used in failure report)
    last_snapshot: Dict[str, Any] = {}

    for _step in range(total_steps):
        steps_run += 1
        current_time_s = env.get_time_s()
        interval_end_s = current_time_s + dt_seconds
        state_at_start = greenhouse.get_state()
        t_out_at_start = env.get_temperature_c()
        tau_at_start = env.get_tau()
        dust_active_at_start = (
            storm.start_time_s <= current_time_s < storm.end_time_s
        )

        # 1. Advance fault state (must happen before reading sensors)
        sensors.tick_faults(current_time_s, dt_seconds)

        # 2. Read sensors
        temp_reading, rh_reading = sensors.read_DHT22()
        co2_k30 = sensors.read_K30()  # primary; it may freeze at a stuck value
        co2_scd41 = sensors.read_SCD41()  # backup CO2 sensor
        vwc_reading = sensors.read_TEROS12()
        par_reading = sensors.read_SQ500()

        # 3. Build controller inputs
        readings = SensorReadings(
            temperature_c=temp_reading,
            rh_pct=rh_reading,
            co2_ppm_primary=co2_k30,
            co2_ppm_backup=co2_scd41,
            soil_vwc=vwc_reading,
            par_umol_m2_s=par_reading,
        )
        setpoints = _build_setpoints(env)

        # 4. Student controller step
        commands: ActuatorCommands = controller.update(readings, setpoints, dt_seconds)

        # 5. Apply actuator commands (VirtualActuators clamps to [0, 100])
        actuators.set_heater(commands.heater_pct)
        actuators.set_LED_lights(commands.led_pct)
        actuators.inject_CO2(commands.co2_valve_pct)
        actuators.run_irrigation_pump(commands.pump_pct)
        electrical_w = (
            actuators.state.heater_watts + actuators.state.led_frac * LED_MAX_POWER_W
        )
        sol_index = int(current_time_s // SOL_SECONDS)
        sol_energy_j[sol_index] = (
            sol_energy_j.get(sol_index, 0.0) + electrical_w * dt_seconds
        )

        # 6. Advance physics (environment first, then greenhouse).
        # Gate photosynthesis and transpiration on the living crop: a dead
        # cohort must not keep fixing CO2 or transpiring. Early termination
        # usually hides this here. The acceptance run must not depend on early
        # termination, and the sandbox keeps running after the crop dies.
        greenhouse.living_biomass_factor = plants.health if plants.alive else 0.0
        env.update(dt_seconds)
        state = greenhouse.update_state(env, actuators.state, dt_seconds)

        # 7. Score against Lettuce targets
        temp_error_sum += abs(state.temp_c - setpoints.temperature_c)

        if LETTUCE_CO2_LOW_PPM <= state.co2_ppm <= LETTUCE_CO2_HIGH_PPM:
            co2_in_range_count += 1
        if LETTUCE_RH_LOW_PCT <= state.rh_pct <= LETTUCE_RH_HIGH_PCT:
            rh_in_range_count += 1
        if state.co2_ppm >= CO2_TOXIC_PPM:
            co2_toxic_total_s += dt_seconds
            co2_toxic_consecutive_s += dt_seconds
            if co2_toxic_consecutive_s >= CO2_TOXIC_DURATION_S:
                co2_toxic_event = True
        else:
            co2_toxic_consecutive_s = 0.0

        # 8. Update plant cohort
        plants.update(
            temp_c=state.temp_c,
            soil_vwc=state.soil_vwc,
            par_umol=state.par_umol_m2_s,
            dt_seconds=dt_seconds,
            current_time_s=interval_end_s,
        )
        last_snapshot = {
            "t_in_c": state.temp_c,
            "soil_vwc": state.soil_vwc,
            "par_umol": state.par_umol_m2_s,
            "heater_pct": commands.heater_pct,
            "led_pct": commands.led_pct,
            "co2_valve_pct": commands.co2_valve_pct,
            "pump_pct": commands.pump_pct,
        }

        # 9. Optional per-step logging (includes the death step when terminated)
        if log_records:
            records.append(
                SimulationRecord(
                    time_s=current_time_s,
                    interval_start_s=current_time_s,
                    interval_end_s=interval_end_s,
                    sol=current_time_s / SOL_SECONDS,
                    t_out_c=t_out_at_start,
                    tau=tau_at_start,
                    t_in_c=state_at_start.temp_c,
                    rh_pct=state_at_start.rh_pct,
                    co2_ppm=state_at_start.co2_ppm,
                    soil_vwc=state_at_start.soil_vwc,
                    par_umol=state_at_start.par_umol_m2_s,
                    heater_pct=commands.heater_pct,
                    led_pct=commands.led_pct,
                    co2_valve_pct=commands.co2_valve_pct,
                    pump_pct=commands.pump_pct,
                    co2_k30_reading=co2_k30,
                    co2_scd41_reading=co2_scd41,
                    co2_freeze_active=sensors.co2_freeze_active,
                    dust_storm_active=dust_active_at_start,
                    electrical_w=electrical_w,
                    scd41_drift_active=sensors.scd41_drift_active,
                )
            )

        # 10. Early-stop check (after logging so death step is included)
        if not plants.alive:
            break

    denom = steps_run if steps_run > 0 else 1
    sols_survived = (steps_run * dt_seconds) / SOL_SECONDS

    # Battery sizing: the most demanding complete sol (a partial final sol
    # would understate it), falling back to partial sols for very short runs.
    complete = [e for k, e in sol_energy_j.items() if k + 1 <= int(sols_survived)]
    worst_sol_kwh = max(complete or list(sol_energy_j.values()) or [0.0]) / 3.6e6

    return SimulationResult(
        days=days,
        dt_seconds=dt_seconds,
        seed=seed,
        total_steps=total_steps,
        steps_run=steps_run,
        mean_temp_error_c=temp_error_sum / denom,
        co2_in_range_fraction=co2_in_range_count / denom,
        rh_in_range_fraction=rh_in_range_count / denom,
        co2_toxic_event=co2_toxic_event,
        co2_toxic_duration_s=co2_toxic_total_s,
        terminated_early=not plants.alive,
        failure_sol=plants.failure_sol,
        failure_cause=plants.failure_cause,
        failure_snapshot=last_snapshot if not plants.alive else None,
        plant_health=plants.health,
        sols_survived=sols_survived,
        glazing=hardware.glazing,
        heater_w=hardware.heater_w,
        worst_sol_energy_kwh=worst_sol_kwh,
        mission_energy_kwh=sum(sol_energy_j.values()) / 3.6e6,
        battery_mass_kg=battery_mass_kg(worst_sol_kwh),
        launch_mass_kg=hardware.launch_mass_kg(worst_sol_kwh),
        records=records,
    )


# ---------------------------------------------------------------------------
# Student submission loader
# ---------------------------------------------------------------------------


def load_student_controller(search_dirs: Optional[List[str]] = None) -> Type:
    """
    Locate and load the student's controller class from their submission.

    The function searches for either:

    * ``student_controller.py``: a single-file submission, or
    * ``student_controller/``: a package directory containing
      ``__init__.py`` (which must re-export ``GreenhouseController``).

    In both cases the module must define a class named
    ``GreenhouseController`` with an ``update(readings, setpoints, dt)``
    method whose signature matches :class:`~.controllers.StudentPIDController`.

    Parameters
    ----------
    search_dirs : list of str, optional
        Directories to search (in order).  The current working directory is
        always appended as a final fallback.

    Returns
    -------
    type
        The ``GreenhouseController`` class found in the student's module.

    Raises
    ------
    FileNotFoundError
        If no submission is found in any of the searched directories.
    AttributeError
        If the located module does not define ``GreenhouseController``.
    """
    importlib.invalidate_caches()
    stale_modules = [
        name
        for name in sys.modules
        if name == "student_controller" or name.startswith("student_controller.")
    ]
    for name in stale_modules:
        del sys.modules[name]

    dirs_to_try: List[Path] = []
    if search_dirs:
        dirs_to_try.extend(Path(d) for d in search_dirs)
    dirs_to_try.append(Path.cwd())

    for directory in dirs_to_try:
        # Option A: single file
        single_file = directory / "student_controller.py"
        if single_file.is_file():
            spec = importlib.util.spec_from_file_location(  # type: ignore[attr-defined]
                "student_controller", single_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
                sys.modules["student_controller"] = module
                spec.loader.exec_module(module)
                return getattr(module, "GreenhouseController")

        # Option B: package directory
        pkg_dir = directory / "student_controller"
        if pkg_dir.is_dir() and (pkg_dir / "__init__.py").is_file():
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
            module = importlib.import_module("student_controller")
            return getattr(module, "GreenhouseController")

    searched = ", ".join(str(d) for d in dirs_to_try)
    raise FileNotFoundError(
        "No student_controller.py or student_controller/ package found. "
        f"Searched: {searched}"
    )

def load_student_hardware(
    search_dirs: Optional[List[str]] = None,
) -> Optional[Hardware]:
    """
    Read the team's hardware selection from its submission.

    Looks for ``student_controller/hardware.py`` (package submissions) or
    module-level ``GLAZING`` and ``HEATER_W`` in ``student_controller.py``
    (single-file submissions), in the same directories as
    :func:`load_student_controller`.

    Returns
    -------
    Hardware or None
        The declared selection, or ``None`` if no declaration was found.

    Raises
    ------
    ValueError
        If a declaration exists but names hardware that is not on the menu.
    """
    dirs_to_try: List[Path] = [Path(d) for d in (search_dirs or [])]
    dirs_to_try.append(Path.cwd())

    for directory in dirs_to_try:
        candidates = [
            directory / "student_controller" / "hardware.py",
            directory / "student_controller.py",
        ]
        for path in candidates:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location(  # type: ignore[attr-defined]
                f"_student_hardware_{abs(hash(str(path)))}", path
            )
            if not (spec and spec.loader):
                continue
            module = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
            spec.loader.exec_module(module)
            glazing = getattr(module, "GLAZING", None)
            heater_w = getattr(module, "HEATER_W", None)
            if glazing is None and heater_w is None:
                continue  # template left unfilled: not declared
            if glazing is None or heater_w is None:
                raise ValueError(
                    f"{path.name} declares only one of GLAZING and HEATER_W; "
                    "set both."
                )
            return Hardware(glazing=glazing, heater_w=heater_w)
    return None


if __name__ == "__main__":
    print("Running 30-sol Martian greenhouse stress test (stub controller)...")
    result = run_simulation(days=30, seed=DEFAULT_SEED)
    print(result.summary())
