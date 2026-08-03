"""Evidence-level tests for conservative bilingual question extraction."""

from battery_sim.interfaces.python.question_interpreter import QuestionInterpreter


def test_french_question_extracts_only_supported_exact_vocabulary():
    question = (
        "Simule une décharge de NMC_CHEN_LGM50 à -10 °C avec SPMe, "
        "la tension et la concentration électrolyte."
    )

    interpretation = QuestionInterpreter().interpret(question)

    assert interpretation.value("preset_name") == "NMC_CHEN_LGM50"
    assert interpretation.value("investigation_type") == "cc_discharge"
    assert interpretation.value("temperature_C") == -10.0
    assert interpretation.value("model") == "single_particle_electrolyte"
    assert interpretation.value("requested_signals") == [
        "voltage",
        "electrolyte_concentration",
    ]


def test_every_evidence_span_is_a_literal_question_fragment():
    question = "Run a DFN discharge of LFP_PRADA_2P3AH at 15 C and report voltage."

    interpretation = QuestionInterpreter().interpret(question)

    for evidence in interpretation.fields.values():
        assert question[evidence.start:evidence.end] == evidence.text


def test_unsupported_qualitative_temperature_is_not_guessed():
    interpretation = QuestionInterpreter().interpret(
        "Run NMC_CHEN_LGM50 in very cold conditions."
    )

    assert interpretation.value("temperature_C") is None


def test_c_rate_is_not_misread_as_temperature():
    interpretation = QuestionInterpreter().interpret(
        "Run a 1C discharge and report voltage."
    )

    assert interpretation.value("temperature_C") is None


def test_cell_temperature_does_not_duplicate_generic_temperature_signal():
    interpretation = QuestionInterpreter().interpret(
        "Report cell temperature during the discharge."
    )

    assert interpretation.value("requested_signals") == ["cell_temperature"]


def test_unknown_commercial_cell_is_not_mapped_to_a_reference_preset():
    interpretation = QuestionInterpreter().interpret(
        "Discharge a commercial 21700 cell at 25 C."
    )

    assert interpretation.value("preset_name") is None
