"""
Tests for D3: Cell Selection Wizard

Tests the multi-criteria decision support tool that ranks cell chemistries
against application requirements.
"""

import pytest
from typing import Dict, Any

from battery_sim.application.analysis.investigation import (
    CellSelectionScorer,
    CellScoringResult,
)
from battery_sim.interfaces.python.tool_registry import AgentAPI
from battery_sim.core.cell import CellPresets
from battery_sim.interfaces.presenters.result import (
    DualFormatResult,
    ExecutiveSummaryFormatter,
)


# ============================================================================
# CELL SELECTION SCORER TEST SUITE
# ============================================================================

class TestCellSelectionScorerMath:
    """Test the core scoring mathematics."""
    
    @pytest.fixture
    def base_requirements(self) -> Dict[str, Any]:
        """Standard EV application requirements."""
        return {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 15000.0,
        }
    
    def test_score_returns_list_of_results(self, base_requirements):
        """Scoring should return list of CellScoringResult objects."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, CellScoringResult) for r in results)
    
    def test_scores_sorted_descending(self, base_requirements):
        """Results should be sorted by total_score (best first)."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_scores_are_0_to_100(self, base_requirements):
        """All dimension scores should be 0-100."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        
        for r in results:
            assert 0 <= r.energy_score <= 100
            assert 0 <= r.power_score <= 100
            assert 0 <= r.cost_score <= 100
            assert 0 <= r.lifetime_score <= 100
            assert 0 <= r.charge_score <= 100
            assert 0 <= r.total_score <= 100
    
    def test_total_score_is_average_of_dimensions(self, base_requirements):
        """Total score must equal average of 5 dimension scores."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()[:1]]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        r = results[0]
        
        expected_avg = (
            r.energy_score + r.power_score + r.cost_score +
            r.lifetime_score + r.charge_score
        ) / 5.0
        
        assert abs(r.total_score - expected_avg) < 0.1
    
    def test_meets_requirements_reflects_hard_constraints(self, base_requirements):
        """meets_requirements should only be True if weight/volume/cost within budget."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        
        for r in results:
            # Check weight constraint
            if r.pack_config and r.pack_config.system_weight_kg > base_requirements['weight_budget_kg']:
                assert not r.meets_requirements
            # Check volume constraint
            if r.pack_config and r.pack_config.system_volume_L > base_requirements['volume_budget_L']:
                assert not r.meets_requirements
            # Check cost constraint
            if r.pack_config:
                total_cost = r.pack_config.cost_per_kWh * r.pack_config.pack_energy_kWh
                if total_cost > base_requirements['cost_budget_usd']:
                    assert not r.meets_requirements
    
    def test_energy_score_penalizes_heavy_packs(self, base_requirements):
        """Energy score should be lower for packs that exceed weight budget."""
        # Tight weight budget
        tight_budget = base_requirements.copy()
        tight_budget['weight_budget_kg'] = 300.0
        
        # Loose weight budget
        loose_budget = base_requirements.copy()
        loose_budget['weight_budget_kg'] = 800.0
        
        presets = [CellPresets.LFP_5AH]
        
        tight_results = CellSelectionScorer.score(tight_budget, presets)
        loose_results = CellSelectionScorer.score(loose_budget, presets)
        
        # Same preset should score higher with looser constraint
        assert loose_results[0].energy_score >= tight_results[0].energy_score
    
    def test_power_score_high_for_high_discharge_cells(self):
        """Power score should be high for cells with high discharge C-rate."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
        }
        
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        results = CellSelectionScorer.score(requirements, presets)
        
        # All cells should have reasonable power scores (can achieve ~1C at minimum)
        assert all(r.power_score >= 30 for r in results)
    
    def test_lifetime_score_reflects_cycle_life(self):
        """Lifetime score should be high for LFP (long cycle life) vs NCA (shorter)."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
        }
        
        # LFP has ~3000 cycles, NCA ~1500
        lfp_results = CellSelectionScorer.score(requirements, [CellPresets.LFP_5AH])
        nca_results = CellSelectionScorer.score(requirements, [CellPresets.NCA_5AH])
        
        # LFP should score better on lifetime
        assert lfp_results[0].lifetime_score > nca_results[0].lifetime_score
    
    def test_cost_score_penalizes_expensive_packs(self):
        """Cost score should be lower for packs exceeding budget."""
        # Tight budget
        tight = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'cost_budget_usd': 5000.0,  # Very tight
        }
        
        # Loose budget
        loose = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'cost_budget_usd': 50000.0,  # Very loose
        }
        
        presets = [CellPresets.NCA_5AH]  # Expensive chemistry
        
        tight_results = CellSelectionScorer.score(tight, presets)
        loose_results = CellSelectionScorer.score(loose, presets)
        
        # Same preset should have same cost, but scoring interpretation differs
        # Tight budget should penalize cost more
        assert loose_results[0].cost_score >= tight_results[0].cost_score
    
    def test_recommendation_text_generated(self, base_requirements):
        """Each result should have meaningful recommendation text."""
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        results = CellSelectionScorer.score(base_requirements, presets)
        
        assert all(isinstance(r.recommendation, str) for r in results)
        assert all(len(r.recommendation) > 10 for r in results)
        
        # Meeting cells should have positive recommendations
        meeting = [r for r in results if r.meets_requirements]
        if meeting:
            assert any("Best for" in r.recommendation or "Balanced" in r.recommendation for r in meeting)
        
        # Failing cells should indicate why (could be cost, weight, etc.)
        failing = [r for r in results if not r.meets_requirements]
        if failing:
            # Should have reason for failure
            assert any(keyword in r.recommendation for keyword in [
                "Fails on", "Does not meet", "Exceeds", "budget", "weight", "volume", "cost", "cycle life"
            ] for r in failing)


# ============================================================================
# CELL SELECTION WIZARD API TEST SUITE
# ============================================================================

class TestCellSelectionWizardAPI:
    """Test the agent API integration."""
    
    @pytest.fixture
    def api(self):
        """Fresh AgentAPI instance."""
        return AgentAPI()
    
    def test_cell_selection_wizard_returns_dual_format(self, api):
        """cell_selection_wizard should return DualFormatResult."""
        result = api.cell_selection_wizard(
            range_km=400,
            power_kW=150,
            weight_budget_kg=500,
            lifetime_years=8,
        )
        
        assert isinstance(result, DualFormatResult)
        assert result.json_data is not None
        assert result.markdown_text is not None
    
    def test_wizard_json_has_required_fields(self, api):
        """JSON output must include rankings and requirements."""
        result = api.cell_selection_wizard()
        
        json_data = result.json_data
        assert 'type' in json_data
        assert json_data['type'] == 'cell_selection'
        assert 'requirements' in json_data
        assert 'rankings' in json_data
        assert isinstance(json_data['rankings'], list)
    
    def test_wizard_json_ranking_has_scores(self, api):
        """Each ranking should include all five dimension scores."""
        result = api.cell_selection_wizard()
        
        for ranking in result.json_data['rankings']:
            assert 'preset_name' in ranking
            assert 'chemistry' in ranking
            assert 'total_score' in ranking
            assert 'scores' in ranking
            
            scores = ranking['scores']
            assert 'energy' in scores
            assert 'power' in scores
            assert 'cost' in scores
            assert 'lifetime' in scores
            assert 'charge' in scores
    
    def test_wizard_markdown_readable(self, api):
        """Markdown output should contain rankings table and recommendations."""
        result = api.cell_selection_wizard()
        
        md = result.markdown_text
        assert 'Cell Selection Wizard' in md or 'cell' in md.lower()
        assert 'Recommendation' in md
    
    def test_wizard_multiple_presets_scored(self, api):
        """Wizard should score all available presets."""
        result = api.cell_selection_wizard()
        
        # Should score at least 5 different presets
        assert len(result.json_data['rankings']) >= 5
    
    def test_wizard_respects_weight_budget(self, api):
        """When weight budget is tight, fewer presets should meet requirements."""
        # Loose weight budget
        loose = api.cell_selection_wizard(weight_budget_kg=800)
        loose_meeting = sum(1 for r in loose.json_data['rankings'] if r['meets_requirements'])
        
        # Tight weight budget
        tight = api.cell_selection_wizard(weight_budget_kg=300)
        tight_meeting = sum(1 for r in tight.json_data['rankings'] if r['meets_requirements'])
        
        # Tighter budget should have fewer meeting
        assert tight_meeting <= loose_meeting
    
    def test_wizard_respects_cost_budget(self, api):
        """When cost budget is tight, fewer presets should meet requirements."""
        # Loose cost budget
        loose = api.cell_selection_wizard(cost_budget_usd=100000)
        loose_meeting = sum(1 for r in loose.json_data['rankings'] if r['meets_requirements'])
        
        # Tight cost budget
        tight = api.cell_selection_wizard(cost_budget_usd=5000)
        tight_meeting = sum(1 for r in tight.json_data['rankings'] if r['meets_requirements'])
        
        # Tighter budget should have fewer meeting
        assert tight_meeting <= loose_meeting
    
    def test_wizard_handles_optional_parameters(self, api):
        """Wizard should work with minimal and full parameter sets."""
        # Minimal
        minimal = api.cell_selection_wizard()
        assert len(minimal.json_data['rankings']) > 0
        
        # Full
        full = api.cell_selection_wizard(
            range_km=450,
            power_kW=200,
            weight_budget_kg=450,
            lifetime_years=10,
            volume_budget_L=250,
            cost_budget_usd=12000,
            charge_time_min=20,
        )
        assert len(full.json_data['rankings']) > 0
    
    def test_wizard_interpretation_hints_provided(self, api):
        """Result should include interpretation hints for LLM."""
        result = api.cell_selection_wizard()
        
        assert result.interpretation_hints is not None
        assert len(result.interpretation_hints) > 0
        assert all(isinstance(h, str) for h in result.interpretation_hints)


# ============================================================================
# REQUIREMENTS VALIDATION TEST SUITE  
# ============================================================================

class TestRequirementsValidation:
    """Test that requirements are correctly validated as met/not-met."""
    
    def test_lfp_meets_long_lifetime_requirement(self):
        """LFP with 3000+ cycle life should meet 8-year warranty."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 500.0,
            'cost_budget_usd': 20000.0,
        }
        
        results = CellSelectionScorer.score(
            requirements,
            [CellPresets.LFP_5AH]
        )
        
        # LFP should have high lifetime score
        assert results[0].lifetime_score >= 50
    
    def test_nca_scores_high_on_energy(self):
        """NCA with high energy density should score well on energy dimension."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 400.0,  # Tight weight budget favors high energy density
            'lifetime_years': 8.0,
            'volume_budget_L': 200.0,
        }
        
        results = CellSelectionScorer.score(
            requirements,
            [CellPresets.NCA_5AH]
        )
        
        # NCA should have decent energy score (high density helps with weight constraint)
        assert results[0].energy_score >= 40
    
    def test_impossible_requirements_fail(self):
        """Unrealistic requirements should result in no cells meeting constraints."""
        impossible = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 100.0,  # Impossible: 60 kWh pack is ~400 kg minimum
            'lifetime_years': 8.0,
            'volume_budget_L': 10.0,  # Impossible: 60 kWh needs ~100-200 L minimum
            'cost_budget_usd': 1000.0,  # Impossible: 60 kWh costs >$6000
        }
        
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        results = CellSelectionScorer.score(impossible, presets)
        
        # No preset should meet impossible requirements
        meeting = [r for r in results if r.meets_requirements]
        assert len(meeting) == 0

    def test_missing_packaging_data_is_not_treated_as_zero(self):
        """A research preset with unknown mass/volume/cost cannot pass pack constraints."""
        requirements = {
            'weight_budget_kg': 500.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 20000.0,
        }

        result = CellSelectionScorer.score(
            requirements,
            [CellPresets.LFP_PRADA_2P3AH],
        )[0]

        assert result.meets_requirements is False
        assert result.energy_score == 0.0
        assert result.cost_score == 0.0
    
    def test_realistic_requirements_at_least_one_meets(self):
        """Realistic requirements should have at least one cell meeting them."""
        realistic = {
            'range_km': 300.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 20000.0,
        }
        
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        results = CellSelectionScorer.score(realistic, presets)
        
        # At least one preset should meet realistic requirements
        meeting = [r for r in results if r.meets_requirements]
        assert len(meeting) >= 1


# ============================================================================
# EXECUTIVE SUMMARY FORMATTER TEST SUITE
# ============================================================================

class TestExecutiveSummaryFormatter:
    """Test plain-language executive summary generation."""
    
    def test_executive_summary_non_empty(self):
        """Executive summary should not be empty."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 15000.0,
        }
        
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        results = CellSelectionScorer.score(requirements, presets)
        
        if results:
            summary = ExecutiveSummaryFormatter.from_cell_selection_results(
                results[0], results, requirements
            )
            
            assert len(summary) > 0
            assert '\n' in summary  # Should be multi-line
    
    def test_executive_summary_includes_go_or_no_go(self):
        """Summary should clearly state go/no-go decision."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 15000.0,
        }
        
        presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        results = CellSelectionScorer.score(requirements, presets)
        
        summary = ExecutiveSummaryFormatter.from_cell_selection_results(
            results[0], results, requirements
        )
        
        # Should have clear decision indicator
        summary_lower = summary.lower()
        assert any(indicator in summary_lower for indicator in ['go', 'no-go', 'conditional', 'ready', 'meets', 'proceed'])
    
    def test_executive_summary_mentions_strengths(self):
        """Summary should highlight cell's key tradeoffs/strengths."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 15000.0,
        }
        
        presets = [CellPresets.LFP_5AH]
        results = CellSelectionScorer.score(requirements, presets)
        
        summary = ExecutiveSummaryFormatter.from_cell_selection_results(
            results[0], results, requirements
        )
        
        # Should mention something about strengths/tradeoffs
        summary_lower = summary.lower()
        assert any(word in summary_lower for word in [
            'strength', 'power', 'cost', 'reliability', 'charging', 'long-term'
        ])
    
    def test_executive_summary_plain_language_chemistry_names(self):
        """Summary should use plain English chemistry names, not abbreviations."""
        requirements = {
            'range_km': 400.0,
            'power_kW': 150.0,
            'weight_budget_kg': 500.0,
            'lifetime_years': 8.0,
            'volume_budget_L': 300.0,
            'cost_budget_usd': 15000.0,
        }
        
        presets = [CellPresets.LFP_5AH]
        results = CellSelectionScorer.score(requirements, presets)
        
        summary = ExecutiveSummaryFormatter.from_cell_selection_results(
            results[0], results, requirements
        )
        
        # Should contain plain language name, not just abbreviation
        assert 'lithium iron phosphate' in summary.lower() or 'LFP' not in summary


