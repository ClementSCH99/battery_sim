# battery_sim/backend/pybamm_backend.py
import pybamm
import time

from battery_sim.backend.pybamm_observability import PyBaMMObservabilityBuilder
from battery_sim.backend.pybamm_problem_builder import (
    PyBaMMProblemBuilder,
    translate_protocol_to_pybamm,
)
from battery_sim.backend.pybamm_result_extractor import PyBaMMResultExtractor
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.protocol import Protocol
from battery_sim.core.result import Result
from battery_sim.core.solver import SolverConfig

from battery_sim.core.simulation import SimulationRun

class PyBaMMBackend(SimulationBackend):

    def run(self, simulation: Simulation, **kwargs) -> SimulationRun:
        """
        Execute simulation and return complete SimulationRun with observability.
        
        This method orchestrates the simulation workflow without handling details.
        """
        solution, elapsed_seconds = self._execute_simulation(simulation, **kwargs)
        result = self._extract_result(solution, protocol=simulation.protocol)
        observability = PyBaMMObservabilityBuilder().build(
            result,
            solution,
            simulation,
            elapsed_seconds,
        )
        return SimulationRun(
            result=result,
            metadata=observability.metadata,
            errors=observability.errors,
            diagnostics=observability.diagnostics,
        )
    
    def _execute_simulation(self, simulation: Simulation, **kwargs) -> tuple:
        """Build and solve one PyBaMM problem, returning solution and wall time."""
        problem = PyBaMMProblemBuilder().build(simulation)
        pybamm_simulation = pybamm.Simulation(
            problem.model,
            experiment=problem.experiment,
            parameter_values=problem.parameters,
            solver=problem.solver,
            **kwargs,
        )
        started = time.perf_counter()
        solution = pybamm_simulation.solve(
            initial_soc=simulation.solver_config.initial_soc
        )
        return solution, time.perf_counter() - started

    @staticmethod
    def _validate_parameter_set_capabilities(simulation: Simulation) -> None:
        """Compatibility delegate to the focused PyBaMM problem builder."""
        PyBaMMProblemBuilder.validate_capabilities(simulation)

    def _extract_result(self, solution, protocol: Protocol = None) -> Result:
        """Compatibility delegate to the focused solution extractor."""
        return PyBaMMResultExtractor().extract(solution, protocol)

    def _extract_solution_telemetry(self, solution, elapsed_seconds: float) -> dict:
        """Compatibility delegate to focused PyBaMM observability."""
        return PyBaMMObservabilityBuilder.extract_telemetry(
            solution,
            elapsed_seconds,
        )

    def _build_observability_data(
        self,
        result: Result,
        solution,
        simulation: Simulation,
        elapsed_seconds: float,
    ) -> dict:
        """Compatibility dictionary for older private callers."""
        built = PyBaMMObservabilityBuilder().build(
            result,
            solution,
            simulation,
            elapsed_seconds,
        )
        return {
            "metadata": built.metadata,
            "errors": built.errors,
            "diagnostics": built.diagnostics,
        }

    def _build_model(self, model: Model, environment: Environment, degradation=None):
        """Compatibility delegate to the focused PyBaMM problem builder."""
        return PyBaMMProblemBuilder.build_model(model, environment, degradation)

    def _build_experiment(self, simulation: Simulation):
        """Compatibility delegate to the focused PyBaMM problem builder."""
        return PyBaMMProblemBuilder.build_experiment(simulation)

    def _build_solver(self, solver_config: SolverConfig):
        """Compatibility delegate to the focused PyBaMM problem builder."""
        return PyBaMMProblemBuilder.build_solver(solver_config)

    def _build_parameters(self, cell: Cell, environment: Environment):
        """Compatibility delegate to the focused PyBaMM problem builder."""
        return PyBaMMProblemBuilder.build_parameters(cell, environment)

    def supports_model(self, model: Model) -> bool:
         return model  in {Model.SPM, Model.SPMe, Model.DFN}

        
