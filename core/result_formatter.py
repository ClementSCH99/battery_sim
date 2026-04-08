"""
LAYER 3: RESULT FORMATTING - Dual Output (JSON + Markdown)

TEACHING FOCUS: Serving multiple audiences

WHY THIS LAYER EXISTS:
When the LLM runs an investigation tool, it gets structured data derived from
SimulationRun objects.
This layer formats those interface outputs in TWO ways:

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

DESIGN PRINCIPLE: Every tool output should be immediately useful to BOTH audiences.
The LLM can parse the JSON for reasoning.
The engineer can read the Markdown for insights.

This module does not define the runtime execution contract.
Simulation.run() canonically returns SimulationRun; formatting happens after that.
Runtime time-series signals use the canonical Signal vocabulary (`voltage`,
`current`, `soc`, `temperature`, etc.), while formatter outputs may also expose
derived summary metrics such as `peak_power_W`.

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
            metrics_dict: Dict of metrics (from ComparisonService)
        
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
            else:
                json_data['metrics'][metric_name] = {
                    'type': metric_data.get('type', 'categorical'),
                    'values': metric_data.get('values', {}),
                    'categories': metric_data.get('categories', {}),
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

        # Add categorical/error-focused context when available
        categorical_metrics = [
            (metric_name, metric_data)
            for metric_name, metric_data in metrics_dict.items()
            if metric_data.get('type') != 'numeric'
        ]
        if categorical_metrics:
            md_lines.append("")
            md_lines.append("### Status and Error Context")
            md_lines.append("")
            for metric_name, metric_data in categorical_metrics:
                values = metric_data.get('values', {})
                formatted_values = [
                    f"{scenario}: {ComparisonFormatter._format_categorical_value(values.get(scenario))}"
                    for scenario in scenarios
                ]
                md_lines.append(f"- **{metric_name}**: {'; '.join(formatted_values)}")
        
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
    def format_comparison_with_ev(
        scenarios: List[str],
        metrics_dict: Dict[str, Any],
        ev_metrics: Optional[Dict[str, Dict[str, float]]] = None,
        ragone_data: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> DualFormatResult:
        """
        Format comparison with EV-specific metrics and Ragone data.
        
        TEACHING: This enhanced formatter adds:
        1. EV-relevant metrics (energy density, cost/kWh, C-rates)
        2. Ragone plot data (power vs energy trade-off)
        3. Best-for analysis: which preset wins on which metric
        
        Args:
            scenarios: List of scenario/preset names
            metrics_dict: Dict of simulation metrics
            ev_metrics: EV-specific metrics (gravimetric, volumetric density, cost, C-rates)
            ragone_data: Power-energy trade-off data
        
        Returns:
            DualFormatResult with comprehensive comparison
        """
        
        # Build JSON structure
        json_data = {
            'type': 'comparison_with_ev_metrics',
            'scenarios': scenarios,
            'metrics': {},
            'ev_metrics': ev_metrics or {},
            'ragone_data': ragone_data or {},
        }
        
        # Analyze baseline metrics
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
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
            else:
                json_data['metrics'][metric_name] = {
                    'type': metric_data.get('type', 'categorical'),
                    'values': metric_data.get('values', {}),
                    'categories': metric_data.get('categories', {}),
                }
        
        # Compute "best_for" winners across all metrics
        best_for = ComparisonFormatter._compute_best_for(metrics_dict, ev_metrics)
        json_data['best_for'] = best_for
        
        # Build Markdown output
        md_lines = [
            "## Comparison Results: Cell Presets with EV Metrics",
            "",
            f"Scenarios compared: {', '.join(f'**{s}**' for s in scenarios)}",
            "",
        ]
        
        # EV Metrics Table
        if ev_metrics:
            md_lines.extend([
                "### EV-Specific Metrics",
                "",
                "| Metric | " + " | ".join(scenarios) + " |",
                "|" + "|".join(["-" * 30] * (len(scenarios) + 1)) + "|",
            ])
            
            # Gravimetric energy density
            row = "| Gravimetric Energy Density (Wh/kg) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('energy_density_Wh_per_kg', 0)
                row += f" {val:.1f} |"
            md_lines.append(row)
            
            # Volumetric energy density
            row = "| Volumetric Energy Density (Wh/L) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('energy_density_Wh_per_L', 0)
                row += f" {val:.1f} |"
            md_lines.append(row)
            
            # Cost per kWh
            row = "| Cost per kWh ($/kWh) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('cost_per_kWh', 0)
                row += f" ${val:.2f} |"
            md_lines.append(row)
            
            # Max charge C-rate
            row = "| Max Charge C-Rate |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('max_charge_c_rate', 0)
                row += f" {val:.1f}C |"
            md_lines.append(row)
            
            # Max discharge C-rate
            row = "| Max Discharge C-Rate |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('max_discharge_c_rate', 0)
                row += f" {val:.1f}C |"
            md_lines.append(row)
            
            # Cycle life
            row = "| Cycle Life (cycles) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('cycle_life_cycles', 0)
                row += f" {int(val)} |"
            md_lines.append(row)
            
            md_lines.append("")
        
        # Ragone Data (Power vs Energy)
        if ragone_data and len(ragone_data) >= 2:
            md_lines.extend([
                "### Ragone Plot Data (Power Density vs Energy Density)",
                "",
                "| Cell | Energy Density (Wh/kg) | Power Density (W/kg) |",
                "|---|---|---|",
            ])
            
            for scenario in scenarios:
                data = ragone_data.get(scenario, {})
                energy = data.get('energy_density_Wh_per_kg', 0)
                power = data.get('power_density_W_per_kg', 0)
                md_lines.append(f"| {scenario} | {energy:.1f} | {power:.0f} |")
            
            md_lines.extend([
                "",
                "**Ragone Plot Interpretation**:",
                "- Cells to the right have higher energy density (more Wh per kg)",
                "- Cells higher up have higher power density (more W per kg)",
                "- Ideal EV cells push both corners; real cells show power-energy trade-off",
                "",
            ])
        
        # Best-For Summary
        if best_for:
            md_lines.extend([
                "### Best-For Summary",
                "",
            ])
            for metric, winner in best_for.items():
                md_lines.append(f"- **{metric}**: {winner}")
            md_lines.append("")
        
        # Key findings
        md_lines.extend([
            "### Key Findings",
            "",
        ])

        categorical_metrics = [
            (metric_name, metric_data)
            for metric_name, metric_data in metrics_dict.items()
            if metric_data.get('type') != 'numeric'
        ]
        if categorical_metrics:
            md_lines.append("### Status and Error Context")
            md_lines.append("")
            for metric_name, metric_data in categorical_metrics:
                values = metric_data.get('values', {})
                formatted_values = [
                    f"{scenario}: {ComparisonFormatter._format_categorical_value(values.get(scenario))}"
                    for scenario in scenarios
                ]
                md_lines.append(f"- **{metric_name}**: {'; '.join(formatted_values)}")
            md_lines.append("")
        
        insights = ComparisonFormatter._extract_insights(json_data)
        for insight in insights[:8]:
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
    def _compute_best_for(
        metrics_dict: Dict[str, Any],
        ev_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, str]:
        """
        Compute which preset wins on each metric.
        
        Returns:
            Dict mapping metric name to winning preset name
        """
        best_for = {}
        
        # Baseline metrics
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                values = metric_data['values']
                numeric_values = [(s, v) for s, v in values.items() if v is not None]
                
                if numeric_values:
                    best_val = max(numeric_values, key=lambda x: x[1] if metric_name not in ['solver_time_s'] else -x[1])
                    best_for[metric_name] = best_val[0]
        
        # EV metrics
        if ev_metrics:
            # Energy density (higher is better)
            energy_density_vals = {
                s: d.get('energy_density_Wh_per_kg', 0) 
                for s, d in ev_metrics.items()
            }
            if energy_density_vals:
                best_for['Gravimetric Energy Density'] = max(energy_density_vals, key=energy_density_vals.get)
            
            # Volumetric energy density (higher is better)
            volumetric_vals = {
                s: d.get('energy_density_Wh_per_L', 0) 
                for s, d in ev_metrics.items()
            }
            if volumetric_vals:
                best_for['Volumetric Energy Density'] = max(volumetric_vals, key=volumetric_vals.get)
            
            # Cost per kWh (lower is better)
            cost_vals = {
                s: d.get('cost_per_kWh', float('inf')) 
                for s, d in ev_metrics.items()
            }
            if cost_vals:
                best_for['Cost per kWh'] = min(cost_vals, key=cost_vals.get)
            
            # Discharge power (higher is better)
            discharge_vals = {
                s: d.get('max_discharge_c_rate', 0) 
                for s, d in ev_metrics.items()
            }
            if discharge_vals:
                best_for['Power Delivery'] = max(discharge_vals, key=discharge_vals.get)
            
            # Cycle life (higher is better)
            cycle_vals = {
                s: d.get('cycle_life_cycles', 0) 
                for s, d in ev_metrics.items()
            }
            if cycle_vals:
                best_for['Cycle Life'] = max(cycle_vals, key=cycle_vals.get)
        
        return best_for
    
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
    def _format_categorical_value(value: Any) -> str:
        """Format categorical values for markdown display."""
        if value is None:
            return "-"
        if isinstance(value, list):
            if not value:
                return "[]"
            return ", ".join(str(v) for v in value)
        return str(value)
    
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


# ============================================================================
# EXECUTIVE SUMMARY FORMATTER: Plain-language for non-experts
# ============================================================================

class ExecutiveSummaryFormatter:
    """
    Format technical results in plain language for stakeholders.
    
    TEACHING: Not everyone understands battery engineering terms.
    Engineers need to communicate results to product managers, executives,
    investors. This formatter translates technical findings into business language.
    
    Goals:
    - 3-5 bullet points, maximum
    - No jargon (no "C-rate", "SOH", "NMC")
    - Clear go/no-go decision
    - High-level tradeoffs ("power vs cost", "range vs weight")
    """
    
    @staticmethod
    def from_cell_selection_results(
        top_cell: 'CellScoringResult',
        all_results: List['CellScoringResult'],
        requirements: Dict[str, Any],
    ) -> str:
        """
        Generate executive summary from cell selection results.
        
        Args:
            top_cell: Best-scored CellScoringResult
            all_results: All CellScoringResult objects from scoring
            requirements: Original requirements dict
        
        Returns:
            Plain-language summary (3-5 bullet points)
        """
        
        lines = []
        
        # Line 1: Go/no-go decision
        meeting_count = sum(1 for r in all_results if r.meets_requirements)
        if top_cell.meets_requirements:
            lines.append(
                f"✓ **Go**: {ExecutiveSummaryFormatter._chemistry_name(top_cell.chemistry)} "
                f"meets all requirements and is ready to proceed."
            )
        elif meeting_count > 0:
            best_meeting = [r for r in all_results if r.meets_requirements][0]
            lines.append(
                f"⚠ **Conditional Go**: Only {ExecutiveSummaryFormatter._chemistry_name(best_meeting.chemistry)} "
                f"meets hard constraints; consider relaxing weight or cost budget."
            )
        else:
            lines.append(
                f"✗ **No-Go**: No battery chemistry meets your hard constraints. "
                f"Recommend revisiting weight or cost budget."
            )
        
        # Line 2: Top tradeoff for this cell
        tradeoff = ExecutiveSummaryFormatter._explain_tradeoff(top_cell)
        if tradeoff:
            lines.append(f"- **Key strength**: {tradeoff}")
        
        # Line 3: Cost/timeline implications
        cost_line = ExecutiveSummaryFormatter._cost_implication(top_cell, requirements)
        if cost_line:
            lines.append(f"- {cost_line}")
        
        # Line 4: Risk/warranty implication
        risk_line = ExecutiveSummaryFormatter._warranty_implication(top_cell, requirements)
        if risk_line:
            lines.append(f"- {risk_line}")
        
        # Line 5: Recommendation for next step
        if meeting_count > 1:
            runners_up = all_results[1:min(3, len(all_results))]
            chemistry_names = [ExecutiveSummaryFormatter._chemistry_name(r.chemistry) for r in runners_up]
            lines.append(
                f"- **Consider alternatives**: {' or '.join(chemistry_names)} "
                f"if priorities shift toward cost or performance."
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def _chemistry_name(chemistry: str) -> str:
        """Convert technical chemistry name to plain English."""
        names = {
            'LFP': 'lithium iron phosphate',
            'NMC': 'nickel-manganese-cobalt',
            'NCA': 'nickel-cobalt-aluminum',
            'LCO': 'lithium cobalt oxide',
            'LMNO': 'lithium manganese nickel oxide',
        }
        return names.get(chemistry, chemistry)
    
    @staticmethod
    def _explain_tradeoff(result: 'CellScoringResult') -> Optional[str]:
        """Identify and explain the cell's primary strength."""
        
        scores = [
            ('power delivery', result.power_score),
            ('energy storage', result.energy_score),
            ('affordability', result.cost_score),
            ('long-term reliability', result.lifetime_score),
            ('fast charging', result.charge_score),
        ]
        
        # Find strongest dimension
        best_dimension, best_score = max(scores, key=lambda x: x[1])
        
        if best_score >= 80:
            weakness_dimension, weakness_score = min(scores, key=lambda x: x[1])
            if weakness_score < 50:
                return f"{best_dimension} (good) vs lower {weakness_dimension}"
            else:
                return f"excellent {best_dimension}"
        
        return None
    
    @staticmethod
    def _cost_implication(result: 'CellScoringResult', requirements: Dict[str, Any]) -> Optional[str]:
        """Describe cost implications."""
        
        pack_cost = result.pack_config.cost_per_kWh * result.pack_config.pack_energy_kWh
        budget = requirements.get('cost_budget_usd', None)
        
        if budget is None:
            # No budget specified; give absolute cost
            return f"**Cost**: ~${pack_cost:,.0f} for 60 kWh (${result.pack_config.cost_per_kWh:.0f}/kWh market price)"
        
        if pack_cost <= budget:
            margin = (budget - pack_cost) / budget * 100
            if margin > 30:
                return f"**Cost**: Well within budget ({margin:.0f}% margin)"
            else:
                return f"**Cost**: At/near budget limit (${pack_cost:,.0f} / ${budget:,.0f})"
        else:
            overage = (pack_cost - budget) / budget * 100
            return f"**Cost**: Exceeds budget by {overage:.0f}% (${pack_cost:,.0f} vs ${budget:,.0f})"
    
    @staticmethod
    def _warranty_implication(result: 'CellScoringResult', requirements: Dict[str, Any]) -> Optional[str]:
        """Describe warranty/lifetime implications."""
        
        lifetime_years = requirements.get('lifetime_years', 8.0)
        lifetime_score = result.lifetime_score
        
        if lifetime_score >= 80:
            return f"**Warranty**: Excellent support for {lifetime_years}-year warranty (low risk)"
        elif lifetime_score >= 50:
            return f"**Warranty**: Meets {lifetime_years}-year warranty (moderate risk)"
        else:
            return f"**Warranty**: May not support {lifetime_years}-year warranty (high risk)"
