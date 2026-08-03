"""Fast contracts for cell-to-pack-to-vehicle screening handlers."""

import pytest

from battery_sim.core.simulation import ConvergenceDiagnostics
from battery_sim.core.result import Result
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationMetadata
from battery_sim.core.simulation import SimulationRun
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.interfaces.python.vehicle_tools import VehicleToolHandler
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


class EnergyBackend(SimulationBackend):
    def __init__(self, cell_energy_Wh=1.0):
        self.cell_energy_Wh = cell_energy_Wh
        self.last_simulation = None

    def run(self, simulation, **solver_options):
        self.last_simulation = simulation
        return SimulationRun(
            result=Result(
                {
                    Signal.ENERGY: TimeSeries(
                        time_s=[0.0, 1.0],
                        values=[0.0, self.cell_energy_Wh],
                        unit="Wh",
                    )
                }
            ),
            metadata=SimulationMetadata.create(
                solver_config=simulation.solver_config,
                duration_s=0.01,
                success=True,
                backend_name="energy-test-backend",
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics.create(total_time_steps=2),
        )

    def supports_model(self, model):
        return True


def _handler():
    backend = EnergyBackend()
    session = SimulationSession(name="vehicle handler test")
    return (
        VehicleToolHandler(
            session=session,
        ),
        backend,
        session,
    )


def test_pack_sizing_keeps_missing_packaging_as_unknown():
    handler, _, _ = _handler()

    result = handler.pack_sizing("NMC_CHEN_LGM50", target_energy_kWh=60.0)

    assert result.json_data["configuration"]["pack_energy_kWh"] >= 60.0
    assert result.json_data["physical_metrics"]["pack_weight_kg"] is None
    assert result.json_data["physical_metrics"]["pack_cost_usd"] is None
    assert result.json_data["data_quality"]["mass"] == "missing"
    assert "N/A" in result.markdown_text


def test_cell_selection_derives_pack_energy_from_explicit_vehicle_assumptions():
    handler, _, session = _handler()

    result = handler.cell_selection(range_km=400.0, power_kW=150.0)

    assert result.json_data["derived_target_energy_kWh"] == pytest.approx(80.0)
    assert result.json_data["assumptions"]["reference_consumption_kWh_per_km"] == 0.18
    reference = next(
        ranking
        for ranking in result.json_data["rankings"]
        if ranking["preset_name"] == "NMC_CHEN_LGM50"
    )
    assert reference["meets_requirements"] is False
    assert reference["pack_config"]["system_weight_kg"] is None
    assert session.investigation_history[-1].investigation_type == "cell_selection_wizard"


def test_range_distributes_vehicle_power_and_integrates_pack_profile():
    handler, backend, session = _handler()

    result = handler.estimate_range(
        "LFP_5AH",
        n_series=96,
        n_parallel=40,
        vehicle_mass_kg=1800.0,
        peak_power_kW=150.0,
    )

    assert result.json_data["power_scaling"]["per_cell_peak_profile_W"] == pytest.approx(
        150000.0 / (96 * 40)
    )
    assert result.json_data["energy"]["energy_per_cycle_kWh"] > 0
    assert result.json_data["energy"]["usable_pack_energy_kWh"] == pytest.approx(
        96 * 40 * 3.2 * 5.0 / 1000.0 * 0.9
    )
    assert result.json_data["assumptions"]["temperature_effect"].startswith("not modeled")
    assert session.investigation_history[-1].investigation_type == "estimate_range"


def test_pack_sizing_rejects_reversed_voltage_window():
    handler, _, _ = _handler()

    with pytest.raises(ValueError, match="min_V"):
        handler.pack_sizing("LFP_5AH", voltage_range=(400.0, 300.0))


def test_range_rejects_pack_that_cannot_supply_requested_peak_power():
    handler, backend, session = _handler()

    result = handler.estimate_range(
        "LFP_5AH",
        n_series=48,
        n_parallel=2,
        peak_power_kW=50.0,
    )

    assert result.json_data["type"] == "range_estimation_error"
    assert "exceeds" in result.json_data["error"]
    assert backend.last_simulation is None
    assert session.investigation_history[-1].investigation_type == "estimate_range"
