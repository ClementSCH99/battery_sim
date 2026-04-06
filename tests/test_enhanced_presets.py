"""
Tests for enhanced cell presets with EV-specific metadata.

TEACHING: These tests verify:
1. CellPreset computed properties (energy density, cost per kWh)
2. Compare_presets EV metrics calculation
3. Ragone data generation
4. Comparison formatter with EV metrics
"""

import pytest
from battery_sim.core.cell_presets import CellPresets, CellPreset
from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.result_formatter import ComparisonFormatter


class TestCellPresetEnhanced:
    """Test enhanced CellPreset dataclass with weight/volume/cost metadata."""
    
    def test_preset_has_physical_metadata(self):
        """Test that presets include weight, volume, cost."""
        lfp = CellPresets.get('LFP_5AH')
        assert lfp.weight_kg > 0, "LFP_5AH should have weight"
        assert lfp.volume_L > 0, "LFP_5AH should have volume"
        assert lfp.cost_usd > 0, "LFP_5AH should have cost"
        
    def test_preset_has_crate_capability(self):
        """Test that presets include max C-rate specifications."""
        nmc = CellPresets.get('NMC_5AH')
        assert nmc.max_charge_c_rate > 0, "NMC_5AH should have max charge C-rate"
        assert nmc.max_discharge_c_rate >= nmc.max_charge_c_rate, \
            "Discharge C-rate should >= charge C-rate"
    
    def test_energy_density_gravimetric(self):
        """Test gravimetric energy density calculation (Wh/kg)."""
        lfp = CellPresets.get('LFP_5AH')
        nmc = CellPresets.get('NMC_5AH')
        nca = CellPresets.get('NCA_5AH')
        
        # LFP should have lowest energy density (~160 Wh/kg)
        assert lfp.energy_density_Wh_per_kg < 200
        # NMC should be higher (~240-260 Wh/kg)
        assert nmc.energy_density_Wh_per_kg > lfp.energy_density_Wh_per_kg
        # NCA should be highest (~270 Wh/kg)
        assert nca.energy_density_Wh_per_kg > nmc.energy_density_Wh_per_kg
    
    def test_energy_density_volumetric(self):
        """Test volumetric energy density calculation (Wh/L)."""
        lfp = CellPresets.get('LFP_5AH')
        nmc = CellPresets.get('NMC_5AH')
        
        # Both should have positive volumetric density
        assert lfp.energy_density_Wh_per_L > 0
        assert nmc.energy_density_Wh_per_L > 0
        # NMC should typically have higher density
        assert nmc.energy_density_Wh_per_L > lfp.energy_density_Wh_per_L
    
    def test_cost_per_kwh(self):
        """Test cost per kWh calculation."""
        lfp = CellPresets.get('LFP_5AH')
        nmc = CellPresets.get('NMC_5AH')
        
        # LFP typically cheaper per kWh: ~150-200 $/kWh
        assert 100 < lfp.cost_per_kWh < 300
        # NMC typically more expensive per kWh: ~200-250 $/kWh
        assert 100 < nmc.cost_per_kWh < 300
    
    def test_nominal_energy_wh(self):
        """Test nominal energy calculation."""
        preset = CellPresets.get('NMC_5AH')
        expected = preset.cell.nominal_capacity_Ah * preset.cell.nominal_voltage_V
        assert preset.nominal_energy_Wh == expected
    
    def test_cycle_life_extraction(self):
        """Test cycle life parsing from metadata."""
        lfp = CellPresets.get('LFP_5AH')
        nmc = CellPresets.get('NMC_5AH')
        
        # LFP should have longer cycle life
        assert lfp.cycle_life_cycles >= 3000
        # NMC should have shorter cycle life
        assert nmc.cycle_life_cycles >= 1000
        assert nmc.cycle_life_cycles < lfp.cycle_life_cycles
    
    def test_all_presets_have_metadata(self):
        """Test that all presets have the new metadata fields."""
        for preset_name in CellPresets.list_all():
            preset = CellPresets.get(preset_name)
            # Should have defaults or values
            assert preset.weight_kg >= 0
            assert preset.volume_L >= 0
            assert preset.cost_usd >= 0
            assert preset.max_charge_c_rate > 0
            assert preset.max_discharge_c_rate >= 0


