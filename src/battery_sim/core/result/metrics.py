"""Derived scalar metrics for canonical simulation results."""

from typing import Optional

import numpy as np

from battery_sim.core.result.signals import Signal
from battery_sim.core.result.timeseries import TimeSeries


class ResultMetricsMixin:
    """Metrics derived only from canonical time series.

    The concrete result model supplies ``_data`` and the convenience accessors.
    Keeping derivations here separates signal storage from analysis.
    """

    _data: dict[Signal, TimeSeries]

    def energy(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def capacity(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def power(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def voltage(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def current(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def temperature(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def internal_resistance(self) -> Optional[TimeSeries]:
        raise NotImplementedError

    def final(self, signal: Signal) -> float:
        raise NotImplementedError

    def total_energy(self) -> Optional[float]:
        series = self.energy()
        return None if series is None else series.values[-1]

    def total_energy_Wh(self) -> Optional[float]:
        """Legacy alias retained until compatibility removal."""
        return self.total_energy()

    def total_capacity_delivered(self) -> Optional[float]:
        series = self.capacity()
        return None if series is None else series.values[-1]

    def peak_power(self) -> Optional[float]:
        series = self.power()
        return None if series is None else float(np.max(np.abs(series.values)))

    def average_power(self) -> Optional[float]:
        series = self.power()
        return None if series is None else float(np.mean(series.values))

    def min_voltage(self) -> Optional[float]:
        series = self.voltage()
        return None if series is None else float(np.min(series.values))

    def max_voltage(self) -> Optional[float]:
        series = self.voltage()
        return None if series is None else float(np.max(series.values))

    def peak_voltage(self) -> Optional[float]:
        return self.max_voltage()

    def peak_current(self) -> Optional[float]:
        series = self.current()
        return None if series is None else float(np.max(np.abs(series.values)))

    def final_soc(self) -> Optional[float]:
        return self.final(Signal.SOC) if Signal.SOC in self._data else None

    def min_temperature(self) -> Optional[float]:
        series = self.temperature()
        return None if series is None else float(np.min(series.values))

    def max_temperature(self) -> Optional[float]:
        series = self.temperature()
        return None if series is None else float(np.max(series.values))

    def average_internal_resistance(self) -> Optional[float]:
        series = self.internal_resistance()
        if series is None:
            return None
        valid = np.asarray(series.values)[~np.isnan(series.values)]
        return None if len(valid) == 0 else float(np.mean(valid))

    def round_trip_efficiency(self) -> Optional[float]:
        energy = self.energy()
        power = self.power()
        voltage = self.voltage()
        if energy is None or power is None or voltage is None:
            return None

        charge_energy = 0.0
        discharge_energy = 0.0
        for index, value in enumerate(power.values):
            duration = power.time_s[index] if index > 0 else 0
            if value < 0:
                charge_energy += abs(value) * duration
            else:
                discharge_energy += value * duration
        if charge_energy <= 0:
            return None
        return discharge_energy / charge_energy * 100.0

    @staticmethod
    def _integrate_phase(
        values: np.ndarray,
        time_s: np.ndarray,
        *,
        charging: bool,
    ) -> float:
        dt = np.diff(time_s)
        samples = values[:-1]
        mask = samples < 0 if charging else samples > 0
        increments = np.where(mask, np.abs(samples) * dt / 3600.0, 0)
        return float(np.sum(increments))

    def charged_capacity(self) -> Optional[float]:
        current = self.current()
        if current is None:
            return None
        return self._integrate_phase(
            np.asarray(current.values),
            np.asarray(current.time_s),
            charging=True,
        )

    def discharged_capacity(self) -> Optional[float]:
        current = self.current()
        if current is None:
            return None
        return self._integrate_phase(
            np.asarray(current.values),
            np.asarray(current.time_s),
            charging=False,
        )

    def net_capacity(self) -> Optional[float]:
        discharged = self.discharged_capacity()
        charged = self.charged_capacity()
        if discharged is None or charged is None:
            return None
        return discharged - charged

    def _phase_energy(self, *, charging: bool) -> Optional[float]:
        current = self.current()
        voltage = self.voltage()
        if current is None or voltage is None:
            return None
        power = np.asarray(voltage.values) * np.asarray(current.values)
        return self._integrate_phase(
            power,
            np.asarray(current.time_s),
            charging=charging,
        )

    def charged_energy(self) -> Optional[float]:
        return self._phase_energy(charging=True)

    def discharged_energy(self) -> Optional[float]:
        return self._phase_energy(charging=False)

    def net_energy(self) -> Optional[float]:
        discharged = self.discharged_energy()
        charged = self.charged_energy()
        if discharged is None or charged is None:
            return None
        return discharged - charged

    def charge_discharge_efficiency(self) -> Optional[float]:
        charged = self.charged_energy()
        discharged = self.discharged_energy()
        if charged is None or discharged is None:
            return None
        if charged <= 0:
            return 100.0 if discharged > 0 else None
        return discharged / charged * 100.0

    def efficiency(self) -> Optional[float]:
        series = self._data.get(Signal.EFFICIENCY)
        if series is not None:
            values = np.asarray(series.values)
            valid = values[~np.isnan(values)]
            if len(valid) > 0:
                return float(np.mean(valid))
        return self.charge_discharge_efficiency()

    def state_variables_summary(self) -> dict[Signal, dict[str, float]]:
        summary: dict[Signal, dict[str, float]] = {}
        for signal, series in self._data.items():
            values = np.asarray(series.values)
            valid = values[~np.isnan(values)]
            if len(valid) == 0:
                continue
            summary[signal] = {
                "min": float(np.min(valid)),
                "mean": float(np.mean(valid)),
                "max": float(np.max(valid)),
                "final": float(series.values[-1]),
            }
        return summary
