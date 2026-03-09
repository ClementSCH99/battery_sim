"""
LAYER 3: RESULT FORMATTING - Dual Output (JSON + Markdown)

TEACHING FOCUS: Serving multiple audiences

WHY THIS LAYER EXISTS:
When the LLM runs an investigation tool, it gets raw data.
But the data needs to be presented in TWO ways:

1. JSON: For the LLM to process and reason about
   - Structured
   - Machine-queryable
   - Follows a schema
   - No ambiguity

2. Markdown: For the engineer to READ
   - Human-readable tables
   - Clear conclusions  
   - formatted, not raw numbers
   - Easy to put in reports

DESIGN PRINCIPLE: Every result should be immediately useful to BOTH audiences.
The LLM can parse the JSON for reasoning.
The engineer can read the Markdown for insights.

---

EXAMPLE: Comparison Results

JSON OUTPUT (for LLM):
{
  "type": "comparison",
  "scenarios": ["LFP_5AH", "NMC_5AH", "NCA_5AH"],
  "metrics": {
    "peak_power_W": {
      "values": {"LFP_5AH": 12.4, "NMC_5AH": 18.6, "NCA_5AH": 25.3},
      "best": "NCA_5AH",
      "worst": "LFP_5AH"
    },
    "efficiency": {
      "values": {"LFP_5AH": 0.96, "NMC_5AH": 0.94, "NCA_5AH": 0.91},
      "best": "LFP_5AH"
    }
  }
}

MARKDOWN OUTPUT (for engineer):
## Comparison: LFP_5AH vs NMC_5AH vs NCA_5AH

| Chemistry | Peak Power (W) | Efficiency | Peak Current (A) |
|-----------|--------|----------|------|
| LFP_5AH   | 12.4W  | 96%      | 8.2A |
| NMC_5AH   | 18.6W (+50%) | 94%  | 12.3A |
| **NCA_5AH**   | **25.3W (+104%)** | 91% | **16.5A** |

### Key Findings:
- **Peak Power**: NCA is 2x more powerful than LFP
- **Efficiency**: LFP is 5% more efficient than NCA
- **Trade-off**: Choose NCA for power, LFP for efficiency

The Markdown is what gets communicated. The JSON is what gets processed.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import json


# ============================================================================
# DUAL FORMAT RESULT: JSON + Markdown
# ============================================================================

@dataclass(frozen=True)
class DualFormatResult:
    """
    A result that can be consumed by both LLM and humans.
    
    TEACHING: This is the key insight of Layer 3.
    Every tool returns a result that contains BOTH:
    - json_data: Machine-readable (for reasoning)
    - markdown_text: Human-readable (for communication)
    
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
        """One-liner summary of the result."""
        # Look for 'summary' key in JSON
        if 'summary' in self.json_data:
            return self.json_data['summary']
        
        # Fallback: extract from markdown
        lines = self.markdown_text.split('\n')
        for line in lines:
            if line.startswith('#'):
                return line.strip('#').strip()
        
        return "Comparison result"


# ============================================================================
# COMPARISON FORMATTER
# ============================================================================

