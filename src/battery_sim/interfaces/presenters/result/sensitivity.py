"""Sensitivity formatting and reusable insight extraction."""

from typing import Any, Dict, List, Optional

from battery_sim.interfaces.presenters.result.model import DualFormatResult

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
