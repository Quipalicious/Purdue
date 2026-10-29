"""Milestone 4 practice acceptance check for the Martian Greenhouse controller.

This runner ships inside the student sandbox zip. It uses the same criteria,
thresholds, and 30-sol mission as the Milestone 4 graded test, including the
sensor behavior reported in the GHU-2 commissioning report
(``constants.M4_SENSOR_FAULTS``). Two things differ:

    * PRACTICE  one mission, seed 42 by default (the sandbox default)
    * GRADED    several missions with seeds you cannot see; every test must
                pass on every one of them

The dust-storm onset and the timing of every sensor fault depend on the seed,
so each graded mission differs from this practice run. A controller that
hard-codes actions to the practice run will fail the graded test. Build a
controller that reacts to its sensor readings, and run this check on several
seeds of your own choosing.

The mission runs on your team's declared hardware (GLAZING and HEATER_W in
`student_controller/hardware.py`). The graded test reads the same file.

This file has no Gradescope dependencies. It runs on a plain Python install
with only what the sandbox needs. Run it from the folder that contains your
`student_controller/` package:

    python practice_test_m4.py              # seed 42
    python practice_test_m4.py --seed 7     # any other mission
"""

import sys
import unittest
from pathlib import Path

# --- Locate the martian_greenhouse_sim package -----------------------------
# This runner works inside the sandbox zip, where the package sits next to this
# file, and in the course repo, where it is in source/Part_05_Team_Project/.
# The loop adds the directory that holds the package to sys.path so
# `import martian_greenhouse_sim` resolves in both layouts.
#
# The loop checks this file's directory first, then each parent directory in
# turn. An earlier version used `_HERE.parents[2]`. From .../M4/tasks/ICA_1/a
# that is .../M4, which does not contain the package, so the import failed in
# the course repo.
_HERE = Path(__file__).resolve().parent
for _root in (_HERE, *_HERE.parents):
    if (_root / "martian_greenhouse_sim").is_dir():
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        break

from martian_greenhouse_sim.constants import (  # noqa: E402
    LAUNCH_MASS_CEILING_KG,
    M4_SENSOR_FAULTS,
)
from martian_greenhouse_sim.hardware import Hardware  # noqa: E402
from martian_greenhouse_sim.simulation import (  # noqa: E402
    SimulationResult,
    load_student_controller,
    load_student_hardware,
    run_simulation,
)

# --- PRACTICE configuration -------------------------------------------------
# The default practice seed matches the sandbox default (run_sandbox.py and the
# GUI). Pass --seed N to fly a different mission. The graded test flies several
# missions with seeds you cannot see. The physics are the same. The weather and
# fault timing are different.
PRACTICE_SEED = 42
DAYS = 30
MISSION_FAULTS = M4_SENSOR_FAULTS  # Milestone 4 sensor faults

_ASSIGNMENT_DIR = _HERE  # your student_controller/ package sits next to this file


def _load_controller():
    """Locate your student_controller/ package next to this runner."""
    return load_student_controller(search_dirs=[str(_ASSIGNMENT_DIR)])


def _load_hardware() -> Hardware:
    """Your declared hardware, or the default if missing or invalid."""
    try:
        return load_student_hardware(search_dirs=[str(_ASSIGNMENT_DIR)]) or Hardware()
    except ValueError:
        return Hardware()


def _run_with_student() -> SimulationResult:
    """Run the 30-sol practice mission with your controller and hardware."""
    return run_simulation(
        days=DAYS,
        seed=PRACTICE_SEED,
        controller_cls=_load_controller(),
        hardware=_load_hardware(),
        sensor_overrides=MISSION_FAULTS,
    )


class TestHardware(unittest.TestCase):
    """Verify your team declared a hardware selection from the menu."""

    def test_05_hardware_declared(self):
        """student_controller/hardware.py must declare GLAZING and HEATER_W.

        Both must name options on the hardware menu.
        """
        try:
            hardware = load_student_hardware(search_dirs=[str(_ASSIGNMENT_DIR)])
        except ValueError as exc:
            self.fail(f"{exc} The mission ran on the default hardware instead.")
        if hardware is None:
            self.fail(
                "No hardware declaration found. Set GLAZING and HEATER_W in "
                "student_controller/hardware.py. The mission ran on the default "
                "hardware (twin_wall, 2000 W) instead."
            )


class TestFilePresence(unittest.TestCase):
    """Verify your submission file is on disk."""

    def test_00_student_controller_present(self):
        """student_controller.py (or student_controller/) must exist here."""
        single_file = _ASSIGNMENT_DIR / "student_controller.py"
        package_dir = _ASSIGNMENT_DIR / "student_controller"
        package_init = package_dir / "__init__.py"
        found = single_file.is_file() or (package_dir.is_dir() and package_init.is_file())
        self.assertTrue(
            found,
            "No submission found. Copy the student_controller_template/ folder "
            f"to student_controller/ in {_ASSIGNMENT_DIR} and edit its actuator "
            "files.",
        )


