"""Fast contract tests for the extracted single-simulation interface handler."""

import pytest

from battery_sim.core.simulation import ConvergenceDiagnostics
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.core.result import Result
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationMetadata
from battery_sim.core.simulation import SimulationRun
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import SolverConfig
from battery_sim.interfaces.python.simulation_tool import SimulationToolHandler


class CapturingBackend(SimulationBackend):
    """Backend test double that records the request without invoking PyBaMM."""

    def __init__(self) -> None:
        self.last_simulation = None
        self.last_run = None

    def run(self, simulation, **solver_options) -> SimulationRun:
        self.last_simulation = simulation
        self.last_run = SimulationRun(
            result=Result({}),
            metadata=SimulationMetadata.create(
                solver_config=simulation.solver_config,
                duration_s=0.01,
                backend_name="test-backend",
                backend_version="1.0",
                model=simulation.model.value,
                cell_chemistry=simulation.cell.chemistry,
                parameter_set="test-parameters",
                parameter_mapping_policy="exact_match",
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics.create(total_time_steps=2),
        )
        return self.last_run

    def supports_model(self, model: Model) -> bool:
        return True


@pytest.fixture
def handler():
    backend = CapturingBackend()
    session = SimulationSession(name="handler test")
    tool = SimulationToolHandler(
        backend=backend,
        session=session,
        default_protocol=Protocol.cc(current_A=1.0, duration_s=60.0),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(initial_soc=0.8),
    )
    return tool, backend, session


def test_handler_builds_request_and_records_provenance(handler):
    tool, backend, session = handler

    response = tool.run(
        "NMC_CHEN_LGM50",
        current_A=2.5,
        duration_s=120.0,
        temperature_C=15.0,
    )

    simulation = backend.last_simulation
    assert simulation.cell.chemistry == "NMC-CHEN"
    assert simulation.protocol.steps[0].current_A == 2.5
    assert simulation.protocol.steps[0].duration_s() == 120.0
    assert simulation.environment.ambient_temperature_C == 15.0
    assert simulation.solver_config.initial_soc == 0.8
    assert response.json_data["provenance"] == {
        "backend": "test-backend",
        "backend_version": "1.0",
        "model": Model.SPM.value,
        "parameter_set": "test-parameters",
        "cell_chemistry": "NMC-CHEN",
    }
    assert response.json_data["simulation_id"] == backend.last_run.metadata.simulation_id
    assert "parameters=test-parameters" in response.markdown_text
    assert session.investigation_history[-1].investigation_type == "run_simulation"


def test_partial_override_preserves_default_current(handler):
    tool, backend, _ = handler

    tool.run("NMC_CHEN_LGM50", duration_s=30.0)

    step = backend.last_simulation.protocol.steps[0]
    assert step.current_A == 1.0
    assert step.duration_s() == 30.0


def test_overrides_require_constant_current_default():
    tool = SimulationToolHandler(
        backend=CapturingBackend(),
        session=SimulationSession(name="invalid default"),
        default_protocol=Protocol.rest(duration_s=60.0),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )

    with pytest.raises(ValueError, match="ConstantCurrent"):
        tool.run("NMC_CHEN_LGM50", current_A=1.0)
