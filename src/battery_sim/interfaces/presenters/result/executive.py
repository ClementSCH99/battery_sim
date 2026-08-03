"""Executive summaries for cell-selection decisions."""

from typing import Any, Dict, List, Optional

from battery_sim.interfaces.presenters.result.model import DualFormatResult

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
