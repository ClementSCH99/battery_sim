"""Canonical parameter-sweep orchestration."""

from dataclasses import replace
from typing import Any, Optional

from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationRun
from battery_sim.core.services.execution import SimulationExecutionService


class ParameterSweepService:
    """Vary cell or environment dataclass fields on a baseline simulation."""

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
            raise ValueError("ParameterSweepService requires either execution_service or backend")

    def sweep_parameter(
        self,
        baseline_simulation: Simulation,
        target: str,
        parameter_name: str,
        values: list[Any],
        continue_on_error: bool = False,
    ) -> list[tuple[Any, Optional[SimulationRun], dict[str, Any], dict[str, Any]]]:
        results = []
        for value in values:
            modified_cell = baseline_simulation.cell
            modified_environment = baseline_simulation.environment
            if target == "cell":
                modified_cell = replace(modified_cell, **{parameter_name: value})
                cell_overrides = {parameter_name: value}
                environment_overrides = {}
            elif target == "environment":
                modified_environment = replace(
                    modified_environment, **{parameter_name: value}
                )
                cell_overrides = {}
                environment_overrides = {parameter_name: value}
            else:
                raise ValueError(f"Unsupported sweep target: {target}")

            simulation = replace(
                baseline_simulation,
                cell=modified_cell,
                environment=modified_environment,
            )
            try:
                run = self.execution_service.execute(simulation)
            except Exception:
                if not continue_on_error:
                    raise
                run = None
            results.append((value, run, cell_overrides, environment_overrides))
        return results

    def multi_parameter_sweep(
        self,
        baseline_simulation: Simulation,
        parameters: dict[str, list[Any]],
    ) -> list[tuple[dict[str, Any], SimulationRun, dict[str, Any], dict[str, Any]]]:
        cell_parameters: dict[str, list[Any]] = {}
        environment_parameters: dict[str, list[Any]] = {}
        for name, values in parameters.items():
            if name.startswith("cell::"):
                cell_parameters[name[6:]] = values
            elif name.startswith("environment::"):
                environment_parameters[name[13:]] = values
            else:
                raise ValueError(
                    f"Parameter {name} must start with 'cell::' or 'environment::'"
                )

        cell_combinations = self._combinations(cell_parameters)
        environment_combinations = self._combinations(environment_parameters)
        results = []
        for cell_overrides in cell_combinations:
            for environment_overrides in environment_combinations:
                simulation = replace(
                    baseline_simulation,
                    cell=(
                        replace(baseline_simulation.cell, **cell_overrides)
                        if cell_overrides
                        else baseline_simulation.cell
                    ),
                    environment=(
                        replace(baseline_simulation.environment, **environment_overrides)
                        if environment_overrides
                        else baseline_simulation.environment
                    ),
                )
                run = self.execution_service.execute(simulation)
                values = {**cell_overrides, **environment_overrides}
                results.append((values, run, cell_overrides, environment_overrides))
        return results

    @classmethod
    def _combinations(cls, parameters: dict[str, list[Any]]) -> list[dict[str, Any]]:
        if not parameters:
            return [{}]
        items = list(parameters.items())
        name, values = items[0]
        remaining = cls._combinations(dict(items[1:]))
        return [{name: value, **combo} for value in values for combo in remaining]
