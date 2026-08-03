"""Typed compatibility facade over the canonical parameter-sweep service."""

from dataclasses import dataclass, field
from typing import Any, Callable

from battery_sim.application.services import ParameterSweepService
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationRun


@dataclass(frozen=True)
class ParameterOverride:
    """Record cell and environment changes for reproducibility."""

    cell_parameters: dict[str, Any] = field(default_factory=dict)
    environment_parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_parameters": self.cell_parameters,
            "environment_parameters": self.environment_parameters,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ParameterOverride":
        return ParameterOverride(
            cell_parameters=data.get("cell_parameters", {}),
            environment_parameters=data.get("environment_parameters", {}),
        )

    def summary(self) -> str:
        lines: list[str] = []
        for label, values in (
            ("Cell parameters", self.cell_parameters),
            ("Environment parameters", self.environment_parameters),
        ):
            if values:
                lines.append(f"{label}:")
                lines.extend(f"  {key}: {value}" for key, value in values.items())
        return "\n".join(lines) if lines else "(No overrides)"


@dataclass(frozen=True)
class SweepResult:
    """Typed result for one value in a one-at-a-time sweep."""

    parameter_name: str
    parameter_value: Any
    simulation_result: SimulationRun
    override: ParameterOverride


class ParameterSweep:
    """Preserve the historical typed API while delegating all execution."""

    def __init__(self, backend: SimulationBackend) -> None:
        self._sweep_service = ParameterSweepService(backend=backend)

    def sweep_cell_parameter(
        self,
        baseline_simulation: Simulation,
        parameter_name: str,
        values: list[Any],
        verbose: bool = False,
    ) -> list[SweepResult]:
        return self._sweep_one_target(
            baseline_simulation,
            "cell",
            parameter_name,
            values,
            verbose,
        )

    def sweep_environment_parameter(
        self,
        baseline_simulation: Simulation,
        parameter_name: str,
        values: list[Any],
        verbose: bool = False,
    ) -> list[SweepResult]:
        return self._sweep_one_target(
            baseline_simulation,
            "environment",
            parameter_name,
            values,
            verbose,
        )

    def _sweep_one_target(
        self,
        baseline_simulation: Simulation,
        target: str,
        parameter_name: str,
        values: list[Any],
        verbose: bool,
    ) -> list[SweepResult]:
        raw_results = self._sweep_service.sweep_parameter(
            baseline_simulation,
            target,
            parameter_name,
            values,
        )
        results: list[SweepResult] = []
        for index, (value, run, cell_values, environment_values) in enumerate(
            raw_results,
            start=1,
        ):
            if run is None:
                raise RuntimeError("Sweep service returned no run without continue_on_error")
            if verbose:
                print(f"  [{index}/{len(values)}] {parameter_name} = {value}... Done")
            results.append(
                SweepResult(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    simulation_result=run,
                    override=ParameterOverride(cell_values, environment_values),
                )
            )
        return results

    def multi_parameter_sweep(
        self,
        baseline_simulation: Simulation,
        parameters: dict[str, list[Any]],
        verbose: bool = False,
    ) -> list[tuple[dict[str, Any], SimulationRun, ParameterOverride]]:
        raw_results = self._sweep_service.multi_parameter_sweep(
            baseline_simulation,
            parameters,
        )
        results = []
        for index, (values, run, cell_values, environment_values) in enumerate(
            raw_results,
            start=1,
        ):
            if verbose:
                assignments = " ".join(f"{key}={value}" for key, value in values.items())
                print(f"  [{index}/{len(raw_results)}] {assignments} ... Done")
            results.append(
                (values, run, ParameterOverride(cell_values, environment_values))
            )
        return results

    @staticmethod
    def analyze_sensitivity(
        sweep_results: list[SweepResult],
        metric_func: Callable[[SimulationRun], float],
        metric_name: str = "Metric",
    ) -> dict[str, Any]:
        if not sweep_results:
            return {"metric_name": metric_name, "error": "No sweep results provided"}
        parameter_values: list[Any] = []
        metric_values: list[float] = []
        for sweep_result in sweep_results:
            try:
                metric_value = metric_func(sweep_result.simulation_result)
            except Exception:
                continue
            if metric_value is not None:
                parameter_values.append(sweep_result.parameter_value)
                metric_values.append(metric_value)
        parameter_name = sweep_results[0].parameter_name
        if not metric_values:
            return {
                "metric_name": metric_name,
                "parameter_name": parameter_name,
                "error": "No valid metric values computed",
            }
        minimum = min(metric_values)
        maximum = max(metric_values)
        value_range = maximum - minimum
        baseline = metric_values[0]
        return {
            "metric_name": metric_name,
            "parameter_name": parameter_name,
            "parameter_values": parameter_values,
            "metric_values": metric_values,
            "min": minimum,
            "max": maximum,
            "range": value_range,
            "sensitivity": value_range / baseline if baseline != 0 else 0,
            "baseline_value": baseline,
        }
