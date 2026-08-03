"""Focused recording behavior."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from battery_sim.application.session.models import (
    InvestigationRun,
)

class RecordingMixin:
    def __init__(self, name: str = "Investigation Session"):
        """
        Initialize a new investigation session.

        Args:
            name: Human-readable name for this investigation
        """
        self.name = name
        self.created_at = datetime.now()
        self.investigation_history: List[InvestigationRun] = []

        # Track "conclusions" - what the LLM has learned
        self.conclusions: Dict[str, Any] = {}
    def record_investigation(
        self,
        investigation_type: str,
        parameters: Dict[str, Any],
        result_summary: Dict[str, Any],
        result_markdown: str,
        duration_seconds: float = 0,
        key_findings: Optional[List[str]] = None,
    ) -> InvestigationRun:
        """
        Record an investigation that was run.

        TEACHING: After the LLM runs an investigation tool, it calls this
        to record what happened. This builds the session history.

        Args:
            investigation_type: Tool that was used (e.g., 'compare_presets')
            parameters: Parameters passed to the tool
            result_summary: JSON result from the tool
            result_markdown: Markdown-formatted result
            duration_seconds: How long did it take?
            key_findings: List of insights from this investigation

        Returns:
            InvestigationRun object (added to session history)
        """

        run = InvestigationRun(
            investigation_type=investigation_type,
            timestamp=datetime.now(),
            parameters=parameters,
            result_summary=result_summary,
            result_markdown=result_markdown,
            duration_seconds=duration_seconds,
            key_findings=key_findings or [],
        )

        self.investigation_history.append(run)
        return run
    def update_conclusion(self, key: str, value: Any) -> None:
        """
        Record a conclusion from this investigation.

        TEACHING: After analyzing results, the LLM might conclude:
        "NMC is the best chemistry for this application"

        We record that so later steps can refer back to it.

        Args:
            key: What aspect of the problem? (e.g., "best_chemistry")
            value: What's the conclusion? (e.g., "NMC")
        """
        self.conclusions[key] = value
    def get_conclusion(self, key: str) -> Optional[Any]:
        """Retrieve a previous conclusion."""
        return self.conclusions.get(key)
    def get_investigation_history(self) -> List[InvestigationRun]:
        """Get all investigations in this session, in order."""
        return self.investigation_history
    def num_investigations(self) -> int:
        """How many investigations have been done?"""
        return len(self.investigation_history)
    def total_simulation_time(self) -> float:
        """Total wall-clock time spent on simulations."""
        return sum(run.duration_seconds for run in self.investigation_history)
