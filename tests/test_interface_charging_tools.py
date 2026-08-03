"""Fast contracts for the extracted charging interface handler."""

from battery_sim.core.simulation import ConvergenceDiagnostics
from battery_sim.core.experiment import Model
from battery_sim.core.result import Result
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationMetadata
from battery_sim.core.simulation import SimulationRun
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.interfaces.python.charging_tools import ChargingToolHandler
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class ChargeBackend(SimulationBackend):
    def __init__(self):
        self.simulations = []

    def run(self, simulation, **solver_options):
        self.simulations.append(simulation)
        current = simulation.protocol.steps[0].charge_current_A
        duration = 3600.0 / current
        return SimulationRun(
            result=Result(
                {
                    Signal.VOLTAGE: TimeSeries(
                        time_s=[0.0, duration],
                        values=[3.2, simulation.protocol.steps[0].cutoff_voltage_V],
                        unit="V",
                    )
                }
            ),
            metadata=SimulationMetadata.create(
                solver_config=simulation.solver_config,
                duration_s=0.01,
                success=True,
                backend_name="charge-test",
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics.create(total_time_steps=2),
        )

    def supports_model(self, model):
        return True


def _handler():
    backend = ChargeBackend()
    session = SimulationSession(name="charging handler test")
    return (
        ChargingToolHandler(
            backend=backend,
            session=session,
            default_model=Model.SPM,
        ),
        backend,
        session,
    )


def test_rate_screen_observes_time_and_does_not_invent_aging():
    handler, backend, session = _handler()

    result = handler.optimize_charging("LFP_5AH", (1.0, 5.0), 3, 25.0)

    assert result.json_data["optimal_params"]["charge_current_A"] == 5.0
    assert result.json_data["optimal_params"]["capacity_fade_per_cycle"] is None
    assert result.json_data["evidence"]["not_observed"] == [
        "capacity fade",
        "round-trip efficiency",
        "lithium plating",
    ]
    assert all(simulation.solver_config.initial_soc == 0.2 for simulation in backend.simulations)
    assert session.investigation_history[-1].investigation_type == "optimize_charging"


def test_rate_screen_skips_currents_above_preset_limit():
    handler, backend, _ = _handler()

    result = handler.optimize_charging("LFP_5AH", (5.0, 10.0), 2)

    rows = {row["charge_current_A"]: row for row in result.json_data["all_results"]}
    assert rows[5.0]["status"] == "ok"
    assert rows[10.0]["status"] == "outside_preset_limit"
    assert len(backend.simulations) == 1


def test_invalid_rate_screen_inputs_fail_early():
    handler, _, _ = _handler()

    import pytest

    with pytest.raises(ValueError):
        handler.optimize_charging("LFP_5AH", (5.0, 1.0), 3)
