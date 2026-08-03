"""Unit contracts for PyBaMM execution observability."""

from types import SimpleNamespace

from battery_sim.infrastructure.pybamm.pybamm_observability import PyBaMMObservabilityBuilder
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.core.result import Result
from battery_sim.core.simulation import Simulation
from battery_sim.core.experiment import SolverConfig
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class Variable:
    def __init__(self, data):
        self.data = data


class Solution(dict):
    termination = "final time"
    total_time = SimpleNamespace(value=0.25)


def test_observability_preserves_solver_and_parameter_provenance():
    simulation = Simulation(
        cell=Cell.preset("LFP_5AH"),
        model=Model.SPM,
        protocol=Protocol.cc(1.0, 60.0),
        environment=Environment(25.0),
        solver_config=SolverConfig(),
    )
    result = Result(
        {
            Signal.VOLTAGE: TimeSeries([0.0, 60.0], [3.3, 3.2], "V"),
            Signal.CURRENT: TimeSeries([0.0, 60.0], [1.0, 1.0], "A"),
        }
    )

    built = PyBaMMObservabilityBuilder().build(
        result,
        Solution({"Time [s]": Variable([0.0, 60.0])}),
        simulation,
        elapsed_seconds=9.0,
    )

    assert built.metadata.success is True
    assert built.metadata.duration_s == 0.25
    assert built.metadata.duration_source == "pybamm_total_time"
    assert built.metadata.parameter_set == "Prada2013"
    assert built.metadata.backend_name == "PyBaMM"
    assert built.diagnostics.total_time_steps == 2


def test_telemetry_marks_explicit_failure_termination():
    solution = Solution()
    solution.termination = "solver failed: singular Jacobian"
    solution.total_time = None

    telemetry = PyBaMMObservabilityBuilder.extract_telemetry(solution, 1.5)

    assert telemetry["success"] is False
    assert telemetry["duration_s"] == 1.5
    assert telemetry["duration_source"] == "wall_clock"
