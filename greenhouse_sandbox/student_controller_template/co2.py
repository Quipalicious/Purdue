"""CO2 valve control for the GHU-2 greenhouse (percent open, 0 to 100).

Owner: <name>
"""


def control_co2(readings, setpoints, dt, state) -> float:
    """Return the CO2 valve opening for this tick, a number in [0, 100].

    Parameters
    ----------
    readings : SensorReadings
        temperature_c, rh_pct, co2_ppm_primary (K30), co2_ppm_backup (SCD41),
        soil_vwc, par_umol_m2_s.
    setpoints : Setpoints
        temperature_c (day and night aware), co2_ppm, rh_pct, soil_vwc,
        is_daytime.
    dt : float
        The length of this tick in seconds (60 by default).
    state : dict
        A plain dictionary you may use to remember values between ticks.
        All four actuator files share this one dictionary, so start every
        key you use with this file's name (for example, state["co2_total"]).
        Two files that both write state["total"] overwrite each other.

    Returns
    -------
    float
        CO2 valve opening percent, from 0 to 100.
    """
    # TODO: Replace this stub with your Milestone 3 CO2 design.
    # Your M3 flowchart is the specification, including your CO2 sensor-trust
    # rule. Keep each command in range before you return it:
    #   1. At the top of this file, add "from .helpers import _clamp".
    #   2. Return "_clamp(u, 0.0, 100.0)", where u is your command.
    return 0.0