# ============================================================================
# INTEGRATION TEST SUITE
# ============================================================================

class TestCellSelectionWizardIntegration:
    """End-to-end integration tests."""
    
    def test_wizard_full_workflow(self):
        """Complete workflow: call wizard, get results, parse JSON, read Markdown."""
        api = AgentAPI()
        
        # Call wizard
        result = api.cell_selection_wizard(
            range_km=350,
            power_kW=120,
            weight_budget_kg=450,
            lifetime_years=8,
            charge_time_min=30,
        )
        
        # Verify JSON is valid
        assert isinstance(result.json_data['rankings'], list)
        assert len(result.json_data['rankings']) > 0
        
        # Verify Markdown is readable
        assert 'Recommendation' in result.markdown_text or 'recommendation' in result.markdown_text.lower()
        
        # Verify session tracking
        summary = api.get_session_summary()
        assert 'cell_selection_wizard' in summary.lower() or 'selection' in summary.lower()
    
    def test_wizard_consistent_across_runs(self):
        """Same requirements should produce consistent rankings."""
        api1 = AgentAPI()
        api2 = AgentAPI()
        
        requirements_set = {
            'range_km': 400,
            'power_kW': 150,
            'weight_budget_kg': 500,
            'lifetime_years': 8,
        }
        
        result1 = api1.cell_selection_wizard(**requirements_set)
        result2 = api2.cell_selection_wizard(**requirements_set)
        
        # Top preset should be same
        assert result1.json_data['rankings'][0]['preset_name'] == result2.json_data['rankings'][0]['preset_name']
        
        # Scores should be identical
        assert result1.json_data['rankings'][0]['total_score'] == result2.json_data['rankings'][0]['total_score']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
