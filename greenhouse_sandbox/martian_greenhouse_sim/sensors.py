"""
Virtual sensor layer for the Martian greenhouse simulation.

Each sensor method returns the corresponding greenhouse state variable with
a small amount of Gaussian noise added to simulate real-world measurement
inaccuracies.  Sensor names match real hardware used in MLGH research:

+---------+----------------------------------------------+------------------+
| Sensor  | Measurement                                  | Noise (1-sigma)  |
+=========+==============================================+==================+
| DHT22   | Temperature (deg C) + Relative humidity (%)  | 0.2 deg C, 1.0 % |
+---------+----------------------------------------------+------------------+
| K30     | CO2 concentration (ppm), primary             | 20 ppm           |
|         | Fault mode: freeze                           |                  |
+---------+----------------------------------------------+------------------+
| SCD41   | CO2 concentration (ppm), backup              | 20 ppm           |
|         | Fault mode: drift (optional)                 |                  |
+---------+----------------------------------------------+------------------+
| TEROS12 | Soil volumetric water content (VWC) [0-1]    | 0.01             |
+---------+----------------------------------------------+------------------+
| SQ-500  | PAR (umol/m^2/s)                             | 10 umol/m^2/s    |
+---------+----------------------------------------------+------------------+

CO2 Sensor Faults
-----------------
The K30 primary CO2 sensor can freeze and report a wrong value, regardless
of the true internal CO2 level, until it recovers.  The SCD41 backup can
drift.  Fault injection is off by default in this class.
``simulation.run_simulation`` turns on K30 freezes for every mission it runs.
The fault model itself is in ``co2_faults``.

How the controller uses the two CO2 readings is a design decision for the
team.
"""

import random
from typing import Optional, Tuple

from . import co2_faults
from .constants import (
    NOISE_CO2_PPM,
    NOISE_PAR_UMOL,
    NOISE_RH_PCT,
    NOISE_TEMP_C,
    NOISE_VWC,
)
from .greenhouse import Greenhouse


class VirtualSensors:
    """
    Data acquisition layer that reads greenhouse state with realistic noise.

    Parameters
    ----------
    greenhouse : Greenhouse
        The greenhouse instance to read state from.
    rng : random.Random, optional
        Random number generator.  Pass a seeded instance for reproducible
        noise and fault patterns.
    freeze_prob_per_step : float
        Probability that the K30 sensor enters a freeze fault at any given
        time step.  The default is 0.0 so faults occur only when enabled.
    freeze_duration_range_s : tuple of (float, float)
        (min, max) duration of a K30 freeze event in seconds.
        Default (1 800, 10 800) = 30 min to 3 hours.
    fault_profile : str
        Name of the CO2 fault profile in ``co2_faults``.  ``"ghu1"`` (the
        default) is the original sensor behavior, with the SCD41 fault off.
        ``constants.M4_SENSOR_FAULTS`` selects the Milestone 4 profile.
    **fault_settings
        Overrides for individual profile settings, for instructor tooling
        and tests.
    """

    def __init__(
        self,
        greenhouse: Greenhouse,
        rng: Optional[random.Random] = None,
        freeze_prob_per_step: float = 0.0,
        freeze_duration_range_s: Tuple[float, float] = (1_800.0, 10_800.0),
        *,
        fault_profile: str = "ghu1",
        **fault_settings,
    ) -> None:
        self._gh = greenhouse
        self._rng: random.Random = rng if rng is not None else random.Random()
        self._faults = co2_faults.new_state(
            fault_profile,
            freeze_prob_per_step,
            freeze_duration_range_s,
            **fault_settings,
        )

    # ------------------------------------------------------------------
    # Required sensor API
    # ------------------------------------------------------------------

    def read_DHT22(self) -> Tuple[float, float]:
        """
        Read internal air temperature and relative humidity.

        Returns
        -------
        (temperature_c, relative_humidity_pct) : tuple of float
            Noisy readings from the DHT22 capacitive humidity/temperature
            sensor.  Temperature noise sigma = 0.2 deg C, RH noise sigma = 1.0 %.
        """
        state = self._gh.state
        temp = state.temp_c + self._rng.gauss(0.0, NOISE_TEMP_C)
        rh = state.rh_pct + self._rng.gauss(0.0, NOISE_RH_PCT)
        rh = max(0.0, min(100.0, rh))
        return temp, rh

    def read_K30(self) -> float:
        """
        Read CO2 concentration in ppm from the primary K30 NDIR sensor.

        .. warning::
            **Fault mode.**  This sensor can freeze and report a
            stuck value, regardless of the actual CO2 level inside the
            greenhouse, until it recovers.  How the controller uses the two
            CO2 readings is a design decision for the team.

        Returns
        -------
        float
            CO2 concentration in ppm.
        """
        return co2_faults.read_k30(self._faults, self._gh.state.co2_ppm, self._noisy_co2)

    def read_SCD41(self) -> float:
        """
        Read CO2 concentration in ppm from the backup SCD41 NDIR sensor.

        This sensor does not share the K30 freeze fault.  It has its own
        drift fault, which is off by default.

        Returns
        -------
        float
            CO2 concentration in ppm.
        """
        return co2_faults.read_scd41(self._faults, self._noisy_co2)

    def read_TEROS12(self) -> float:
        """
        Read soil moisture as volumetric water content (VWC).

        Returns
        -------
        float
            VWC in the range [0, 1].  Noise sigma = 0.01.
        """
        state = self._gh.state
        vwc = state.soil_vwc + self._rng.gauss(0.0, NOISE_VWC)
        return max(0.0, min(1.0, vwc))

    def read_SQ500(self) -> float:
        """
        Read photosynthetically active radiation (PAR) at crop level.

        Returns
        -------
        float
            PAR in umol/m^2/s.  Noise sigma = 10 umol/m^2/s; clamped to >= 0.
        """
        state = self._gh.state
        par = state.par_umol_m2_s + self._rng.gauss(0.0, NOISE_PAR_UMOL)
        return max(0.0, par)

    # ------------------------------------------------------------------
    # Fault management
    # ------------------------------------------------------------------

    def tick_faults(self, current_time_s: float, dt_seconds: float) -> None:
        """
        Advance fault state for the current simulation step.

        Call this **once per tick, before reading any sensor**, so that the
        fault state changes at the right time.

        Parameters
        ----------
        current_time_s : float
            Current simulation time in seconds.
        dt_seconds : float
            Duration of the current time step in seconds.
        """
        co2_faults.advance(self._faults, self._rng, current_time_s, dt_seconds)

    @property
    def co2_freeze_active(self) -> bool:
        """True when the K30 primary CO2 sensor is currently frozen."""
        return self._faults.freeze_active

    @property
    def scd41_drift_active(self) -> bool:
        """True when the SCD41 backup CO2 sensor is currently drifting."""
        return self._faults.drift_active

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _noisy_co2(self, offset_ppm: float = 0.0) -> float:
        """Return true CO2 with Gaussian noise, clamped to >= 200 ppm."""
        co2 = (
            self._gh.state.co2_ppm
            + offset_ppm
            + self._rng.gauss(0.0, NOISE_CO2_PPM)
        )
        return max(200.0, co2)
