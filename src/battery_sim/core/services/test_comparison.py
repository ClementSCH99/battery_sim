"""Numerical comparison of simulated and measured cell-test traces."""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from battery_sim.core.simulation import SimulationRun
from battery_sim.core.test_trace import CellTestTrace


@dataclass(frozen=True)
class TraceComparison:
    metrics: dict[str, Optional[float]]
    coverage: dict[str, Any]
    aligned_trace: dict[str, list[float]]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics,
            "coverage": self.coverage,
            "aligned_trace": self.aligned_trace,
            "warnings": list(self.warnings),
        }


class TraceComparisonService:
    """Compare voltage/current only where simulation and test actually overlap."""

    def compare(self, run: SimulationRun, trace: CellTestTrace) -> TraceComparison:
        simulated_voltage = run.result.voltage()
        if simulated_voltage is None:
            raise ValueError("simulation did not provide a voltage signal")
        if simulated_voltage.unit != "V":
            raise ValueError("simulation voltage signal must use V")

        measured_time = np.asarray(trace.elapsed_time_s, dtype=float)
        simulation_time = np.asarray(simulated_voltage.time_s, dtype=float)
        simulation_values = np.asarray(simulated_voltage.values, dtype=float)
        if len(simulation_time) < 2:
            raise ValueError("simulation voltage must contain at least two samples")
        if len(simulation_time) != len(simulation_values):
            raise ValueError("simulation voltage time and values must have the same length")
        if not np.all(np.isfinite(simulation_time)) or not np.all(np.isfinite(simulation_values)):
            raise ValueError("simulation voltage signal must contain only finite values")
        if np.any(np.diff(simulation_time) <= 0):
            raise ValueError("simulation voltage time must be strictly increasing")

        common_start = max(float(measured_time[0]), float(simulation_time[0]))
        common_end = min(float(measured_time[-1]), float(simulation_time[-1]))
        mask = (measured_time >= common_start) & (measured_time <= common_end)
        if int(np.count_nonzero(mask)) < 2:
            raise ValueError("simulation and test share fewer than two time samples")

        aligned_time = measured_time[mask]
        measured_voltage = np.asarray(trace.voltage_V, dtype=float)[mask]
        aligned_sim_voltage = np.interp(
            aligned_time,
            simulation_time,
            simulation_values,
        )
        voltage_residual = aligned_sim_voltage - measured_voltage

        metrics: dict[str, Optional[float]] = {
            "voltage_rmse_V": float(np.sqrt(np.mean(voltage_residual**2))),
            "voltage_mae_V": float(np.mean(np.abs(voltage_residual))),
            "voltage_bias_V": float(np.mean(voltage_residual)),
            "voltage_max_abs_error_V": float(np.max(np.abs(voltage_residual))),
            "current_rmse_A": None,
            "current_bias_A": None,
        }
        aligned: dict[str, list[float]] = {
            "time_s": aligned_time.tolist(),
            "measured_voltage_V": measured_voltage.tolist(),
            "simulated_voltage_V": aligned_sim_voltage.tolist(),
            "voltage_residual_V": voltage_residual.tolist(),
        }

        warnings: list[str] = []
        simulated_current = run.result.current()
        if trace.current_A is not None and simulated_current is not None:
            if simulated_current.unit != "A":
                raise ValueError("simulation current signal must use A")
            simulated_current_time = np.asarray(simulated_current.time_s, dtype=float)
            simulated_current_values = np.asarray(simulated_current.values, dtype=float)
            if len(simulated_current_time) != len(simulated_current_values):
                raise ValueError("simulation current time and values must have the same length")
            if (
                not np.all(np.isfinite(simulated_current_time))
                or not np.all(np.isfinite(simulated_current_values))
                or np.any(np.diff(simulated_current_time) <= 0)
            ):
                raise ValueError("simulation current signal must be finite with increasing time")
            if (
                simulated_current_time[0] > aligned_time[0]
                or simulated_current_time[-1] < aligned_time[-1]
            ):
                warnings.append(
                    "Simulation current does not cover the voltage comparison interval; current metrics were omitted."
                )
                simulated_current = None

        if trace.current_A is not None and simulated_current is not None:
            measured_current = np.asarray(trace.current_A, dtype=float)[mask]
            aligned_sim_current = np.interp(
                aligned_time,
                simulated_current_time,
                simulated_current_values,
            )
            current_residual = aligned_sim_current - measured_current
            metrics["current_rmse_A"] = float(np.sqrt(np.mean(current_residual**2)))
            metrics["current_bias_A"] = float(np.mean(current_residual))
            aligned.update(
                {
                    "measured_current_A": measured_current.tolist(),
                    "simulated_current_A": aligned_sim_current.tolist(),
                    "current_residual_A": current_residual.tolist(),
                }
            )
        elif trace.current_A is not None and not warnings:
            warnings.append(
                "Measured current was supplied but simulation current was unavailable; current metrics were omitted."
            )

        measured_duration = float(measured_time[-1] - measured_time[0])
        compared_start = float(aligned_time[0])
        compared_end = float(aligned_time[-1])
        compared_duration = compared_end - compared_start
        coverage_fraction = compared_duration / measured_duration
        if coverage_fraction < 1.0 - 1e-12:
            warnings.append(
                "Simulation ended before the test trace; metrics exclude the uncovered tail."
            )
        if trace.current_A is None:
            warnings.append("Measured current was not supplied; current agreement was not checked.")

        return TraceComparison(
            metrics=metrics,
            coverage={
                "status": "complete" if coverage_fraction >= 1.0 - 1e-12 else "partial",
                "compared_samples": int(np.count_nonzero(mask)),
                "total_test_samples": len(trace.time_s),
                "common_start_s": compared_start,
                "common_end_s": compared_end,
                "compared_duration_s": compared_duration,
                "test_duration_s": measured_duration,
                "test_duration_fraction": coverage_fraction,
                "extrapolation_used": False,
                "interpolation_method": "linear_simulation_to_measurement_timestamps",
                "metric_weighting": "unweighted_measurement_samples",
            },
            aligned_trace=aligned,
            warnings=tuple(warnings),
        )
