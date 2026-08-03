"""Single and batch simulation execution orchestration."""

from typing import Any, Optional

from battery_sim.core.cell import Cell
from battery_sim.core.simulation import ConvergenceDiagnostics
from battery_sim.core.result import Result
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import ErrorType, SimulationError
from battery_sim.core.simulation import SimulationMetadata
from battery_sim.core.simulation import SimulationRun


class SimulationExecutionService:
    """Execute a validated Simulation through an injected backend port."""

    def __init__(self, backend: SimulationBackend) -> None:
        self.backend = backend

    def execute(self, simulation: Simulation) -> SimulationRun:
        return simulation.run(self.backend)


class BatchExecutionService:
    """Execute homogeneous preset batches while preserving failed runs."""

    def __init__(
        self,
        execution_service: Optional[SimulationExecutionService] = None,
        backend: Optional[SimulationBackend] = None,
    ) -> None:
        if execution_service is not None:
            self.execution_service = execution_service
        elif backend is not None:
            self.execution_service = SimulationExecutionService(backend)
        else:
            raise ValueError("BatchExecutionService requires either execution_service or backend")

    def run_presets(
        self,
        preset_names: list[str],
        config: Any,
    ) -> list[tuple[str, Optional[SimulationRun]]]:
        results: list[tuple[str, Optional[SimulationRun]]] = []
        for preset_name in preset_names:
            try:
                simulation = Simulation(
                    cell=Cell.preset(preset_name),
                    model=config.model,
                    protocol=config.protocol,
                    environment=config.environment,
                    solver_config=config.solver_config,
                )
                results.append((preset_name, self.execution_service.execute(simulation)))
            except Exception as exc:
                results.append(
                    (preset_name, self._build_failed_run(exc, config.solver_config))
                )
        return results

    @staticmethod
    def _build_failed_run(exc: Exception, solver_config: Any) -> SimulationRun:
        error_message = f"{type(exc).__name__}: {exc}"
        return SimulationRun(
            result=Result({}),
            metadata=SimulationMetadata.create(
                solver_config=solver_config,
                success=False,
                convergence_reason=error_message,
                duration_s=0.0,
                duration_source="service_exception",
                protocol_steps=0,
                solver_iterations=0,
            ),
            errors=[
                SimulationError(
                    error_type=ErrorType.UNRECOGNIZED,
                    severity="critical",
                    message=error_message,
                    location="BatchExecutionService.run_presets",
                )
            ],
            diagnostics=ConvergenceDiagnostics.create(
                total_time_steps=0,
                problem_description="execution failed before result generation",
                telemetry_status="unavailable",
            ),
        )

    def run_parameter_variations(
        self,
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: list[Any],
        config: Any,
    ) -> list[tuple[Any, Optional[SimulationRun]]]:
        from battery_sim.application.services.sweep import ParameterSweepService

        baseline_simulation = Simulation(
            cell=baseline_cell,
            model=config.model,
            protocol=config.protocol,
            environment=config.environment,
            solver_config=config.solver_config,
        )
        target = "environment" if parameter_name == "temperature_C" else "cell"
        results = ParameterSweepService(self.execution_service).sweep_parameter(
            baseline_simulation,
            target,
            parameter_name,
            parameter_values,
            continue_on_error=True,
        )
        return [(value, run) for value, run, _, _ in results]
