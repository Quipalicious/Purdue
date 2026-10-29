"""
Student PID controller interface for the Martian greenhouse simulation.

Students implement their environmental control algorithm inside the
:class:`StudentPIDController` class below.  The :meth:`update` method is
called once per simulation tick (default dt = 60 s) and must return
:class:`ActuatorCommands` with all percentages clamped to [0, 100].

PID control law
---------------
For each controlled variable, the control signal u(t) is:

    u(t) = Kp * e(t)  +  Ki * integral of e(t) dt  +  Kd * de(t)/dt

where:

    e(t)                = setpoint - measured_value     (current error)
    integral of e(t) dt = accumulated over time         (removes steady offset)
    de(t)/dt            ~= (e(t) - e(t-1)) / dt         (rate of change)

Lettuce (*Lactuca sativa*) growth targets
-----------------------------------------
+---------------------+------------------------------+
| Variable            | Target                       |
+=====================+==============================+
| Temperature (day)   | 23 deg C                     |
+---------------------+------------------------------+
| Temperature (night) | 18 deg C                     |
+---------------------+------------------------------+
| CO2                 | 800 to 1 000 ppm  (set 900)  |
+---------------------+------------------------------+
| Relative humidity   | 40 to 60 %        (set 50 %) |
+---------------------+------------------------------+

CO2 sensor fault
----------------
The primary CO2 sensor (``co2_ppm_primary`` / ``read_K30``) can freeze and
report a stuck value until it recovers.  The acceptance test includes K30
freezes.  The Milestone 4 acceptance test also includes the sensor faults found
when GHU-2 was commissioned (``constants.M4_SENSOR_FAULTS``).  GHU-2 shares an airlock with crew spaces, so CO2 at or above
5 000 ppm for 30 consecutive minutes is a toxicity event for the crew, and
a toxicity event fails the test.

How the controller uses the two CO2 readings is a design decision for the
team.
"""

from dataclasses import dataclass


@dataclass
class SensorReadings:
    """Bundle of all virtual sensor readings for one simulation tick."""

    temperature_c: float  #: DHT22 temperature reading (deg C)
    rh_pct: float  #: DHT22 relative humidity reading (%)
    co2_ppm_primary: float  #: K30 CO2 reading (primary, can freeze at a stuck value)
    co2_ppm_backup: float  #: SCD41 CO2 reading (backup CO2 sensor)
    soil_vwc: float  #: TEROS12 volumetric water content [0 to 1]
    par_umol_m2_s: float  #: SQ-500 PAR reading (umol/m^2/s)


@dataclass
class Setpoints:
    """Target operating conditions for the current time step."""

    temperature_c: float  #: Target temperature (23 deg C day / 18 deg C night)
    co2_ppm: float  #: Target CO2 concentration (ppm)
    rh_pct: float  #: Target relative humidity (%)
    soil_vwc: float  #: Target soil moisture (VWC)
    is_daytime: bool  #: True when the sun is above the horizon


@dataclass
class ActuatorCommands:
    """Control outputs from the student controller (percentages 0 to 100)."""

    heater_pct: float = 0.0  #: Heater power %
    led_pct: float = 0.0  #: LED intensity %
    co2_valve_pct: float = 0.0  #: CO2 valve opening %
    pump_pct: float = 0.0  #: Irrigation pump speed %


class StudentPIDController:
    """
    Student controller class.  Replace the body of ``update()`` with your
    PID control logic.

    The simulator calls your controller once per simulation tick (dt = 60 s).
    It receives sensor readings (with noise and possible faults) and the
    current setpoints.  It must return actuator commands as percentages in
    [0, 100].

    Starter pseudocode (temperature loop)::

        e_temp = setpoints.temperature_c - readings.temperature_c
        self._integral_temp += e_temp * dt_seconds
        deriv = (e_temp - self._prev_error_temp) / dt_seconds
        u_heat = (self.Kp_temp * e_temp + self.Ki_temp * self._integral_temp
                  + self.Kd_temp * deriv)
        self._prev_error_temp = e_temp
        return ActuatorCommands(heater_pct=max(0, min(100, u_heat)))

    Tune the gains (Kp, Ki, Kd) so the controller:
      1. Maintains temperature within +/-2 deg C of setpoint.
      2. Keeps CO2 in [800, 1 000] ppm.
      3. Maintains relative humidity in [40, 60] %.
      4. Handles the K30 CO2 sensor freeze fault safely.

    See the module docstring for the CO2 sensor fault.
    """

    def __init__(self) -> None:
        # ---- Tune these PID gains ------------------------------------
        self.Kp_temp: float = 0.0
        self.Ki_temp: float = 0.0
        self.Kd_temp: float = 0.0

        self.Kp_co2: float = 0.0
        self.Ki_co2: float = 0.0
        self.Kd_co2: float = 0.0
        # ---------------------------------------------------------------

        # Internal PID state.  Add more variables as needed.
        self._integral_temp: float = 0.0
        self._prev_error_temp: float = 0.0

        self._integral_co2: float = 0.0
        self._prev_error_co2: float = 0.0

    def update(
        self,
        readings: SensorReadings,
        setpoints: Setpoints,
        dt_seconds: float,
    ) -> ActuatorCommands:
        """
        Compute actuator commands from sensor readings and setpoints.

        Called once per simulation tick.

        Parameters
        ----------
        readings : SensorReadings
            Current sensor values (with noise and possible faults).
        setpoints : Setpoints
            Current target operating conditions for the active crop phase.
        dt_seconds : float
            Time step duration in seconds (typically 60.0).

        Returns
        -------
        ActuatorCommands
            Desired actuator outputs as percentages (0 to 100).

        Notes
        -----
        **CO2 Sensor Fault Handling (required):**

        The K30 primary sensor (``readings.co2_ppm_primary``) can freeze and
        report a stuck value until it recovers.  CO2 at or above 5 000 ppm
        for 30 consecutive minutes is a toxicity event for the crew, and a
        toxicity event fails the test.

        How the controller uses the two CO2 readings is a design decision
        for the team.
        """
        # ================================================================
        # TODO: Replace this stub with your PID implementation.
        #
        # The stub returns zero commands (no control action), so the simulation
        # can run before any student code is written.  A run with this stub
        # fails: the heater stays off and the greenhouse temperature falls
        # toward the outside Mars temperature.
        # ================================================================
        return ActuatorCommands(
            heater_pct=0.0,
            led_pct=0.0,
            co2_valve_pct=0.0,
            pump_pct=0.0,
        )
