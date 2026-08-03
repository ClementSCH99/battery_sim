"""Dual machine-readable and human-readable interface result."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json

@dataclass(frozen=True)
class DualFormatResult:
    """
    Interface-layer tool output consumable by both LLM and humans.
    
    TEACHING: This is the key insight of Layer 3.
    Every tool returns a result that contains BOTH:
    - json_data: Machine-readable (for reasoning)
    - markdown_text: Human-readable (for communication)

    This is separate from the canonical runtime output.
    Simulation executions return SimulationRun, and formatters consume data
    derived from those runs.
    
    The LLM processes json_data.
    The engineer reads markdown_text.
    Both get the same information, just formatted differently.
    """
    
    # Machine-readable structured data
    json_data: Dict[str, Any]
    
    # Human-readable narrative
    markdown_text: str
    
    # Optional: Hints to guide LLM reasoning
    interpretation_hints: List[str]
    
    def to_json_string(self) -> str:
        """Pretty-print JSON for LLM or logging."""
        return json.dumps(self.json_data, indent=2)
    
    def to_markdown_string(self) -> str:
        """Return markdown for display/documentation."""
        lines = [self.markdown_text]
        
        if self.interpretation_hints:
            lines.append("\n### Hints for Interpretation:")
            for hint in self.interpretation_hints:
                lines.append(f"- {hint}")
        
        return "\n".join(lines)
    
    def summary(self) -> str:
        """One-line summary of the formatted tool output."""
        # Look for 'summary' key in JSON
        if 'summary' in self.json_data:
            return self.json_data['summary']
        
        # Fallback: extract from markdown
        lines = self.markdown_text.split('\n')
        for line in lines:
            if line.startswith('#'):
                return line.strip('#').strip()
        
        return "Comparison result"
