"""Canonical, non-executing contract for an electrochemical experiment plan."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ExperimentPlan:
    """A reviewable proposal produced before constructing a Simulation."""

    question: str
    status: str
    configuration: dict[str, Any]
    model_rationale: str
    missing_inputs: tuple[str, ...] = ()
    proposed_defaults: tuple[dict[str, Any], ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    execution: dict[str, Any] = field(default_factory=dict)
    traceability: dict[str, Any] = field(default_factory=dict)
    plan_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def ready_for_execution(self) -> bool:
        return not self.missing_inputs

    @property
    def requires_confirmation(self) -> bool:
        return bool(self.proposed_defaults)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "experiment_plan",
            "plan_id": self.plan_id,
            "question": self.question,
            "status": self.status,
            "ready_for_execution": self.ready_for_execution,
            "requires_confirmation": self.requires_confirmation,
            "missing_inputs": list(self.missing_inputs),
            "proposed_defaults": list(self.proposed_defaults),
            "configuration": self.configuration,
            "model_rationale": self.model_rationale,
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "execution": self.execution,
            "traceability": self.traceability,
        }
