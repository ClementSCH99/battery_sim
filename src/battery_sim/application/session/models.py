"""Immutable values used by this capability."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

@dataclass
class InvestigationRun:
    """
    A single investigation within a session.
    
    TEACHING: An "investigation run" is one thing the LLM tried.
    It records:
    - What question was asked (investigation_type)
    - What parameters it used
    - What it learned (result_summary)
    - When it happened (timestamp)
    
    The collection of InvestigationRun objects forms the session history.
    """
    
    investigation_type: str  # 'compare_presets', 'sensitivity_analysis', etc.
    timestamp: datetime
    parameters: Dict[str, Any]  # What was tested?
    result_summary: Dict[str, Any]  # What was learned?
    result_markdown: str  # Human-readable format
    duration_seconds: float  # How long did it take?
    
    # Optional: insights that the investigation revealed
    key_findings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization for logging."""
        return {
            'type': self.investigation_type,
            'timestamp': self.timestamp.isoformat(),
            'parameters': self.parameters,
            'summary': self.result_summary,
            'duration_s': self.duration_seconds,
            'findings': self.key_findings,
        }
