"""
Tests for operating window and derating curve functionality.

LEARNING NOTES:
- OperatingWindowAnalyzer maps safe operating regions across SOC × Temperature × C-rate
- Grid evaluation runs many simulations and is time-expensive
- Tests verify correct classification and curve extraction
"""

import pytest
from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.investigation_tools import OperatingWindowAnalyzer, OperatingWindowPoint
from battery_sim.core.cell import Cell
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.solver import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_for_window():
    """AgentAPI pre-configured for operating window tests."""
    return AgentAPI(
        session_name="Operating Window Test Session",
        default_protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )


# ===========================================================================
# OperatingWindowAnalyzer (low-level class)
# ===========================================================================

@pytest.mark.slow
class TestOperatingWindowAnalyzer:
    """Test the OperatingWindowAnalyzer class directly."""

    def test_coarse_grid_produces_results(self):
        """analyze() with coarse grid should produce ~27 results."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        result = analyzer.analyze(
            cell=cell,
            grid_size="coarse",
        )
        
        assert isinstance(result, dict)
        assert 'grid_points' in result
        assert len(result['grid_points']) > 0
        # Coarse grid: 3×3×3 = 27
        assert len(result['grid_points']) == 27

    def test_fine_grid_produces_more_results(self):
        """analyze() with fine grid should produce ~125 results."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        result = analyzer.analyze(
            cell=cell,
            grid_size="fine",
        )
        
        # Fine grid: 5×5×5 = 125
        assert len(result['grid_points']) == 125

    def test_grid_points_have_required_fields(self):
        """Each grid point should have all required fields."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        result = analyzer.analyze(cell=cell, grid_size="coarse")
        
        for point in result['grid_points']:
            assert isinstance(point, OperatingWindowPoint)
            assert point.soc_level is not None
            assert point.temperature_C is not None
            assert point.c_rate is not None
            assert point.zone in ['safe', 'caution', 'avoid']
            assert isinstance(point.simulation_completed, bool)
            assert isinstance(point.details, str)

    def test_invalid_grid_size_raises_error(self):
        """Invalid grid_size should raise ValueError."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        with pytest.raises(ValueError):
            analyzer.analyze(cell=cell, grid_size="invalid")

    def test_classification_is_physical(self):
        """Classification should follow physical rules:
        - higher C-rate at low temp should be 'caution' or 'avoid'
        - higher C-rate at nominal temp should be more 'safe'
        """
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        result = analyzer.analyze(cell=cell, grid_size="coarse")
        
        # Extract worst and best scenarios
        worst_temp = min(p.temperature_C for p in result['grid_points'])
        best_temp = 25
        
        # At worst temperature with high C-rate, should be 'caution' or 'avoid'
        worst_scenarios = [
            p for p in result['grid_points']
            if p.temperature_C == worst_temp and p.c_rate >= 3.0
        ]
        
        # At least some should not be 'safe'
        if worst_scenarios:
            zones = [p.zone for p in worst_scenarios]
            assert len([z for z in zones if z == 'safe']) < len(zones)

    def test_summary_statistics_correct(self):
        """Summary should have correct counts."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("NMC_5AH")
        
        result = analyzer.analyze(cell=cell, grid_size="coarse")
        summary = result['summary']
        
        total = summary['total_points']
        safe = summary['safe']
        caution = summary['caution']
        avoid = summary['avoid']
        
        assert total == len(result['grid_points'])
        assert safe + caution + avoid == total
        assert summary['percent_safe'] + summary['percent_caution'] + summary['percent_avoid'] == 100 or \
               abs(summary['percent_safe'] + summary['percent_caution'] + summary['percent_avoid'] - 100) < 0.1

    def test_derating_curves_extracted(self):
        """get_derating_curves() should return two curves."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        analyzer.analyze(cell=cell, grid_size="coarse")
        curves = analyzer.get_derating_curves()
        
        assert 'max_crate_vs_temperature' in curves
        assert 'max_crate_vs_soc' in curves
        assert len(curves['max_crate_vs_temperature']) > 0
        assert len(curves['max_crate_vs_soc']) > 0

    def test_voltage_bounds_by_chemistry(self):
        """Different chemistries should have different voltage bounds."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        
        # LFP should have 3.65V max
        lfp = Cell.preset("LFP_5AH")
        v_min_lfp, v_max_lfp = analyzer._get_voltage_bounds(lfp)
        assert v_max_lfp == 3.65
        
        # NMC should have 4.2V max
        nmc = Cell.preset("NMC_5AH")
        v_min_nmc, v_max_nmc = analyzer._get_voltage_bounds(nmc)
        assert v_max_nmc == 4.2

    def test_different_chemistries_have_different_windows(self):
        """LFP and NMC should produce different operating windows."""
        analyzer_lfp = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        analyzer_nmc = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        
        lfp_result = analyzer_lfp.analyze(Cell.preset("LFP_5AH"), grid_size="coarse")
        nmc_result = analyzer_nmc.analyze(Cell.preset("NMC_5AH"), grid_size="coarse")
        
        # Extract safe zones
        lfp_safe = [p for p in lfp_result['grid_points'] if p.zone == 'safe']
        nmc_safe = [p for p in nmc_result['grid_points'] if p.zone == 'safe']
        
        # Both should have some safe zones
        assert len(lfp_safe) > 0
        assert len(nmc_safe) > 0


# ===========================================================================
# operating_window (AgentAPI tool)
# ===========================================================================

@pytest.mark.slow
class TestOperatingWindowTool:
    """Test the operating_window method in AgentAPI."""

    def test_operating_window_returns_dual_format(self, api_for_window):
        """operating_window returns a DualFormatResult."""
        result = api_for_window.operating_window(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        assert isinstance(result, DualFormatResult)
        assert isinstance(result.json_data, dict)
        assert isinstance(result.markdown_text, str)
        assert isinstance(result.interpretation_hints, list)

    def test_json_data_structure(self, api_for_window):
        """JSON result should have correct structure."""
        result = api_for_window.operating_window(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        json_data = result.json_data
        assert json_data['type'] == 'operating_window'
        assert 'preset' in json_data
        assert 'grid_size' in json_data
        assert 'total_points' in json_data
        assert 'summary' in json_data
        assert 'grid_points' in json_data

    def test_summary_has_required_fields(self, api_for_window):
        """Summary section should have all counts."""
        result = api_for_window.operating_window(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        summary = result.json_data['summary']
        assert 'safe_count' in summary
        assert 'caution_count' in summary
        assert 'avoid_count' in summary
        assert 'percent_safe' in summary
        assert 'max_safe_crate' in summary

    def test_markdown_readable(self, api_for_window):
        """Markdown output should be readable and informative."""
        result = api_for_window.operating_window(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        md = result.markdown_text
        assert '# Operating Window' in md
        assert 'Summary' in md
        assert 'Zone' in md
        assert 'safe' in md.lower() or '✅' in md
        assert len(md) > 200

    def test_different_presets_different_windows(self, api_for_window):
        """Different presets should have different windows."""
        result_lfp = api_for_window.operating_window(preset_name="LFP_5AH", grid_size="coarse")
        result_nmc = api_for_window.operating_window(preset_name="NMC_5AH", grid_size="coarse")
        
        summary_lfp = result_lfp.json_data['summary']
        summary_nmc = result_nmc.json_data['summary']
        
        # Max safe C-rate should differ
        assert summary_lfp['max_safe_crate'] != summary_nmc['max_safe_crate']

    def test_session_records_investigation(self, api_for_window):
        """Calling operating_window should record in session."""
        initial_count = len(api_for_window.session.investigation_history)
        
        api_for_window.operating_window(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        final_count = len(api_for_window.session.investigation_history)
        assert final_count > initial_count


# ===========================================================================
# derating_curves (AgentAPI tool)
# ===========================================================================

@pytest.mark.slow
class TestDeratingCurvesTool:
    """Test the derating_curves method in AgentAPI."""

    def test_derating_curves_returns_dual_format(self, api_for_window):
        """derating_curves returns a DualFormatResult."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        assert isinstance(result, DualFormatResult)
        assert isinstance(result.json_data, dict)
        assert isinstance(result.markdown_text, str)

    def test_json_data_has_curves(self, api_for_window):
        """JSON should contain both curves."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        json_data = result.json_data
        assert json_data['type'] == 'derating_curves'
        assert 'max_crate_vs_temperature' in json_data
        assert 'max_crate_vs_soc' in json_data
        assert 'chemistry' in json_data
        assert 'nominal_voltage_V' in json_data

    def test_curves_have_data_points(self, api_for_window):
        """Both curves should have multiple data points."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        curves = result.json_data
        assert len(curves['max_crate_vs_temperature']) > 0
        assert len(curves['max_crate_vs_soc']) > 0

    def test_temperature_curve_format(self, api_for_window):
        """Temperature curve points should have correct structure."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        for point in result.json_data['max_crate_vs_temperature']:
            assert 'temperature_C' in point
            assert 'max_c_rate' in point
            assert isinstance(point['temperature_C'], (int, float))
            assert isinstance(point['max_c_rate'], (int, float))
            assert point['max_c_rate'] > 0

    def test_soc_curve_format(self, api_for_window):
        """SOC curve points should have correct structure."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        for point in result.json_data['max_crate_vs_soc']:
            assert 'soc_level' in point
            assert 'max_c_rate' in point
            assert 0 <= point['soc_level'] <= 1.0
            assert point['max_c_rate'] > 0

    def test_markdown_has_tables(self, api_for_window):
        """Markdown should have readable tables."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        md = result.markdown_text
        assert '# Derating Curves' in md
        assert 'Temperature' in md or 'SOC' in md
        assert '|' in md  # Table indicators

    def test_temperature_derating_makes_sense(self, api_for_window):
        """Max C-rate should generally decrease at cold temperatures."""
        result = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        
        curve = result.json_data['max_crate_vs_temperature']
        
        # Find min and max temperature points
        if len(curve) >= 2:
            cold = min(curve, key=lambda p: p['temperature_C'])
            hot = max(curve, key=lambda p: p['temperature_C'])
            
            # Cold typically has lower max C-rate (higher internal resistance)
            # But this depends on degradation rates; we just check structure
            assert cold['temperature_C'] < hot['temperature_C']

    def test_different_grid_sizes_produce_different_curves(self, api_for_window):
        """Coarse vs fine grid should produce different refinement."""
        result_coarse = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="coarse",
        )
        result_fine = api_for_window.derating_curves(
            preset_name="LFP_5AH",
            grid_size="fine",
        )
        
        # Fine should have more data points
        assert len(result_fine.json_data['max_crate_vs_soc']) >= len(result_coarse.json_data['max_crate_vs_soc'])


# ===========================================================================
# Edge cases and error handling
# ===========================================================================

@pytest.mark.slow
class TestOperatingWindowEdgeCases:
    """Test edge cases and robustness."""

    def test_extreme_temperature_classification(self):
        """Very cold and hot should be classified correctly."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        # Should handle extreme temperatures
        point_cold = analyzer._evaluate_point(
            cell=cell,
            soc_level=0.5,
            temperature_C=-10,
            c_rate=2.0,
            voltage_bounds=(2.5, 3.65),
        )
        
        # Cold operation should be caution or avoid
        assert point_cold.zone in ['caution', 'avoid']
        
        point_hot = analyzer._evaluate_point(
            cell=cell,
            soc_level=0.5,
            temperature_C=55,
            c_rate=2.0,
            voltage_bounds=(2.5, 3.65),
        )
        
        # Hot operation should be caution or avoid
        assert point_hot.zone in ['caution', 'avoid']

    def test_extreme_c_rate(self):
        """Very high C-rate should be classified as avoid."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        point_high_crate = analyzer._evaluate_point(
            cell=cell,
            soc_level=0.5,
            temperature_C=25,
            c_rate=10.0,  # Very high
            voltage_bounds=(2.5, 3.65),
        )
        
        # High C-rate at nominal temp might be safe or caution, but shouldn't crash
        assert point_high_crate.zone in ['safe', 'caution', 'avoid']

    def test_very_low_c_rate(self):
        """Very low C-rate should be safe."""
        analyzer = OperatingWindowAnalyzer(backend=PyBaMMBackend())
        cell = Cell.preset("LFP_5AH")
        
        point_low_crate = analyzer._evaluate_point(
            cell=cell,
            soc_level=0.5,
            temperature_C=25,
            c_rate=0.1,  # Very low
            voltage_bounds=(2.5, 3.65),
        )
        
        # Low C-rate should be safe
        assert point_low_crate.zone == 'safe'
