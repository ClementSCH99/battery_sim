"""Regression tests derived from the MCP black-box investigation."""

import json

import pytest

from battery_sim.core.cell import Cell
from battery_sim.experimental.charging.strategies.builder import ChargingStrategyBuilder
from battery_sim.interfaces.presenters.result import ComparisonFormatter
from battery_sim.interfaces.python.question_interpreter import QuestionInterpreter


@pytest.mark.parametrize(
    ("question", "temperature", "c_rate"),
    [
        ("Decharge a 1C", None, 1.0),
        ("Decharge a 2C", None, 2.0),
        ("Decharge a C/2", None, 0.5),
        ("Decharge a 1 degrees C", None, None),
        ("Decharge a 25 C", None, 25.0),
    ],
)
def test_c_rate_is_not_interpreted_as_temperature(question, temperature, c_rate):
    interpretation = QuestionInterpreter().interpret(question)

    assert interpretation.value("temperature_C") == temperature
    assert interpretation.value("c_rate") == c_rate


def test_degree_temperature_remains_distinct_from_c_rate():
    interpretation = QuestionInterpreter().interpret("Decharge a 1 \N{DEGREE SIGN}C")

    assert interpretation.value("temperature_C") == 1.0
    assert interpretation.value("c_rate") is None


def test_compare_presets_rejects_duplicate_scenarios():
    from mcp_server import compare_presets

    payload = json.loads(compare_presets(["NMC_5AH", "NMC_5AH"]))

    assert payload["ok"] is False
    assert payload["response"]["error"]["code"] == "validation_error"


def test_critical_errors_are_minimized_in_comparisons():
    result = ComparisonFormatter.format_comparison(
        ["bad", "good"],
        {
            "critical_errors": {
                "type": "numeric",
                "values": {"bad": 1, "good": 0},
                "range": 1,
            }
        },
    )

    assert result.json_data["metrics"]["critical_errors"]["best"] == "good"


def test_preset_catalog_exposes_execution_and_fidelity_capabilities():
    from mcp_server import list_presets

    payload = json.loads(list_presets())
    presets = {item["name"]: item for item in payload["presets"]}

    assert presets["LCO_3AH"]["capabilities"]["supports_simulation"] is False
    assert presets["LFP_5AH"]["capabilities"]["simulation_fidelity"] == "chemistry_proxy_unscaled"
    assert presets["LFP_PRADA_2P3AH"]["capabilities"]["simulation_fidelity"] == "reference_parameterization"


def test_describe_api_matches_callable_split_range_parameters():
    from mcp_server import describe_api

    payload = json.loads(describe_api())
    tools = {tool["name"]: tool for tool in payload["tools"]}

    assert "voltage_range" not in tools["pack_sizing"]["parameters"]
    assert "voltage_range_min_V" in tools["pack_sizing"]["parameters"]
    assert "charge_current_min_A" in tools["optimize_charging"]["parameters"]
    assert tools["sensitivity_analysis"]["parameters"]["parameters"]["allowed_values"] == ["temperature_C"]


def test_unknown_charging_strategy_is_a_validation_error():
    cell = Cell.preset("NMC_CHEN_LGM50")

    with pytest.raises(ValueError, match="Unknown charging strategies"):
        ChargingStrategyBuilder.build(cell, ["not_a_strategy"])


def test_range_result_labels_synthetic_profile_in_primary_fields():
    from mcp_server import estimate_range

    payload = json.loads(
        estimate_range(
            preset_name="NMC_5AH",
            cycle_name="WLTP_CLASS3",
            peak_power_kW=100.0,
        )
    )

    assert payload["profile_name"] == "synthetic_wltp_class3"
    assert payload["profile_kind"] == "synthetic_normalized_power_trace"
    assert payload["regulatory_cycle"] is False
    assert payload["temperature_effect_applied"] is False


def test_discovery_and_validation_calls_are_recorded_in_session():
    from mcp_server import api, list_presets, run_simulation

    before = api.session.num_investigations()
    catalog = json.loads(list_presets())
    invalid = json.loads(run_simulation("NMC_5AH", duration_s=0.0))
    events = api.session.investigation_history[before:]

    assert catalog["ok"] is True
    assert invalid["ok"] is False
    assert [event.investigation_type for event in events] == [
        "list_presets",
        "run_simulation",
    ]
    assert [event.status for event in events] == ["success", "error"]
    assert all(event.event_id for event in events)
    assert len({event.event_id for event in events}) == 2


@pytest.mark.slow
def test_run_simulation_preserves_plan_fields_and_reports_coverage():
    from mcp_server import plan_experiment, run_simulation

    plan = json.loads(
        plan_experiment(
            question="Discharge NMC_CHEN_LGM50 at 1C with SPMe and voltage",
            requested_signals=["voltage"],
        )
    )
    arguments = dict(plan["execution"]["arguments"])
    arguments["duration_s"] = 30.0
    result = json.loads(run_simulation(**arguments))

    assert plan["ready_for_execution"] is True
    assert result["provenance"]["model"] == "single_particle_electrolyte"
    assert result["execution"]["requested_duration_s"] == 30.0
    assert 0.0 < result["execution"]["coverage_fraction"] <= 1.0
    assert "voltage" in result["signals"]
    assert result["signals"]["voltage"]["unit"] == "V"
    assert result["metrics"]["efficiency_percent"] is None
    assert result["preset_capability"]["simulation_fidelity"] == "reference_parameterization"

@pytest.mark.slow
def test_charging_strategies_produce_distinct_successful_stimuli_and_timings():
    from mcp_server import compare_charging_strategies

    payload = json.loads(
        compare_charging_strategies(
            preset_name="NMC_CHEN_LGM50",
            strategies=["gentle_0.5C", "standard_1C", "fast_2C"],
            n_cycles=1,
        )
    )
    rows = payload["strategies"]

    assert payload["ok"] is True
    assert [row["status"] for row in rows] == ["ok", "ok", "ok"]
    assert len({round(row["charge_time_min"], 6) for row in rows}) == 3
    assert all(row["resolved_protocol"]["steps"] for row in rows)
    first_currents = [row["resolved_protocol"]["steps"][0]["charge_current_A"] for row in rows]
    assert len(set(first_currents)) == 3

@pytest.mark.slow
def test_unidentifiable_aging_never_produces_lifetime_or_warranty_verdict():
    from mcp_server import api, predict_lifetime, warranty_analysis

    lifetime = json.loads(
        predict_lifetime(
            preset_name="NMC_OKANE_AGING",
            n_representative_cycles=3,
        )
    )
    before_warranty = api.session.num_investigations()
    warranty = json.loads(warranty_analysis(preset_name="NMC_OKANE_AGING"))

    assert lifetime["projection"]["status"] == "insufficient_evidence"
    assert lifetime["estimated_years_to_eol"] is None
    assert lifetime["estimated_cycles_to_eol"] is None
    assert lifetime["projection"]["quality_reasons"]
    assert warranty["type"] == "warranty_analysis_error"
    assert warranty["passes_warranty"] is None
    assert warranty["risk_level"] is None
    assert warranty["decision_ready"] is False
    assert warranty["ok"] is False

    warranty_events = api.session.investigation_history[before_warranty:]
    roots = [event for event in warranty_events if event.investigation_type == "warranty_analysis"]
    assert len(roots) == 1
    root = roots[0]
    assert root.status == "error"
    assert any(
        event.investigation_type == "predict_lifetime"
        and event.parent_event_id == root.event_id
        for event in warranty_events
    )
