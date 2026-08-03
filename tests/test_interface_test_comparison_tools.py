"""Fast interface tests for model-to-test comparison orchestration."""

import pytest

from battery_sim.core.convergence_diagnostics import ConvergenceDiagnostics
from battery_sim.core.result import Result
from battery_sim.core.model import Model
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation_metadata import SimulationMetadata
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.solver import SolverConfig
from battery_sim.interface.test_comparison_tools import ModelTestComparisonToolHandler
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class CapturingTraceBackend(SimulationBackend):
    def __init__(self):
        self.last_simulation = None

    def run(self, simulation, **solver_options):
        self.last_simulation = simulation
        time_s = [0.0, 5.0, 10.0]
        current = simulation.protocol.steps[0].current_A
        return SimulationRun(
            result=Result(
                {
                    Signal.VOLTAGE: TimeSeries(time_s, [4.1, 4.0, 3.9], "V"),
                    Signal.CURRENT: TimeSeries(time_s, [current] * 3, "A"),
                }
            ),
            metadata=SimulationMetadata.create(
                solver_config=simulation.solver_config,
                success=True,
                duration_s=0.01,
                protocol_steps=1,
                model=simulation.model.value,
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics.create(total_time_steps=3),
        )

    def supports_model(self, model):
        return True


def _handler():
    backend = CapturingTraceBackend()
    session = SimulationSession("trace comparison")
    handler = ModelTestComparisonToolHandler(
        backend=backend,
        session=session,
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )
    return handler, backend, session


def test_handler_builds_matching_cc_discharge_and_preserves_test_provenance():
    handler, backend, session = _handler()

    result = handler.compare_cc_discharge(
        preset_name="NMC_CHEN_LGM50",
        source="Arbin export / test campaign 42",
        test_id="CELL-07-1C-25C",
        time_s=[100.0, 105.0, 110.0],
        voltage_V=[4.1, 4.0, 3.9],
        applied_current_A=5.0,
        measured_current_A=[-5.0, -5.0, -5.0],
        current_sign_convention="discharge_negative",
        temperature_C=25.0,
        voltage_rmse_limit_V=0.01,
    )
    data = result.json_data

    assert data["type"] == "test_comparison"
    assert data["metrics"]["voltage_rmse_V"] == pytest.approx(0.0)
    assert data["metrics"]["current_rmse_A"] == pytest.approx(0.0)
    assert data["coverage"]["extrapolation_used"] is False
    assert data["test_provenance"]["source"] == "Arbin export / test campaign 42"
    assert data["test_provenance"]["test_id"] == "CELL-07-1C-25C"
    assert "simulation_provenance" in data
    assert data["evidence"]["parameter_fitting_performed"] is False
    assert data["evidence"]["initial_state_alignment"] == "assumed_unverified"
    assert data["assessment"]["acceptance_criterion"]["passed"] is True
    assert data["assessment"]["confidence"] == "low"
    assert data["assessment"]["decision_ready"] is False
    assert data["assessment"]["next_experiments"]
    assert backend.last_simulation.protocol.steps[0].current_A == 5.0
    assert backend.last_simulation.protocol.total_duration_s() == 10.0
    assert session.investigation_history[-1].investigation_type == "compare_test_data"


def test_handler_requires_discharge_positive_applied_current():
    handler, _, _ = _handler()

    with pytest.raises(ValueError, match="applied_current_A"):
        handler.compare_cc_discharge(
            preset_name="NMC_CHEN_LGM50",
            source="cycler",
            time_s=[0.0, 1.0],
            voltage_V=[4.1, 4.0],
            applied_current_A=-5.0,
        )
