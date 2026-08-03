"""Build execution metadata, physical errors and diagnostics for PyBaMM runs."""

from dataclasses import dataclass
from typing import Any

import pybamm

from battery_sim.backend.parameter_mapper import resolve_parameter_mapping
from battery_sim.core.convergence_diagnostics import ConvergenceDiagnostics
from battery_sim.core.result import Result
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_error import ErrorDetector, SimulationError
from battery_sim.core.simulation_metadata import SimulationMetadata


@dataclass(frozen=True)
class PyBaMMObservability:
    metadata: SimulationMetadata
    errors: list[SimulationError]
    diagnostics: ConvergenceDiagnostics


class PyBaMMObservabilityBuilder:
    """Translate solver termination and result checks into core observability."""

    def build(
        self,
        result: Result,
        solution: Any,
        simulation: Simulation,
        elapsed_seconds: float,
    ) -> PyBaMMObservability:
        telemetry = self.extract_telemetry(solution, elapsed_seconds)
        time_data = solution["Time [s]"].data
        time_points = len(time_data) if time_data is not None else 0
        parameter_mapping = resolve_parameter_mapping(simulation.cell)
        metadata = SimulationMetadata.create(
            solver_config=simulation.solver_config,
            solver_iterations=time_points,
            solver_iterations_kind="time_points",
            success=telemetry["success"],
            convergence_reason=telemetry["convergence_reason"],
            duration_s=telemetry["duration_s"],
            duration_source=telemetry["duration_source"],
            protocol_steps=len(simulation.protocol.steps),
            backend_name="PyBaMM",
            backend_version=pybamm.__version__,
            model=simulation.model.value,
            cell_chemistry=simulation.cell.chemistry,
            parameter_set=parameter_mapping.parameter_set,
            parameter_mapping_policy=parameter_mapping.mapping_policy,
        )
        return PyBaMMObservability(
            metadata=metadata,
            errors=ErrorDetector.detect_all(
                result,
                cell=simulation.cell,
                model=simulation.model,
            ),
            diagnostics=ConvergenceDiagnostics.create(
                total_time_steps=time_points,
                avg_newton_iterations=None,
                max_newton_iterations=None,
                min_newton_iterations=None,
                problem_description=(
                    "Newton iteration telemetry unavailable in current PyBaMM integration"
                ),
                telemetry_status="unavailable",
            ),
        )

    @staticmethod
    def extract_telemetry(solution: Any, elapsed_seconds: float) -> dict:
        termination = str(getattr(solution, "termination", "unknown")).strip()
        termination = termination or "unknown"
        total_time = getattr(getattr(solution, "total_time", None), "value", None)
        failure_markers = ("error", "fail", "infeasible", "singular", "diverg")
        return {
            "success": not any(
                marker in termination.lower() for marker in failure_markers
            ),
            "convergence_reason": termination,
            "duration_s": total_time if total_time is not None else elapsed_seconds,
            "duration_source": (
                "pybamm_total_time" if total_time is not None else "wall_clock"
            ),
        }
