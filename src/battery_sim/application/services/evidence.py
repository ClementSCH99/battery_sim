"""Conservative evidence assessment for model-to-test comparisons."""

from dataclasses import dataclass
import math
from typing import Any, Optional

from battery_sim.application.services.test_comparison import TraceComparison


@dataclass(frozen=True)
class EvidenceAssessment:
    confidence: str
    decision_ready: bool
    conclusion: str
    basis: tuple[str, ...]
    acceptance_criterion: dict[str, Any]
    next_experiments: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "decision_ready": self.decision_ready,
            "conclusion": self.conclusion,
            "basis": list(self.basis),
            "acceptance_criterion": self.acceptance_criterion,
            "next_experiments": list(self.next_experiments),
        }


class ModelTestEvidenceService:
    """State what one residual comparison proves and, crucially, what it does not."""

    def assess(
        self,
        *,
        comparison: TraceComparison,
        simulation_successful: bool,
        measured_current_supplied: bool,
        voltage_rmse_limit_V: Optional[float] = None,
    ) -> EvidenceAssessment:
        observed_rmse = comparison.metrics["voltage_rmse_V"]
        if voltage_rmse_limit_V is None:
            criterion = {
                "specified": False,
                "metric": "voltage_rmse_V",
                "limit_V": None,
                "observed_V": observed_rmse,
                "passed": None,
            }
        else:
            if not math.isfinite(voltage_rmse_limit_V) or voltage_rmse_limit_V <= 0:
                raise ValueError("voltage_rmse_limit_V must be > 0 when provided")
            criterion = {
                "specified": True,
                "metric": "voltage_rmse_V",
                "limit_V": voltage_rmse_limit_V,
                "observed_V": observed_rmse,
                "passed": observed_rmse <= voltage_rmse_limit_V,
            }

        basis = [
            "Only one operating condition and one supplied trace were evaluated.",
            "No model parameters were fitted by this comparison.",
            "The experimental initial electrochemical state is not independently verified.",
            "Measurement uncertainty and cell-to-cell repeatability are not yet quantified.",
        ]
        insufficient = not simulation_successful or comparison.coverage["status"] != "complete"
        if not measured_current_supplied:
            basis.append("Measured current was absent, so stimulus agreement was not verified.")
        if insufficient:
            confidence = "insufficient"
            conclusion = (
                "The available overlap is insufficient for a model-adequacy conclusion; "
                "the reported residuals remain descriptive only."
            )
        else:
            confidence = "low"
            criterion_text = ""
            if criterion["passed"] is True:
                criterion_text = " The declared RMSE criterion passes for this trace only."
            elif criterion["passed"] is False:
                criterion_text = " The declared RMSE criterion fails for this trace."
            conclusion = (
                "Residuals are quantified for this single CC-discharge condition, but they do "
                "not validate the preset as a cell model."
                + criterion_text
            )

        return EvidenceAssessment(
            confidence=confidence,
            decision_ready=False,
            conclusion=conclusion,
            basis=tuple(basis),
            acceptance_criterion=criterion,
            next_experiments=(
                "Verify initial SOC using a documented conditioning and rest procedure.",
                "Quantify cycler voltage/current uncertainty and repeatability across replicate cells.",
                "Repeat independent CC discharges across temperature and C-rate.",
                "Reserve separate datasets for parameter calibration and validation.",
                "Inspect time-resolved residual structure, not RMSE alone.",
            ),
        )
