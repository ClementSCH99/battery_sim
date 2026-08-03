"""Tests for conservative model-validation evidence language."""

from battery_sim.application.services.evidence import ModelTestEvidenceService
from battery_sim.application.services.test_comparison import TraceComparison


def _comparison(rmse=0.02, coverage="complete"):
    return TraceComparison(
        metrics={"voltage_rmse_V": rmse},
        coverage={"status": coverage},
        aligned_trace={},
        warnings=(),
    )


def test_passing_local_criterion_does_not_become_model_validation():
    assessment = ModelTestEvidenceService().assess(
        comparison=_comparison(rmse=0.02),
        simulation_successful=True,
        measured_current_supplied=True,
        voltage_rmse_limit_V=0.03,
    )

    assert assessment.acceptance_criterion["passed"] is True
    assert assessment.confidence == "low"
    assert assessment.decision_ready is False
    assert "this trace only" in assessment.conclusion
    assert assessment.next_experiments


def test_failed_local_criterion_is_stated_directly():
    assessment = ModelTestEvidenceService().assess(
        comparison=_comparison(rmse=0.04),
        simulation_successful=True,
        measured_current_supplied=True,
        voltage_rmse_limit_V=0.03,
    )

    assert assessment.acceptance_criterion["passed"] is False
    assert "fails" in assessment.conclusion


def test_partial_coverage_is_insufficient_even_with_small_residual():
    assessment = ModelTestEvidenceService().assess(
        comparison=_comparison(rmse=0.001, coverage="partial"),
        simulation_successful=True,
        measured_current_supplied=True,
    )

    assert assessment.confidence == "insufficient"
    assert assessment.decision_ready is False


def test_absent_measured_current_is_visible_in_evidence_basis():
    assessment = ModelTestEvidenceService().assess(
        comparison=_comparison(),
        simulation_successful=True,
        measured_current_supplied=False,
    )

    assert any("Measured current was absent" in item for item in assessment.basis)
