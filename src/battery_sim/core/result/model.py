"""Signal payload returned by a completed simulation."""

from typing import Any, Optional

from battery_sim.core.result.metrics import ResultMetricsMixin
from battery_sim.core.result.signals import Signal
from battery_sim.core.result.timeseries import TimeSeries


class Result(ResultMetricsMixin):
    """Collection of canonical time series and their derived metrics."""

    def __init__(
        self,
        data: dict[Signal, TimeSeries],
        parameter_override: Optional[Any] = None,
    ) -> None:
        self._data = data
        self.parameter_override = parameter_override

    def get(self, signal: Signal) -> TimeSeries:
        return self._data[signal]

    def final(self, signal: Signal) -> float:
        return self._data[signal].values[-1]

    def available_signals(self) -> list[Signal]:
        return list(self._data)

    def get_parameter_override(self) -> Optional[Any]:
        return self.parameter_override

    def has_parameter_overrides(self) -> bool:
        override = self.parameter_override
        if override is None:
            return False
        return bool(
            override.cell_parameters or override.environment_parameters
        )

    def soc(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.SOC)

    def voltage(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.VOLTAGE)

    def current(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.CURRENT)

    def temperature(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.TEMPERATURE)

    def power(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.POWER)

    def energy(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.ENERGY)

    def capacity(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.CAPACITY)

    def internal_resistance(self) -> Optional[TimeSeries]:
        return self._data.get(Signal.INTERNAL_RESISTANCE)

    def __repr__(self) -> str:
        lines = ["Result Summary:"]
        for signal in self.available_signals():
            series = self._data[signal]
            lines.append(
                f"  {signal.value:20s}: "
                f"final={series.values[-1]:10.3f} {series.unit}"
            )
        return "\n".join(lines)
