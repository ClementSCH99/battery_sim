"""Physical and numerical checks applied to canonical results."""

import numpy as np

from battery_sim.core.result import Result, Signal
from battery_sim.core.simulation.errors import ErrorType, SimulationError


class ErrorDetector:
    """Detect visible physical and numerical violations."""

    @staticmethod
    def detect_voltage_violations(
        result: Result,
        min_voltage_v: float = 2.5,
        max_voltage_v: float = 4.2,
        numerical_tolerance_v: float = 1e-5,
    ) -> list[SimulationError]:
        if Signal.VOLTAGE not in result._data:
            return []

        series = result._data[Signal.VOLTAGE]
        low = [
            index
            for index, value in enumerate(series.values)
            if value < min_voltage_v - numerical_tolerance_v
        ]
        high = [
            index
            for index, value in enumerate(series.values)
            if value > max_voltage_v + numerical_tolerance_v
        ]
        errors: list[SimulationError] = []
        if low:
            index = low[0]
            errors.append(
                SimulationError(
                    error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
                    severity="critical",
                    message=f"Voltage below minimum safe voltage ({len(low)} samples)",
                    location=f"first at {series.time_s[index]:.1f} seconds (index {index})",
                    value=min(series.values[item] for item in low),
                    bounds=f"[{min_voltage_v}V, {max_voltage_v}V]",
                )
            )
        if high:
            index = high[0]
            errors.append(
                SimulationError(
                    error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
                    severity="critical",
                    message=f"Voltage above maximum safe voltage ({len(high)} samples)",
                    location=f"first at {series.time_s[index]:.1f} seconds (index {index})",
                    value=max(series.values[item] for item in high),
                    bounds=f"[{min_voltage_v}V, {max_voltage_v}V]",
                )
            )
        return errors

    @staticmethod
    def detect_numerical_issues(result: Result) -> list[SimulationError]:
        errors: list[SimulationError] = []
        for signal, series in result._data.items():
            values = np.asarray(series.values)
            for indices, error_type, label in (
                (np.where(np.isnan(values))[0], ErrorType.NAN_DETECTED, "NaN"),
                (np.where(np.isinf(values))[0], ErrorType.INF_DETECTED, "Infinity"),
            ):
                if len(indices) == 0:
                    continue
                index = int(indices[0])
                errors.append(
                    SimulationError(
                        error_type=error_type,
                        severity="critical",
                        message=f"{label} detected in {signal.value} ({len(indices)} samples)",
                        location=(
                            f"first at sample {index} "
                            f"(time {series.time_s[index]:.1f}s)"
                        ),
                    )
                )
        return errors

    @staticmethod
    def detect_divergence(
        result: Result,
        growth_threshold: float = 2.0,
    ) -> list[SimulationError]:
        if Signal.VOLTAGE not in result._data:
            return []
        values = np.asarray(result._data[Signal.VOLTAGE].values)
        if len(values) < 2:
            return []
        start = abs(values[0])
        end = abs(values[-1])
        if start <= 0.1 or end / start <= growth_threshold:
            return []
        return [
            SimulationError(
                error_type=ErrorType.DIVERGENCE,
                severity="warning",
                message="Solution appears to be diverging",
                location="over entire simulation",
                value=float(end),
                bounds=f"[0, {start * growth_threshold:.2f}]",
            )
        ]

    @classmethod
    def detect_all(
        cls,
        result: Result,
        cell=None,
        model=None,
    ) -> list[SimulationError]:
        min_voltage_v = 2.5
        max_voltage_v = 4.2
        if cell is not None:
            min_voltage_v = float(
                cell.metadata.get("min_voltage_v", min_voltage_v)
            )
            max_voltage_v = float(
                cell.metadata.get("max_voltage_v", max_voltage_v)
            )
        return [
            *cls.detect_voltage_violations(
                result,
                min_voltage_v=min_voltage_v,
                max_voltage_v=max_voltage_v,
            ),
            *cls.detect_numerical_issues(result),
            *cls.detect_divergence(result),
        ]
