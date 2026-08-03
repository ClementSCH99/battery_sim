"""Translate PyBaMM solutions into battery_sim's canonical Result contract."""

from typing import Any, Optional

import numpy as np

from battery_sim.backend.pybamm_signal import (
    PYBAMM_SIGNAL_ALIASES,
    PYBAMM_SIGNAL_MAP,
)
from battery_sim.core.protocol import Protocol
from battery_sim.core.result import Result
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class PyBaMMResultExtractor:
    """Extract primary, derived and per-cycle signals from a PyBaMM solution."""

    def extract(self, solution: Any, protocol: Optional[Protocol] = None) -> Result:
        time_s = self._time_axis(solution)
        data = self._extract_primary_signals(solution, time_s)
        self._derive_electrical_signals(data, time_s)
        if (
            protocol is not None
            and protocol.n_cycles is not None
            and protocol.n_cycles > 1
            and Signal.CURRENT in data
            and Signal.VOLTAGE in data
        ):
            self._extract_cycling_signals(data, protocol, solution)
        return Result(data)

    def _extract_primary_signals(
        self,
        solution: Any,
        time_s: list[float],
    ) -> dict[Signal, TimeSeries]:
        data: dict[Signal, TimeSeries] = {}
        for signal, (primary_name, declared_unit) in PYBAMM_SIGNAL_MAP.items():
            values = self._read_signal(solution, signal, primary_name)
            if values is None:
                continue
            values_array = np.asarray(values)
            unit = declared_unit
            if signal == Signal.SOC:
                if values_array.size and np.nanmax(values_array) <= 1.0:
                    values_array = values_array * 100.0
                unit = "%"
            elif signal in (Signal.TEMPERATURE, Signal.CELL_TEMPERATURE):
                values_array = values_array - 273.15
                unit = "°C"

            data[signal] = TimeSeries(
                time_s=time_s,
                values=self._flatten(values_array),
                unit=unit,
            )
        return data

    @staticmethod
    def _read_signal(solution: Any, signal: Signal, primary_name: str) -> Any:
        for variable_name in [primary_name, *PYBAMM_SIGNAL_ALIASES.get(signal, [])]:
            try:
                return solution[variable_name].data
            except KeyError:
                continue
        return None

    def _derive_electrical_signals(
        self,
        data: dict[Signal, TimeSeries],
        time_s: list[float],
    ) -> None:
        if Signal.VOLTAGE not in data or Signal.CURRENT not in data:
            return
        voltage = np.asarray(data[Signal.VOLTAGE].values, dtype=float)
        current = np.asarray(data[Signal.CURRENT].values, dtype=float)
        time_array = np.asarray(time_s, dtype=float)
        if not (len(voltage) == len(current) == len(time_array)):
            raise ValueError("Voltage, current and time signals must have equal length")

        power = voltage * current
        data[Signal.POWER] = TimeSeries(time_s, power.tolist(), "W")
        if len(time_array) < 2:
            data[Signal.ENERGY] = TimeSeries(time_s, [0.0] * len(time_s), "Wh")
            data[Signal.CAPACITY] = TimeSeries(time_s, [0.0] * len(time_s), "Ah")
            return

        dt = np.diff(time_array)
        energy = np.concatenate(([0.0], np.cumsum(power[:-1] * dt / 3600.0)))
        data[Signal.ENERGY] = TimeSeries(time_s, energy.tolist(), "Wh")

        charged_capacity, discharged_capacity = self._integrate_signed_quantity(
            current, dt
        )
        charged_energy, discharged_energy = self._integrate_signed_quantity(
            power, dt
        )
        capacity = discharged_capacity - charged_capacity
        data[Signal.CAPACITY] = TimeSeries(time_s, capacity.tolist(), "Ah")

        # Round-trip efficiency only has physical meaning after both charge and
        # discharge energy have been observed. Missing evidence stays absent.
        valid_efficiency = (charged_energy > 0.0) & (discharged_energy > 0.0)
        if np.any(valid_efficiency):
            efficiency = np.full_like(charged_energy, np.nan, dtype=float)
            efficiency[valid_efficiency] = (
                discharged_energy[valid_efficiency]
                / charged_energy[valid_efficiency]
                * 100.0
            )
            finite = np.isfinite(efficiency)
            data[Signal.EFFICIENCY] = TimeSeries(
                time_s=np.asarray(time_s)[finite].tolist(),
                values=efficiency[finite].tolist(),
                unit="%",
            )

        self._derive_internal_resistance(data, time_array, voltage, current)

    @staticmethod
    def _integrate_signed_quantity(
        values: np.ndarray,
        dt: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Integrate negative (charge/input) and positive (discharge/output)."""
        negative = np.zeros_like(values, dtype=float)
        positive = np.zeros_like(values, dtype=float)
        for index in range(len(values) - 1):
            increment = abs(values[index]) * dt[index] / 3600.0
            negative[index + 1] = negative[index]
            positive[index + 1] = positive[index]
            if values[index] < 0:
                negative[index + 1] += increment
            elif values[index] > 0:
                positive[index + 1] += increment
        return negative, positive

    @staticmethod
    def _derive_internal_resistance(
        data: dict[Signal, TimeSeries],
        time_s: np.ndarray,
        voltage: np.ndarray,
        current: np.ndarray,
    ) -> None:
        """Expose only finite ΔV/ΔI estimates; a constant-current trace has none."""
        window_size = max(int(len(current) / 20), 3)
        estimates: list[float] = []
        estimate_times: list[float] = []
        for index in range(window_size, len(current) - window_size):
            start = index - window_size
            end = index + window_size
            if np.mean(np.abs(current[start:end])) < 0.01:
                continue
            delta_current = current[end] - current[start]
            if abs(delta_current) <= 0.01:
                continue
            estimate = abs((voltage[end] - voltage[start]) / delta_current)
            if np.isfinite(estimate):
                estimate_times.append(float(time_s[index]))
                estimates.append(float(estimate))
        if estimates:
            data[Signal.INTERNAL_RESISTANCE] = TimeSeries(
                time_s=estimate_times,
                values=estimates,
                unit="Ω",
            )

    @staticmethod
    def _extract_cycling_signals(
        data: dict[Signal, TimeSeries],
        protocol: Protocol,
        solution: Any,
    ) -> None:
        n_cycles = protocol.n_cycles
        cycle_solutions = list(getattr(solution, "cycles", []) or [])
        if len(cycle_solutions) != n_cycles:
            raise ValueError(
                "PyBaMM cycle boundaries are unavailable or inconsistent: "
                f"expected {n_cycles}, received {len(cycle_solutions)}."
            )

        cycle_numbers: list[float] = []
        discharge_capacities: list[float] = []
        charge_capacities: list[float] = []
        efficiencies: list[float] = []
        for cycle_number, cycle_solution in enumerate(cycle_solutions, start=1):
            time_array = np.asarray(
                cycle_solution["Time [s]"].data, dtype=float
            ).reshape(-1)
            current_array = np.asarray(
                cycle_solution["Current [A]"].data, dtype=float
            ).reshape(-1)
            if len(time_array) < 2 or len(current_array) < 2:
                continue
            dt = np.diff(time_array)
            points = min(len(current_array) - 1, len(dt))
            discharge_Ah = 0.0
            charge_Ah = 0.0
            for index in range(points):
                amp_hours = abs(current_array[index]) * dt[index] / 3600.0
                if current_array[index] > 0:
                    discharge_Ah += amp_hours
                elif current_array[index] < 0:
                    charge_Ah += amp_hours
            cycle_numbers.append(float(cycle_number))
            discharge_capacities.append(discharge_Ah)
            charge_capacities.append(charge_Ah)
            efficiencies.append(
                discharge_Ah / charge_Ah * 100.0 if charge_Ah > 0 else 0.0
            )

        if not cycle_numbers:
            return
        first_capacity = (
            discharge_capacities[0] if discharge_capacities[0] > 0 else 1.0
        )
        retention = [
            capacity / first_capacity * 100.0
            for capacity in discharge_capacities
        ]
        data[Signal.CYCLE_DISCHARGE_CAPACITY] = TimeSeries(
            cycle_numbers, discharge_capacities, "Ah"
        )
        data[Signal.CYCLE_CHARGE_CAPACITY] = TimeSeries(
            cycle_numbers, charge_capacities, "Ah"
        )
        data[Signal.CYCLE_COULOMBIC_EFFICIENCY] = TimeSeries(
            cycle_numbers, efficiencies, "%"
        )
        data[Signal.CYCLE_CAPACITY_RETENTION] = TimeSeries(
            cycle_numbers, retention, "%"
        )

    @classmethod
    def _time_axis(cls, solution: Any) -> list[float]:
        return cls._flatten(np.asarray(solution["Time [s]"].data))

    @staticmethod
    def _flatten(values: np.ndarray) -> list[float]:
        as_list = values.tolist()
        if as_list and isinstance(as_list[0], list):
            return [float(value[0]) for value in as_list]
        return [float(value) for value in as_list]
