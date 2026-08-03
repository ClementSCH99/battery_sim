"""Fast contract tests for comparison and sensitivity interface handlers."""

from unittest.mock import Mock

import pytest

from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.interfaces.presenters.result import ComparisonFormatter
from battery_sim.core.simulation import SimulationBackend
from battery_sim.application.session import SimulationSession
from battery_sim.application.services import SensitivityResult
from battery_sim.core.experiment import SolverConfig
from battery_sim.interfaces.python.investigation_tools import EVAssumptions, InvestigationToolHandler


def _handler(*, comparison_service=None, sensitivity_service=None):
    return InvestigationToolHandler(
        backend=Mock(spec=SimulationBackend),
        session=SimulationSession(name="investigation handler test"),
        default_protocol=Protocol.cc(current_A=1.0, duration_s=60.0),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(initial_soc=0.8),
        comparison_service=comparison_service,
        sensitivity_service=sensitivity_service,
    )


def test_reference_presets_do_not_invent_packaging_metrics_or_winners():
    scenarios = ["LFP_PRADA_2P3AH", "NMC_CHEN_LGM50"]
    ev_metrics = EVAssumptions.compute(scenarios)

    result = ComparisonFormatter.format_comparison_with_ev(
        scenarios,
        metrics_dict={},
        ev_metrics=ev_metrics,
        ragone_data=EVAssumptions.ragone(scenarios),
    )

    assert ev_metrics["LFP_PRADA_2P3AH"]["energy_density_Wh_per_kg"] is None
    assert ev_metrics["NMC_CHEN_LGM50"]["cost_per_kWh"] is None
    assert EVAssumptions.ragone(scenarios) == {}
    assert "N/A" in result.markdown_text
    assert "Gravimetric Energy Density" not in result.json_data["best_for"]
    assert "Cost per kWh" not in result.json_data["best_for"]


def test_comparison_preserves_zero_celsius_and_labels_evidence():
    comparison_service = Mock()
    comparison_service.compare_presets.return_value = {"metrics": {}}
    handler = _handler(comparison_service=comparison_service)

    result = handler.compare_presets(["LFP_5AH", "NMC_5AH"], environment_temp_C=0.0)

    config = comparison_service.compare_presets.call_args.args[1]
    assert config.environment.ambient_temperature_C == 0.0
    assert result.json_data["evidence"]["metrics"] == "derived from SimulationRun values"
    assert "Evidence note" in result.markdown_text


def test_unsupported_sensitivity_parameter_is_rejected_explicitly():
    handler = _handler(sensitivity_service=Mock())

    with pytest.raises(ValueError, match="internal_resistance_Ohm"):
        handler.sensitivity_analysis(
            "NMC_CHEN_LGM50",
            ["internal_resistance_Ohm"],
        )


def test_capacity_sensitivity_range_is_relative_to_selected_cell():
    cell = Cell.preset("LFP_PRADA_2P3AH")

    ranges = InvestigationToolHandler._parameter_ranges(cell)

    assert ranges["nominal_capacity_Ah"] == pytest.approx(
        [1.84, 2.07, 2.3, 2.53, 2.76]
    )


def test_sensitivity_uses_requested_baseline_ambient_temperature():
    sensitivity_service = Mock()
    sensitivity_service.analyze_single_parameter.return_value = SensitivityResult(
        parameter_name="nominal_capacity_Ah",
        parameter_values=[4.0, 5.0, 6.0],
        metric_name="peak_power_W",
        metric_values=[10.0, 11.0, 12.0],
    )
    handler = _handler(sensitivity_service=sensitivity_service)

    result = handler.sensitivity_analysis(
        "LFP_5AH",
        ["nominal_capacity_Ah"],
        temperature_C=10.0,
    )

    config = sensitivity_service.analyze_single_parameter.call_args.args[3]
    assert config.environment.ambient_temperature_C == 10.0
    assert result.json_data["baseline_ambient_temperature_C"] == 10.0