class ComparisonFormatter:
    """
    Format comparison results in dual format.
    
    TEACHING: This is a specialized formatter for the compare_presets tool.
    It takes the raw comparison data and formats it into:
    1. JSON that the LLM can query
    2. Markdown tables the engineer can read
    """
    
    @staticmethod
    def format_comparison(
        scenarios: List[str],
        metrics_dict: Dict[str, Any],
    ) -> DualFormatResult:
        """
        Format a comparison in dual output.
        
        Args:
            scenarios: List of scenario names
            metrics_dict: Dict of metrics (from SimulationComparison)
        
        Returns:
            DualFormatResult with JSON + Markdown
        """
        
        # Build JSON structure (clean, queryable)
        json_data = {
            'type': 'comparison',
            'scenarios': scenarios,
            'metrics': {},
        }
        
        # Analyze each metric
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                # Extract best/worst for numeric metrics
                values = metric_data['values']
                numeric_values = [v for v in values.values() if v is not None]
                
                if numeric_values:
                    best_val = max(numeric_values) if metric_name not in ['solver_time_s'] else min(numeric_values)
                    best_scenario = [s for s, v in values.items() if v == best_val][0]
                    
                    worst_val = min(numeric_values) if metric_name not in ['solver_time_s'] else max(numeric_values)
                    worst_scenario = [s for s, v in values.items() if v == worst_val][0]
                    
                    json_data['metrics'][metric_name] = {
                        'type': 'numeric',
                        'values': values,
                        'best': best_scenario,
                        'best_value': best_val,
                        'worst': worst_scenario,
                        'worst_value': worst_val,
                        'range': metric_data.get('range'),
                    }
        
        # Build Markdown (readable tables)
        md_lines = [
            "## Comparison Results",
            "",
            f"Scenarios compared: {', '.join(f'**{s}**' for s in scenarios)}",
            "",
        ]
        
        # Create comparison table
        md_lines.append("### Metrics Comparison")
        md_lines.append("")
        
        # Table header
        header = "| Metric |" + "".join(f" {s} |" for s in scenarios)
        separator = "|" + "-" * (10 + len(scenarios) * 20) + "|"
        
        md_lines.append(header)
        md_lines.append(separator)
        
        # Table rows
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                values = metric_data['values']
                row = f"| {metric_name} |"
                for scenario in scenarios:
                    val = values.get(scenario)
                    if val is not None:
                        # Format number nicely
                        if isinstance(val, float):
                            formatted = f"{val:.2f}"
                        else:
                            formatted = str(val)
                        row += f" {formatted} |"
                    else:
                        row += " - |"
                md_lines.append(row)
        
        md_lines.append("")
        
        # Key findings  
        md_lines.append("### Key Findings")
        md_lines.append("")
        
        # Extract top insights
        insights = ComparisonFormatter._extract_insights(json_data)
        for insight in insights[:5]:  # Top 5 insights
            md_lines.append(f"- {insight}")
        
        markdown_text = "\n".join(md_lines)
        
        # Generate interpretation hints
        hints = ComparisonFormatter._generate_hints(json_data)
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown_text,
            interpretation_hints=hints,
        )
    
    @staticmethod
    def _extract_insights(json_data: Dict[str, Any]) -> List[str]:
        """
        Extract interesting patterns from comparison data.
        
        TEACHING: This is how we guide the LLM.
        We don't tell it what to think, but we point out patterns.
        """
        insights = []
        
        for metric_name, metric_data in json_data.get('metrics', {}).items():
            if 'best' in metric_data and 'range' in metric_data:
                best = metric_data['best']
                best_val = metric_data['best_value']
                range_val = metric_data['range']
                worst_val = metric_data['worst_value']
                
                if worst_val != 0:
                    ratio = best_val / worst_val
                    if ratio > 1.5:
                        insights.append(
                            f"**{best}** significantly outperforms on {metric_name}: "
                            f"{best_val:.1f} ({ratio:.1f}x better)"
                        )
                    elif range_val > 20:  # Arbitrary threshold for "big difference"
                        insights.append(
                            f"Significant variation in {metric_name} across scenarios "
                            f"(range: {range_val:.1f})"
                        )
        
        return insights
    
    @staticmethod
    def _generate_hints(json_data: Dict[str, Any]) -> List[str]:
        """
        Generate interpretation hints.
        
        TEACHING: Hints guide reasoning without prescribing.
        """
        hints = []
        
        metrics = json_data.get('metrics', {})
        
        # Hint 1: What metric shows the biggest spread?
        max_range = 0
        max_metric = None
        for metric, data in metrics.items():
            if 'range' in data and data['range']:
                if data['range'] > max_range:
                    max_range = data['range']
                    max_metric = metric
        
        if max_metric:
            hints.append(f"Largest variation is in {max_metric} (range: {max_range:.1f})")
        
        # Hint 2: Trade-offs
        if len(metrics) > 1:
            hints.append("Different scenarios excel at different metrics - consider trade-offs")
        
        return hints


# ============================================================================
# SENSITIVITY RESULT FORMATTER
# ============================================================================

