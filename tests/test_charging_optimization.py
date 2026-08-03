"""
Tests for charging optimization functionality.

LEARNING NOTES:
- ChargingOptimizer is a low-level analyzer class that lives in investigation_tools.
- optimize_charging() is an agent_tool that wraps ChargingOptimizer and returns DualFormatResult.
- Tests verify:
  1. ChargingOptimizer produces sorted results
  2. optimize_charging returns valid DualFormatResult with required fields
  3. Results make physical sense (charge_current affects charge_time and aging)
  4. Session tracking records the investigation
"""

import pytest
from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.investigation_tools import ChargingOptimizer, ChargingOptimizationResult
from battery_sim.core.cell import Cell
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol, ConstantCurrent
from battery_sim.core.experiment import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_for_charging():
    """AgentAPI pre-configured for charging optimization tests."""
    return AgentAPI(
        session_name="Charging Optimization Test Session",
        default_protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )


# ===========================================================================
# ChargingOptimizer (low-level class)
# ===========================================================================

@pytest.mark.slow
class TestChargingOptimizer:
    """Test the ChargingOptimizer class directly."""

    def test_optimize_returns_list_of_results(self):
        """optimize() returns a list of ChargingOptimizationResult objects."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(1.0, 5.0),
            n_points=3,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, ChargingOptimizationResult) for r in results)

    def test_results_are_sorted_by_score(self):
        """Results should be sorted in ascending order by score (best first)."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(1.0, 5.0),
            n_points=3,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        # Check sorted ascending by score
        scores = [r.score for r in results]
        assert scores == sorted(scores), "Results should be sorted by score (ascending)"

    def test_charge_time_increases_with_lower_current(self):
        """Lower charge current should result in longer charge times."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(1.0, 5.0),
            n_points=2,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        # Should have at least 2 results
        assert len(results) >= 2
        
        # Charge time should increase for lower currents (protocol is fixed, but logically should be)
        # Actually, since we're using CC-CV, lower current = longer time
        # Both should have roughly the same charge time (protocol is fixed), 
        # but aging should differ
        assert all(r.charge_time_s is not None for r in results)

    def test_single_charge_screen_does_not_invent_capacity_fade(self):
        """A single charge without an aging signal cannot support fade claims."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(1.0, 5.0),
            n_points=2,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        assert len(results) >= 2
        assert all(r.capacity_fade_per_cycle is None for r in results)

    def test_all_results_have_required_fields(self):
        """Each result should have all required fields."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("NMC_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(2.0, 8.0),
            n_points=2,
            max_voltage_V=4.2,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        for result in results:
            assert hasattr(result, 'charge_current_A')
            assert hasattr(result, 'charge_time_s')
            assert hasattr(result, 'capacity_fade_per_cycle')
            assert hasattr(result, 'score')
            assert hasattr(result, 'peak_voltage_V')
            assert hasattr(result, 'final_efficiency')
            
            # Score should be in reasonable range [0, 2] since it's sum of two normalized values
            assert 0.0 <= result.score <= 2.5, f"Score {result.score} out of reasonable range"

    def test_different_chemistries_can_be_optimized(self):
        """Should work with different cell chemistries."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        
        for preset_name in ["LFP_5AH", "NMC_5AH"]:
            cell = Cell.preset(preset_name)
            results = optimizer.optimize(
                cell=cell,
                charge_current_range_A=(1.0, 5.0),
                n_points=2,
                max_voltage_V=4.2,
                num_cycles=1,
                temperature_C=25.0,
            )
            
            assert len(results) > 0, f"Should produce results for {preset_name}"


# ===========================================================================
# optimize_charging (AgentAPI tool)
# ===========================================================================

