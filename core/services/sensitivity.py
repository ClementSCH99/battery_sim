"""One-at-a-time sensitivity analysis service."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from battery_sim.core.cell import Cell
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.services.execution import BatchExecutionService
from battery_sim.core.services.sweep import ParameterSweepService


@dataclass(frozen=True)
class SensitivityResult:
    parameter_name: str
    parameter_values: list[float]
    metric_name: str
    metric_values: list[Optional[float]]
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    range_value: Optional[float] = None
    sensitivity_coefficient: Optional[float] = None

    def interpretation(self) -> str:
        if self.sensitivity_coefficient is None:
            return "Could not compute sensitivity (insufficient data)"
        if self.sensitivity_coefficient < 1:
            return "VERY LOW sensitivity - parameter barely affects result"
        if self.sensitivity_coefficient < 5:
            return "LOW sensitivity - small impact"
        if self.sensitivity_coefficient < 20:
            return "MODERATE sensitivity - meaningful impact"
        if self.sensitivity_coefficient < 50:
            return "HIGH sensitivity - significant impact"
        return "VERY HIGH sensitivity - dramatic impact"


class SensitivityService:
    def __init__(
        self,
        batch_service: Optional[BatchExecutionService] = None,
        backend: Optional[SimulationBackend] = None,
    ) -> None:
        if batch_service is not None:
            self.batch_service = batch_service
        elif backend is not None:
            self.batch_service = BatchExecutionService(backend=backend)
        else:
            raise ValueError("SensitivityService requires either batch_service or backend")

    def analyze_single_parameter(
        self,
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: list[float],
        config: Any,
        metric_extractor: Callable[[SimulationRun], float],
    ) -> SensitivityResult:
        baseline = Simulation(
            cell=baseline_cell,
            model=config.model,
            protocol=config.protocol,
            environment=config.environment,
            solver_config=config.solver_config,
        )
        target = "environment" if parameter_name == "temperature_C" else "cell"
        sweep_results = ParameterSweepService(
            self.batch_service.execution_service
        ).sweep_parameter(
            baseline,
            target,
            parameter_name,
            parameter_values,
            continue_on_error=True,
        )

        metric_values: list[Optional[float]] = []
        for _, run, _, _ in sweep_results:
            if run is None:
                metric_values.append(None)
                continue
            try:
                metric_values.append(metric_extractor(run))
            except Exception:
                metric_values.append(None)

        valid_values = [value for value in metric_values if value is not None]
        min_value = min(valid_values) if valid_values else None
        max_value = max(valid_values) if valid_values else None
        range_value = max_value - min_value if valid_values else None
        coefficient = None
        if valid_values and valid_values[0] != 0:
            coefficient = range_value / abs(valid_values[0]) * 100

        return SensitivityResult(
            parameter_name=parameter_name,
            parameter_values=parameter_values,
            metric_name=metric_extractor.__name__,
            metric_values=metric_values,
            min_value=min_value,
            max_value=max_value,
            range_value=range_value,
            sensitivity_coefficient=coefficient,
        )
