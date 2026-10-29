# GIVEN FILE: DO NOT EDIT.
#
# You do not need to know about classes for this project. This file is the only
# place in your submission that uses a class, and it is written for you. The
# grading simulator needs one "GreenhouseController" object from each team, and
# this file provides it. Do your engineering work in the functions in heater.py,
# leds.py, co2.py, and pump.py. The other files do not use classes.

from .main import control_all


class GreenhouseController:
    """Adapter the simulator builds once and then calls every tick.

    It holds one plain dictionary of memory (self._state) and passes each
    tick to the control_all function in main.py. Do not edit this class.
    """

    def __init__(self):
        self._state = {}

    def update(self, readings, setpoints, dt_seconds):
        return control_all(readings, setpoints, dt_seconds, self._state)