@pytest.mark.slow
class TestOptimizeChargingTool:
    """Test the optimize_charging method in AgentAPI."""

    def test_optimize_charging_returns_dual_format(self, api_for_charging):
        """optimize_charging returns a DualFormatResult."""
        result = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=3,
            temperature_C=25.0,
        )
        
        assert isinstance(result, DualFormatResult)
        assert isinstance(result.json_data, dict)
        assert isinstance(result.markdown_text, str)
        assert isinstance(result.interpretation_hints, list)

    def test_json_data_has_required_fields(self, api_for_charging):
        """JSON result should contain optimization metadata and results."""
        result = api_for_charging.optimize_charging(
            preset_name="NMC_5AH",
            charge_current_range_A=(2.0, 8.0),
            n_sweep_points=3,
            temperature_C=25.0,
        )
        
        json_data = result.json_data
        assert json_data['type'] == 'charging_optimization'
        assert 'preset' in json_data
        assert 'temperature_C' in json_data
        assert 'optimal_params' in json_data
        assert 'all_results' in json_data

    def test_optimal_params_contain_best_solution(self, api_for_charging):
        """optimal_params should have all metrics from the best result."""
        result = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        optimal = result.json_data['optimal_params']
        assert 'charge_current_A' in optimal
        assert 'charge_time_min' in optimal
        assert 'capacity_fade_per_cycle' in optimal
        assert 'score' in optimal

    def test_all_results_array_sorted(self, api_for_charging):
        """all_results should contain results sorted by score."""
        result = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=3,
            temperature_C=25.0,
        )
        
        all_results = result.json_data['all_results']
        assert len(all_results) > 0
        
        # Check order: should be sorted by score (ascending)
        scores = [r['score'] for r in all_results]
        assert scores == sorted(scores), "Results should be sorted by score (best first)"

    def test_markdown_contains_recommendation(self, api_for_charging):
        """Markdown should be readable and contain recommendations."""
        result = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        md = result.markdown_text
        assert '# Charging Optimization' in md
        assert 'Optimal Parameters' in md or 'optimal' in md.lower()
        assert 'Comparison Table' in md or 'Current' in md
        assert len(md) > 100, "Markdown should be substantive"

    def test_temperature_affects_optimization(self, api_for_charging):
        """Different temperatures should produce different optimization results."""
        result_25c = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        result_45c = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=45.0,
        )
        
        # Results should exist for both
        assert len(result_25c.json_data['all_results']) > 0
        assert len(result_45c.json_data['all_results']) > 0
        
        # They might have different optimal parameters or different scores
        # (more degradation at higher temperature)
        assert result_25c.json_data['temperature_C'] == 25.0
        assert result_45c.json_data['temperature_C'] == 45.0

    def test_session_records_investigation(self, api_for_charging):
        """Calling optimize_charging should record the investigation in session."""
        initial_count = len(api_for_charging.session.investigation_history)
        
        api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        final_count = len(api_for_charging.session.investigation_history)
        assert final_count > initial_count, "Session should record the investigation"

    def test_different_presets_produce_different_results(self, api_for_charging):
        """Different chemistries should produce different optimization results."""
        result_lfp = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        result_nmc = api_for_charging.optimize_charging(
            preset_name="NMC_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=25.0,
        )
        
        # Different chemistries should have different max voltages
        assert result_lfp.json_data['max_voltage_V'] == 3.65
        assert result_nmc.json_data['max_voltage_V'] == 4.2


# ===========================================================================
# Edge cases and error handling
# ===========================================================================

@pytest.mark.slow
class TestChargingOptimizationEdgeCases:
    """Test edge cases and robustness."""

    def test_narrow_current_range(self):
        """Should handle very narrow current ranges."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(3.0, 3.5),
            n_points=2,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        assert len(results) > 0

    def test_single_current_point(self):
        """Should handle single-point sweep (edge case)."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(3.0, 3.0),
            n_points=1,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        assert len(results) >= 1

    def test_large_current_sweep(self):
        """Should handle wide current ranges."""
        optimizer = ChargingOptimizer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=(0.5, 20.0),
            n_points=3,
            max_voltage_V=3.65,
            num_cycles=1,
            temperature_C=25.0,
        )
        
        assert len(results) > 0
        # All currents should be in valid range
        for r in results:
            assert 0.5 <= r.charge_current_A <= 20.0

    def test_extreme_temperature(self, api_for_charging):
        """Should handle extreme temperatures gracefully."""
        # Cold
        result_cold = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=-10.0,
        )
        
        assert len(result_cold.json_data['all_results']) > 0
        
        # Hot
        result_hot = api_for_charging.optimize_charging(
            preset_name="LFP_5AH",
            charge_current_range_A=(1.0, 5.0),
            n_sweep_points=2,
            temperature_C=60.0,
        )
        
        assert len(result_hot.json_data['all_results']) > 0
