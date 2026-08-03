"""Focused reasoning behavior."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from battery_sim.application.session.models import (
    InvestigationRun,
)

class ReasoningMixin:
    def get_reasoning_chain(self) -> str:
        """
        Describe the reasoning path taken during this investigation.

        TEACHING: This is how we audit the LLM's reasoning.
        "Here's what the LLM did:
        1. Compared chemistries
        2. Found NMC best
        3. Analyzed NMC sensitivity
        4. Identified temperature as key
        5. Optimized for temperature"

        This narrative shows the investigation strategy.
        """

        lines = [
            f"=== INVESTIGATION CHAIN: {self.name} ===",
            f"Started: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Investigations run: {self.num_investigations()}",
            f"Total simulation time: {self.total_simulation_time():.1f}s",
            "",
            "## Investigation Sequence:",
            "",
        ]

        for i, run in enumerate(self.investigation_history, 1):
            lines.append(f"{i}. **{run.investigation_type}** ({run.duration_seconds:.1f}s)")

            # What was tested?
            param_str = ", ".join(f"{k}={v}" for k, v in run.parameters.items())
            if param_str:
                lines.append(f"   Parameters: {param_str}")

            # What was found?
            if run.key_findings:
                lines.append(f"   Key findings:")
                for finding in run.key_findings:
                    lines.append(f"   - {finding}")

            lines.append("")

        # Conclusions
        if self.conclusions:
            lines.append("## Conclusions Reached:")
            lines.append("")
            for key, value in self.conclusions.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        return "\n".join(lines)
    def identify_investigation_pattern(self) -> str:
        """
        Identify what kind of investigation strategy was used.

        TEACHING: Different LLMs might use different strategies:
        - Broad-to-narrow: Compare many, then focus on best
        - Constraint-driven: Check feasibility first, then optimize
        - Sensitivity-first: Understand parameter importance, then explore

        This classifies what the LLM did.
        """

        if not self.investigation_history:
            return "No investigations run"

        types = [r.investigation_type for r in self.investigation_history]

        if types[0] == 'compare_presets' and 'sensitivity_analysis' in types:
            return "🎯 Broad-to-narrow: Start with preset comparison, then analyze winner"
        elif 'constraint_check' in types[:2]:
            return "🛡️  Constraint-driven: Check feasibility first, then explore"
        elif types[0] == 'sensitivity_analysis':
            return "🔬 Sensitivity-first: Understand parameters, then explore"
        else:
            return "🔍 Custom exploration strategy"
    def generate_report(self) -> str:
        """
        Generate a complete session report.

        TEACHING: This is what gets saved to disk or shown to the engineer.
        It documents the entire investigation process.
        """

        lines = [
            "=" * 70,
            "INVESTIGATION SESSION REPORT",
            "=" * 70,
            "",
            f"Name: {self.name}",
            f"Started: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Investigations: {self.num_investigations()}",
            f"Total time: {self.total_simulation_time():.1f}s",
            f"Strategy: {self.identify_investigation_pattern()}",
            "",
        ]

        # Detail each investigation
        for i, run in enumerate(self.investigation_history, 1):
            lines.append(f"\n### Investigation {i}: {run.investigation_type}")
            lines.append(f"Timestamp: {run.timestamp.strftime('%H:%M:%S')}")
            lines.append(f"Duration: {run.duration_seconds:.1f}s")
            lines.append("")

            # Include the markdown result
            lines.append(run.result_markdown)
            lines.append("")

        # Conclusions
        if self.conclusions:
            lines.append("\n## FINAL CONCLUSIONS")
            lines.append("")
            for key, value in self.conclusions.items():
                lines.append(f"**{key}**: {value}")
            lines.append("")

        return "\n".join(lines)