class TestEvMetricsComputation:
    """Test EV-specific metrics computation in AgentAPI."""
    
    def test_compute_ev_metrics(self):
        """Test that AgentAPI computes EV metrics correctly."""
        presets = ['LFP_5AH', 'NMC_5AH', 'NCA_5AH']
        metrics = AgentAPI._compute_ev_metrics(presets)
        
        # Should return metrics for all presets
        assert len(metrics) == len(presets)
        assert all(p in metrics for p in presets)
        
        # Each preset should have required EV metrics
        required_metrics = {
            'energy_density_Wh_per_kg',
            'energy_density_Wh_per_L',
            'cost_per_kWh',
            'max_charge_c_rate',
            'max_discharge_c_rate',
            'cycle_life_cycles',
            'nominal_energy_Wh',
        }
        for preset_metrics in metrics.values():
            assert all(metric in preset_metrics for metric in required_metrics)
    
    def test_ev_metrics_values_reasonable(self):
        """Test that computed EV metrics are within reasonable ranges."""
        metrics = AgentAPI._compute_ev_metrics(['LFP_5AH', 'NMC_5AH'])
        
        for preset_name, preset_metrics in metrics.items():
            # Energy density: 100-400 Wh/kg reasonable range
            assert 50 < preset_metrics['energy_density_Wh_per_kg'] < 500
            # Volumetric: 100-600 Wh/L reasonable range
            assert 50 < preset_metrics['energy_density_Wh_per_L'] < 800
            # Cost: $50-500 per kWh reasonable range
            assert 20 < preset_metrics['cost_per_kWh'] < 1000
            # C-rates: 0.5-5C reasonable
            assert 0.1 < preset_metrics['max_charge_c_rate'] <= 5
            assert 0.1 < preset_metrics['max_discharge_c_rate'] <= 10


class TestRagoneDataGeneration:
    """Test Ragone plot data generation."""
    
    def test_ragone_data_generation(self):
        """Test that Ragone data is generated correctly."""
        presets = ['LFP_5AH', 'NMC_5AH']
        ragone = AgentAPI._generate_ragone_data(presets)
        
        # Should have data for all presets
        assert len(ragone) == len(presets)
        assert all(p in ragone for p in presets)
        
        # Each entry should have energy and power density
        for data in ragone.values():
            assert 'energy_density_Wh_per_kg' in data
            assert 'power_density_W_per_kg' in data
            assert data['energy_density_Wh_per_kg'] > 0
            assert data['power_density_W_per_kg'] > 0
    
    def test_ragone_power_energy_tradeoff(self):
        """Test Ragone data shows expected power-energy trade-off."""
        ragone = AgentAPI._generate_ragone_data(['LFP_5AH', 'NMC_5AH'])
        
        # NMC should have higher energy density (more Wh/kg)
        nmc_energy = ragone['NMC_5AH']['energy_density_Wh_per_kg']
        lfp_energy = ragone['LFP_5AH']['energy_density_Wh_per_kg']
        assert nmc_energy > lfp_energy, "NMC should have higher energy density"
        
        # LFP has better power capability (3C) vs NMC (3C), but lower energy
        # Power density should still favor high-power designs
        nmc_power = ragone['NMC_5AH']['power_density_W_per_kg']
        lfp_power = ragone['LFP_5AH']['power_density_W_per_kg']
        # Since both are 3C capable, NMC should dominate both axes
        assert nmc_power > lfp_power
    
    def test_ragone_single_preset(self):
        """Test Ragone generation with single preset (edge case)."""
        ragone = AgentAPI._generate_ragone_data(['LFP_5AH'])
        
        # Should still generate data for single preset
        assert len(ragone) == 1
        assert 'LFP_5AH' in ragone


