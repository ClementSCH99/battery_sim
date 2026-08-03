"""Fast contract tests for non-executing electrochemical experiment plans."""

from battery_sim.interface.planning_tools import ExperimentPlanningToolHandler


def test_missing_cell_is_reported_instead_of_guessed():
    result = ExperimentPlanningToolHandler().create(question="Measure voltage response")

    assert result.json_data["status"] == "needs_input"
    assert result.json_data["ready_for_execution"] is False
    assert result.json_data["missing_inputs"] == ["preset_name"]


def test_complete_bulk_discharge_plan_is_reviewable_but_not_executed():
    result = ExperimentPlanningToolHandler().create(
        question="Characterize the 1C discharge curve",
        preset_name="LFP_PRADA_2P3AH",
        temperature_C=25.0,
    )
    data = result.json_data

    assert data["status"] == "draft_ready"
    assert data["ready_for_execution"] is True
    assert data["requires_confirmation"] is True
    assert data["configuration"]["protocol"]["current_A"] == 2.3
    assert data["configuration"]["model"] == "single_particle"
    assert data["execution"]["direct_core_tool_supported"] is True
    assert data["execution"]["tool"] == "run_simulation"
    assert data["execution"]["arguments"] == {
        "preset_name": "LFP_PRADA_2P3AH",
        "current_A": 2.3,
        "duration_s": 3600.0,
        "temperature_C": 25.0,
    }
    assert "result" not in data


def test_electrolyte_signal_selects_spme_and_blocks_simple_execution_adapter():
    result = ExperimentPlanningToolHandler().create(
        question="Inspect electrolyte depletion",
        preset_name="NMC_CHEN_LGM50",
        requested_signals=["voltage", "electrolyte_concentration"],
    )
    data = result.json_data

    assert data["configuration"]["model"] == "single_particle_electrolyte"
    assert "electrolyte" in data["model_rationale"].lower()
    assert data["execution"]["direct_core_tool_supported"] is False
    assert data["execution"]["arguments"] is None


def test_thermal_signal_proposes_lumped_thermal_mode():
    result = ExperimentPlanningToolHandler().create(
        question="Estimate cell temperature rise",
        preset_name="NMC_CHEN_LGM50",
        requested_signals=["voltage", "cell_temperature"],
    )

    assert result.json_data["configuration"]["thermal_mode"] == "lumped"
    assert any(
        item["field"] == "thermal_mode"
        for item in result.json_data["proposed_defaults"]
    )


def test_incompatible_explicit_model_is_rejected():
    handler = ExperimentPlanningToolHandler()

    try:
        handler.create(
            question="Inspect electrolyte depletion",
            preset_name="NMC_CHEN_LGM50",
            model="SPM",
            requested_signals=["electrolyte_concentration"],
        )
    except ValueError as exc:
        assert "SPMe or DFN" in str(exc)
    else:
        raise AssertionError("Expected an incompatible-model error")


def test_plan_ids_are_unique():
    handler = ExperimentPlanningToolHandler()

    first = handler.create(question="First plan").json_data["plan_id"]
    second = handler.create(question="Second plan").json_data["plan_id"]

    assert first != second


def test_question_fields_are_extracted_with_traceable_evidence():
    question = (
        "Simule une décharge de NMC_CHEN_LGM50 à -10 °C avec SPMe, "
        "la tension et la concentration électrolyte."
    )

    data = ExperimentPlanningToolHandler().create(question=question).json_data

    assert data["status"] == "draft_ready"
    assert data["ready_for_execution"] is True
    assert data["configuration"]["preset_name"] == "NMC_CHEN_LGM50"
    assert data["configuration"]["ambient_temperature_C"] == -10.0
    assert data["configuration"]["model"] == "single_particle_electrolyte"
    assert data["traceability"]["resolved_fields"]["preset_name"]["source"] == "question_exact_match"
    assert data["traceability"]["conflicts"] == []


def test_explicit_argument_conflicting_with_question_is_never_silent():
    data = ExperimentPlanningToolHandler().create(
        question="Décharge NMC_CHEN_LGM50 à 25 C",
        preset_name="LFP_PRADA_2P3AH",
    ).json_data

    assert data["status"] == "conflict"
    assert data["requires_confirmation"] is True
    assert data["traceability"]["conflicts"] == [
        {
            "field": "preset_name",
            "explicit_value": "LFP_PRADA_2P3AH",
            "question_value": "NMC_CHEN_LGM50",
            "question_evidence": "NMC_CHEN_LGM50",
        }
    ]
