# Martian Greenhouse Sandbox: Quick Start

This is your local practice kit for the Team Project controller. It contains the
greenhouse simulation, the interactive sandbox GUI, a controller template package, and
two practice acceptance checks, one for each milestone. Each practice check uses the
same criteria and thresholds as its graded acceptance test on one mission. Use the kit
to check your work before you submit to Gradescope.

## What Is in This Folder

| File / folder | What it is |
|---|---|
| `run_sandbox.py` | Launches the interactive sandbox GUI. |
| `martian_greenhouse_sim/` | The simulation package (physics, sensors, plants). Do not edit. |
| `student_controller_template/` | Your starting point: copy the folder, then fill in the four actuator files. |
| `practice_test_m3.py` | The Milestone 3 practice acceptance check. |
| `practice_test_m4.py` | The Milestone 4 practice acceptance check, with the sensor faults from the GHU-2 commissioning report. |
| `QUICKSTART.md` | This file. |

## Requirements

- Python 3.9 or newer
- tkinter, the GUI toolkit. It ships with the standard python.org installer on
  Windows and macOS. On Linux, install it with your package manager (for example,
  `sudo apt install python3-tk`).
- matplotlib, for the live charts (`pip install matplotlib`)

The sandbox and the practice checks need no numpy, pandas, or Gradescope packages. The
Milestone 4 analysis script reads mission logs with pandas, so install it before
Milestone 4 (`pip install pandas`).

> **Run this kit on your own computer, not in Codespaces or the cloud.** The GUI opens
> a desktop window and needs an on-screen display, which a Codespace does not have.
> Download and unzip this kit onto your own laptop.

## 1. Launch the Sandbox

Run this command from this folder, the one that contains `run_sandbox.py`.

```sh
python run_sandbox.py
```

Drag the actuator sliders and watch the sensors respond. Trigger a K30 freeze or a dust
storm from the **Faults** tab, and try to keep the plants alive. When hand-tuned rules
stop being enough, move on to writing a controller.

To see different weather, pass a seed (for example, `python run_sandbox.py 7`). To try
any glazing and heater from the hardware menu, pass them as options (for example,
`python run_sandbox.py --glazing aerogel --heater 3000`). Without those options, the
sandbox uses the hardware your team declares in `student_controller/hardware.py`. If
that file is not filled in yet, the sandbox uses the as-built hardware.

In Milestone 4, launch the sandbox with the sensor faults from the GHU-2 commissioning
report (`python run_sandbox.py --mission m4`). In that mode, the **Faults** tab can also
start an SCD41 drift.

## 2. Write Your Controller

1. Copy the whole `student_controller_template/` folder to `student_controller/` in
   this same folder.
2. Fill in the four actuator files inside it: `heater.py`, `leds.py`, `co2.py`, and
   `pump.py`. Each file holds one plain function that returns a percent from 0 to 100
   for its actuator. Each team member can own the file for their actuator.
3. Store anything your design must remember between ticks in the `state` dictionary
   that every function receives. Do not store it in a class.
4. Set `GLAZING` and `HEATER_W` in `hardware.py` to your team's hardware selection.
   The practice check and the graded test both run your controller on that hardware.

You do not need to know how classes work to do this project. The one small class the
simulator requires is already written in `__init__.py`, and you never open that file.
You also do not edit `main.py`, which connects your four functions to the simulator.

## 3. Run a Practice Acceptance Check

With your `student_controller/` package in place, run the check for your milestone from
this folder. The Milestone 4 check adds the sensor faults from the GHU-2 commissioning
report.

```sh
python practice_test_m3.py
python practice_test_m4.py
```

Each check flies one 30-sol mission (seed 42 unless you choose another, for example
`python practice_test_m4.py --seed 7`) and checks the same criteria as the graded test.

- A `student_controller/` package (or `student_controller.py`) is present.
- `student_controller/hardware.py` declares a glazing and a heater from the menu.
- The controller loads.
- The mission completes.
- No CO2 toxic event occurs.
- Plants survive at least 28 of 30 sols.
- The mean absolute temperature error is under 2.5 C.
- CO2 is in band at least 65 % of the time.
- Relative humidity is in 40 to 60 % at least 25 % of the time.
- Repeat runs are deterministic.
- Launch mass (glazing, heater, and battery) is at or under the launch-mass ceiling.

## The Graded Test Flies Several Hidden Missions

Each Gradescope acceptance test uses the same physics as its practice check. It flies
several missions that you cannot see, each with **different weather and fault timing**,
and every test must pass on every mission. A controller that hard-codes an action
sequence to the practice run will fail when it is graded. Build a controller that reacts
to its sensors, and practice on several seeds.