class TestComparisonFormatterEv:
    """Test ComparisonFormatter with EV metrics."""
    
    def test_format_comparison_with_ev_basic(self):
        """Test basic EV comparison formatting."""
        scenarios = ['LFP_5AH', 'NMC_5AH']
        metrics_dict = {}  # Empty baseline metrics
        
        ev_metrics = AgentAPI._compute_ev_metrics(scenarios)
        ragone_data = AgentAPI._generate_ragone_data(scenarios)
        
        result = ComparisonFormatter.format_comparison_with_ev(
            scenarios,
            metrics_dict,
            ev_metrics=ev_metrics,
            ragone_data=ragone_data,
        )
        
        # Should have JSON data
        assert result.json_data is not None
        assert result.json_data['type'] == 'comparison_with_ev_metrics'
        
        # Should have markdown output
        assert result.markdown_text is not None
        assert 'EV-Specific Metrics' in result.markdown_text
        assert 'Ragone Plot' in result.markdown_text
    
    def test_compute_best_for(self):
        """Test computation of best winner for each metric."""
        scenarios = ['LFP_5AH', 'NMC_5AH', 'NCA_5AH']
        ev_metrics = AgentAPI._compute_ev_metrics(scenarios)
        
        best_for = ComparisonFormatter._compute_best_for({}, ev_metrics)
        
        # Should have best-for entries
        assert len(best_for) > 0
        
        # All entries should be preset names
        for preset_name in best_for.values():
            assert preset_name in scenarios
        
        # NCA should win on energy density
        if 'Gravimetric Energy Density' in best_for:
            assert best_for['Gravimetric Energy Density'] == 'NCA_5AH'
        
        # LFP should win on cycle life
        if 'Cycle Life' in best_for:
            assert best_for['Cycle Life'] == 'LFP_5AH'
    
    def test_ev_metrics_in_markdown(self):
        """Test that EV metrics appear in markdown output."""
        scenarios = ['LFP_5AH', 'NMC_5AH']
        ev_metrics = AgentAPI._compute_ev_metrics(scenarios)
        
        result = ComparisonFormatter.format_comparison_with_ev(
            scenarios,
            {},
            ev_metrics=ev_metrics,
        )
        
        markdown = result.markdown_text
        
        # Should contain all EV metric headings
        assert 'Gravimetric Energy Density' in markdown
        assert 'Volumetric Energy Density' in markdown
        assert 'Cost per kWh' in markdown
        assert 'Max Charge C-Rate' in markdown
        assert 'Cycle Life' in markdown
    
    def test_ragone_data_in_markdown(self):
        """Test that Ragone data appears in markdown output."""
        scenarios = ['LFP_5AH', 'NMC_5AH']
        ragone_data = AgentAPI._generate_ragone_data(scenarios)
        
        result = ComparisonFormatter.format_comparison_with_ev(
            scenarios,
            {},
            ragone_data=ragone_data,
        )
        
        markdown = result.markdown_text
        
        # Should contain Ragone section
        assert 'Ragone Plot' in markdown
        assert 'Power Density' in markdown
        assert 'Energy Density' in markdown


class TestIntegration:
    """Integration tests for enhanced presets."""
    
    def test_compare_presets_end_to_end(self):
        """Test full compare_presets flow with EV metrics."""
        # This is an integration test that exercises the full pipeline
        api = AgentAPI()
        
        # Compare should succeed
        result = api.compare_presets(['LFP_5AH', 'NMC_5AH'])
        
        # Should have EV metrics in output
        assert 'ev_metrics' in result.json_data
        assert 'LFP_5AH' in result.json_data['ev_metrics']
        assert 'NMC_5AH' in result.json_data['ev_metrics']
        
        # Should have Ragone data
        assert 'ragone_data' in result.json_data
        assert 'LFP_5AH' in result.json_data['ragone_data']
        
        # Should have best-for summary
        assert 'best_for' in result.json_data
        
        # Markdown should be readable
        assert result.markdown_text is not None
        assert len(result.markdown_text) > 100
    
    def test_ev_metrics_consistency(self):
        """Test that EV metrics are consistent across API and Formatter."""
        presets = ['LFP_5AH', 'NMC_5AH']
        
        # Get metrics from API
        api_metrics = AgentAPI._compute_ev_metrics(presets)
        
        # Get presets directly
        direct_metrics = {
            name: {
                'energy_density_Wh_per_kg': CellPresets.get(name).energy_density_Wh_per_kg,
                'energy_density_Wh_per_L': CellPresets.get(name).energy_density_Wh_per_L,
                'cost_per_kWh': CellPresets.get(name).cost_per_kWh,
            }
            for name in presets
        }
        
        # Should match
        for preset in presets:
            for metric in ['energy_density_Wh_per_kg', 'energy_density_Wh_per_L', 'cost_per_kWh']:
                assert api_metrics[preset][metric] == direct_metrics[preset][metric]