class SensitivityFormatter:
    """
    Format sensitivity analysis results.
    
    TEACHING: Sensitivity results show "how much does X matter?"
    We format this to emphasize:
    1. The ranked importance of parameters
    2. The magnitude of effects
    3. Actionable guidance
    """
    
    @staticmethod
    def format_sensitivity(
        sensitivity_results: List[Any],  # List of SensitivityResult
    ) -> DualFormatResult:
        """
        Format sensitivity analysis in dual output.
        
        Args:
            sensitivity_results: List of SensitivityResult objects
        
        Returns:
            DualFormatResult
        """
        
        # JSON: Ranked sensitivity
        json_data = {
            'type': 'sensitivity_analysis',
            'parameters': [],
        }
        
        # Sort by sensitivity coefficient (descending)
        ranked = sorted(
            sensitivity_results,
            key=lambda r: r.sensitivity_coefficient or 0,
            reverse=True,
        )
        
        for result in ranked:
            json_data['parameters'].append({
                'name': result.parameter_name,
                'sensitivity': result.sensitivity_coefficient,
                'interpretation': result.interpretation(),
                'range_tested': (min(result.parameter_values), max(result.parameter_values)),
                'metric_range': (result.min_value, result.max_value),
            })
        
        # Markdown: Human-readable ranking
        md_lines = [
            "## Sensitivity Analysis: Parameter Importance",
            "",
            "### Ranked by Sensitivity (most important first)",
            "",
        ]
        
        for i, result in enumerate(ranked, 1):
            sensitivity_pct = result.sensitivity_coefficient or 0
            interpretation = result.interpretation()
            
            md_lines.append(f"{i}. **{result.parameter_name}**")
            md_lines.append(f"   - Sensitivity: {sensitivity_pct:.1f}%")
            md_lines.append(f"   - {interpretation}")
            md_lines.append(f"   - Range tested: {min(result.parameter_values):.2f} - {max(result.parameter_values):.2f}")
            md_lines.append("")
        
        # Guidance
        md_lines.append("### Interpretation Guide")
        md_lines.append("")
        md_lines.append("- **HIGH sensitivity (>20%)**: Tuning this parameter will significantly affect results")
        md_lines.append("- **MODERATE sensitivity (5-20%)**: Tuning matters, but not the most important")
        md_lines.append("- **LOW sensitivity (<5%)**: Tuning has minimal effect - deprioritize")
        md_lines.append("")
        
        markdown_text = "\n".join(md_lines)
        
        # Hints
        hints = []
        high_sensitivity = [r for r in ranked if (r.sensitivity_coefficient or 0) > 20]
        if high_sensitivity:
            params = ", ".join(r.parameter_name for r in high_sensitivity[:3])
            hints.append(f"Focus on tuning {params} for maximum impact")
        
        low_sensitivity = [r for r in ranked if (r.sensitivity_coefficient or 0) < 5]
        if low_sensitivity:
            params = ", ".join(r.parameter_name for r in low_sensitivity)
            hints.append(f"Deprioritize {params} - they have minimal effect")
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown_text,
            interpretation_hints=hints,
        )


# ============================================================================
# INSIGHT EXTRACTOR: Additional hints from results
# ============================================================================

class InsightExtractor:
    """
    Extract additional insights from results to guide LLM reasoning.
    
    TEACHING: Some things are obvious from numbers, but LLMs reason better
    when we point them out. This class generates "hints" that highlight
    patterns without prescribing conclusions.
    """
    
    @staticmethod
    def extract_from_comparison(scenarios: List[str], metrics: Dict[str, Any]) -> List[str]:
        """Extract insights from comparison results."""
        insights = []
        
        # Identify dominant scenarios (best at multiple metrics)
        scenario_scores = {s: 0 for s in scenarios}
        
        for metric_name, metric_data in metrics.items():
            if 'best' in metric_data:
                best = metric_data['best']
                scenario_scores[best] = scenario_scores.get(best, 0) + 1
        
        if scenario_scores:
            best_overall = max(scenario_scores, key=lambda s: scenario_scores[s])
            if scenario_scores[best_overall] > 1:
                insights.append(
                    f"{best_overall} dominates: best at {scenario_scores[best_overall]} metrics"
                )
        
        return insights
    
    @staticmethod
    def extract_from_sensitivity(
        results: List[Any],
    ) -> List[str]:
        """Extract insights from sensitivity results."""
        insights = []
        
        # Identify key parameters
        high_sensitivity = [r for r in results if (r.sensitivity_coefficient or 0) > 20]
        
        if high_sensitivity:
            top_param = high_sensitivity[0]
            insights.append(
                f"Most critical parameter: {top_param.parameter_name} "
                f"({top_param.sensitivity_coefficient:.0f}% sensitivity)"
            )
        
        # Identify non-factors
        low_sensitivity = [r for r in results if (r.sensitivity_coefficient or 0) < 2]
        if low_sensitivity:
            non_factors = ", ".join(r.parameter_name for r in low_sensitivity[:2])
            insights.append(f"Non-factors (ignore): {non_factors}")
        
        return insights
