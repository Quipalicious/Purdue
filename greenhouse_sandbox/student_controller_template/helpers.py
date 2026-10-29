"""Team information and a shared helper for the GHU-2 controller.

Course      : ENGR 13100
Assignment  : Team Project M4: Controller Implementation
Team ID     : <team>
Author(s)   : <names>
Actuator owners: heater <name> / LEDs <name> / CO2 valve <name> / pump <name>
Contributors: <anyone else who helped, including AI tools per your AI Use Log>

Academic Integrity Statement:
    I/we have not used source code obtained from any other unauthorized
    source, either modified or unmodified. Any AI assistance complied with
    the project AI Usage Policy and is documented in our AI Use Log.

Fill in the fields above. Every team member edits the actuator file they own
(heater.py, leds.py, co2.py, pump.py). The _clamp helper below keeps any
command inside the legal actuator range, and every actuator file may use it.
"""


def _clamp(value, lo=0.0, hi=100.0):
    """Limit a command to the legal actuator range [lo, hi]."""
    return max(lo, min(hi, value))
