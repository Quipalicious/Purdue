# GIVEN FILE: DO NOT EDIT.
#
# This file calls your four actuator functions and gives the simulator one
# ActuatorCommands result per tick. Do not change anything here.
# Do your engineering work in heater.py, leds.py, co2.py, and pump.py.

from .heater import control_heater
from .leds import control_leds
from .co2 import control_co2
from .pump import control_pump

from martian_greenhouse_sim.controllers import ActuatorCommands


def control_all(readings, setpoints, dt, state) -> ActuatorCommands:
    """Call the four actuator functions and assemble one command bundle.

    Parameters
    ----------
    readings : SensorReadings
        The current sensor values for this tick.
    setpoints : Setpoints
        The current target conditions for this tick.
    dt : float
        The length of this tick in seconds (60 by default).
    state : dict
        A plain dictionary the four functions share to remember values between
        ticks. Each file starts its keys with its own name (for example,
        "heater_total") so no two files overwrite each other's values.

    Returns
    -------
    ActuatorCommands
        heater_pct, led_pct, co2_valve_pct, pump_pct, each in [0, 100].
    """
    return ActuatorCommands(
        heater_pct=control_heater(readings, setpoints, dt, state),
        led_pct=control_leds(readings, setpoints, dt, state),
        co2_valve_pct=control_co2(readings, setpoints, dt, state),
        pump_pct=control_pump(readings, setpoints, dt, state),
    )
