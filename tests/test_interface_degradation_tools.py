"""Fast contracts for experimental lifetime and warranty handlers."""

from battery_sim.core.convergence_diagnostics import ConvergenceDiagnostics
from battery_sim.core.model import Model
from battery_sim.core.result import Result
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation_metadata import SimulationMetadata
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.interface.degradation_tools import DegradationToolHandler
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class CyclingBackend(SimulationBackend):
    def __init__(self, capacities):
        self.capacities = capacities
        self.last_simulation = None

    def run(self, simulation, **solver_options):
        self.last_simulation = simulation
        return SimulationRun(
            result=Result(
                {
                    Signal.CYCLE_DISCHARGE_CAPACITY: TimeSeries(
                        time_s=list(range(1, len(self.capacities) + 1)),
                        values=list(self.capacities),
                        unit="Ah",
                    )
                }
            ),
            metadata=SimulationMetadata.create(
                solver_config=simulation.solver_config,
                duration_s=0.01,
                success=True,
                backend_name="synthetic-cycling-backend",
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics.create(
                total_time_steps=len(self.capacities)
            ),
        )

    def supports_model(self, model):
        return True


def _handler(capacities=(5.0, 4.99, 4.98, 4.97, 4.96)):
    backend = CyclingBackend(capacities)
    session = SimulationSession(name="degradation handler test")
    return (
        DegradationToolHandler(
            backend=backend,
            session=session,
            default_model=Model.SPM,
        ),
        backend,
        session,
    )


def test_lifetime_separates_observation_fit_and_unvalidated_projection():
    handler, backend, session = _handler()

    result = handler.predict_lifetime(
        "LFP_5AH",
        usage_profile={"daily_charge_cycles": 2.0, "storage_soc": 0.6},
        n_representative_cycles=5,
    )

    assert result.json_data["projection"]["status"] == "linear_extrapolation_available"
    assert result.json_data["projection"]["observed_cycle_count"] == 5
    assert result.json_data["evidence"]["validation_status"] == (
        "not validated against cell test data"
    )
    assert result.json_data["usage_profile"]["daily_charge_cycles"] == 2.0
    assert "Evidence limit" in result.markdown_text
    assert backend.last_simulation.protocol.steps[0].cutoff_voltage_V == 3.65
    assert session.investigation_history[-1].investigation_type == "predict_lifetime"


def test_non_declining_capacity_does_not_create_a_fake_million_cycle_life():
    handler, _, _ = _handler((5.0, 5.0, 5.0, 5.0))

    result = handler.predict_lifetime("LFP_5AH", n_representative_cycles=4)

    assert result.json_data["estimated_cycles_to_eol"] is None
    assert result.json_data["estimated_years_to_eol"] is None
    assert result.json_data["projection"]["status"] == "no_decline_observed"


def test_warranty_uses_profile_and_first_expiring_time_or_distance_limit():
    handler, _, session = _handler()

    result = handler.warranty_analysis(
        "LFP_5AH",
        warranty_years=8.0,
        warranty_km=1000.0,
        usage_profile={"daily_km": 100.0, "daily_charge_cycles": 2.0},
    )

    assert result.json_data["type"] == "warranty_analysis"
    assert result.json_data["limiting_condition"] == "distance"
    assert result.json_data["evaluation_years"] < 0.03
    assert result.json_data["usage_profile"]["daily_km"] == 100.0
    assert result.json_data["evidence"]["status"] == "screening only"
    assert "Decision limit" in result.markdown_text
    assert session.investigation_history[-1].investigation_type == "warranty_analysis"


def test_insufficient_cycles_return_explicit_error_without_execution():
    handler, backend, _ = _handler()

    result = handler.predict_lifetime("LFP_5AH", n_representative_cycles=1)

    assert result.json_data["type"] == "lifetime_prediction_error"
    assert backend.last_simulation is None
    assert result.interpretation_hints