class TestDesignProject(unittest.TestCase):
    """Same performance criteria as the graded acceptance test, on one mission."""

    _result: "SimulationResult | None" = None

    @classmethod
    def _result_cached(cls) -> SimulationResult:
        if cls._result is None:
            cls._result = _run_with_student()
        return cls._result

    def test_10_loads_controller(self):
        """GreenhouseController must load without raising."""
        cls = _load_controller()
        self.assertTrue(callable(cls), "load_student_controller returned a non-callable")
        instance = cls()
        self.assertTrue(
            hasattr(instance, "update"),
            "GreenhouseController must define an update() method",
        )

    def test_20_simulation_completes(self):
        """The 30-sol simulation must run end-to-end without exception."""
        result = self._result_cached()
        self.assertIsInstance(result, SimulationResult)
        self.assertGreater(result.total_steps, 0, "Simulation reported zero total steps")

    def test_30_no_toxic_co2_event(self):
        """The controller must not cause a CO2 toxicity event."""
        result = self._result_cached()
        self.assertFalse(
            result.co2_toxic_event,
            "CO2 toxic event detected: CO2 reached the crew toxicity limit. "
            f"toxic_duration_s={result.co2_toxic_duration_s:.0f}",
        )

    def test_40_sols_survived(self):
        """Plants must survive at least 28 of 30 sols."""
        result = self._result_cached()
        report = result.failure_report() if result.terminated_early else "(no failure)"
        self.assertGreaterEqual(
            result.sols_survived,
            28.0,
            f"Plants died too early: sols_survived={result.sols_survived:.2f}. {report}",
        )

    def test_50_temp_control(self):
        """Mean absolute temperature error must be below 2.5 C."""
        result = self._result_cached()
        self.assertLess(
            result.mean_temp_error_c,
            2.5,
            f"Mean temperature error too high: {result.mean_temp_error_c:.2f} C >= 2.5",
        )

    def test_60_co2_in_range(self):
        """CO2 must be in [800, 1000] ppm at least 65 % of the time."""
        result = self._result_cached()
        self.assertGreaterEqual(
            result.co2_in_range_fraction,
            0.65,
            f"CO2 in range only {result.co2_in_range_fraction:.1%} (need >= 65 %)",
        )

    def test_70_rh_in_range(self):
        """RH must be inside [40, 60] % on at least 25 % of ticks."""
        result = self._result_cached()
        self.assertGreaterEqual(
            result.rh_in_range_fraction,
            0.25,
            f"RH in range only {result.rh_in_range_fraction:.1%} (need >= 25 %)",
        )

    def test_80_deterministic(self):
        """Repeating the mission must reproduce its headline metrics exactly.

        Checks the same fields, to the same precision, as the graded test.
        """
        first = self._result_cached()
        second = _run_with_student()
        for name in (
            "mean_temp_error_c",
            "sols_survived",
            "co2_in_range_fraction",
            "rh_in_range_fraction",
            "launch_mass_kg",
        ):
            self.assertAlmostEqual(
                getattr(first, name),
                getattr(second, name),
                places=6,
                msg=f"Repeated runs of the same mission produced different {name}",
            )
        self.assertEqual(
            first.co2_toxic_event,
            second.co2_toxic_event,
            msg="Repeated runs of the same mission disagreed on co2_toxic_event",
        )

    def test_90_launch_mass(self):
        """Launch mass (glazing + heater + battery) must not exceed the ceiling.

        Assessed only for a mission the crop survives: a controller that lets the
        crop die early draws little energy, and its battery would look small.
        """
        result = self._result_cached()
        self.assertGreaterEqual(
            result.sols_survived,
            28.0,
            "Launch mass is assessed only for a mission the crop survives "
            f"(at least 28 sols); this run ended at sol {result.sols_survived:.2f}.",
        )
        hardware = Hardware(result.glazing, result.heater_w)
        breakdown = (
            f"{result.glazing} glazing {hardware.glazing_mass_kg:.0f} kg + "
            f"{result.heater_w} W heater {hardware.heater_mass_kg:.0f} kg + "
            f"battery {result.battery_mass_kg:.0f} kg "
            f"(worst sol {result.worst_sol_energy_kwh:.1f} kWh) = "
            f"{result.launch_mass_kg:.0f} kg"
        )
        print(f"\nLaunch mass: {breakdown}")
        self.assertLessEqual(
            result.launch_mass_kg,
            LAUNCH_MASS_CEILING_KG,
            f"Launch mass over the {LAUNCH_MASS_CEILING_KG:.0f} kg ceiling: {breakdown}",
        )


def _take_seed_argument(argv):
    """Remove an optional ``--seed N`` from argv and apply it.

    unittest.main parses the rest of the command line, so the seed is taken
    out before it sees the arguments.
    """
    global PRACTICE_SEED
    if "--seed" in argv:
        i = argv.index("--seed")
        if i + 1 >= len(argv):
            raise SystemExit("--seed needs a whole number, for example --seed 7")
        try:
            PRACTICE_SEED = int(argv[i + 1])
        except ValueError:
            raise SystemExit("--seed needs a whole number, for example --seed 7")
        del argv[i : i + 2]
    print(f"Practice mission seed: {PRACTICE_SEED}")


if __name__ == "__main__":
    _take_seed_argument(sys.argv)
    unittest.main(verbosity=2)
