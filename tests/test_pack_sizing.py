"""
Tests for pack sizing tool.

TEACHING: These tests verify:
1. PackSizer math: correct series/parallel calculation
2. pack_sizing API returns valid DualFormatResult
3. Edge cases and constraint handling
4. Physical metrics consistency
"""

import pytest
import math
from battery_sim.core.cell import CellPresets
from battery_sim.core.investigation_tools import PackSizer, PackConfiguration
from battery_sim.core.pack import PackSizer as FocusedPackSizer
from battery_sim.core.agent_api import AgentAPI


class TestPackSizerMath:
    """Test core PackSizer calculation logic."""

    def test_legacy_import_is_identity_compatible(self):
        assert PackSizer is FocusedPackSizer
    
    def test_size_pack_basic_lfp(self):
        """Test basic pack sizing with LFP_5AH."""
        lfp = CellPresets.get('LFP_5AH')
        
        # Target: 60 kWh pack with 300-400V range
        config = PackSizer.size_pack(
            cell_preset=lfp,
            target_energy_kWh=60.0,
            voltage_range=(300.0, 400.0),
        )
        
        # Verify output type
        assert isinstance(config, PackConfiguration)
        
        # Verify series count is reasonable for LFP (3.2V nominal)
        # Target voltage = 350V (midpoint), so 350/3.2 ≈ 109 series
        assert 90 < config.n_series < 130, f"Got {config.n_series}S (expected ~109S)"
        
        # Verify pack voltage is in range
        assert 300 <= config.pack_voltage_nominal_V <= 400
        
        # Verify parallel count is positive
        assert config.n_parallel >= 1
        
        # Verify total cells
        assert config.total_cells == config.n_series * config.n_parallel
        
        # Verify actual energy >= target energy (round-up)
        assert config.pack_energy_kWh >= 60.0
        assert config.pack_energy_kWh < 65.0  # Should not be too much more
    
    def test_size_pack_nmc(self):
        """Test pack sizing with NMC_5AH (higher voltage)."""
        nmc = CellPresets.get('NMC_5AH')
        
        config = PackSizer.size_pack(
            cell_preset=nmc,
            target_energy_kWh=60.0,
            voltage_range=(300.0, 400.0),
        )
        
        # NMC is 3.7V nominal, so 350V midpoint / 3.7V ≈ 95S
        assert 85 < config.n_series < 110
        assert config.pack_voltage_nominal_V >= 300
        assert config.pack_voltage_nominal_V <= 400
    
    def test_pack_voltage_calculation(self):
        """Test that pack voltage = n_series × cell_voltage."""
        lfp = CellPresets.get('LFP_5AH')
        config = PackSizer.size_pack(
            cell_preset=lfp,
            target_energy_kWh=50.0,
        )
        
        expected_voltage = config.n_series * lfp.cell.nominal_voltage_V
        assert abs(config.pack_voltage_nominal_V - expected_voltage) < 0.01
    
    def test_pack_capacity_calculation(self):
        """Test that pack capacity = n_parallel × cell_capacity."""
        nmc = CellPresets.get('NMC_5AH')
        config = PackSizer.size_pack(
            cell_preset=nmc,
            target_energy_kWh=75.0,
        )
        
        expected_capacity = config.n_parallel * nmc.cell.nominal_capacity_Ah
        assert abs(config.pack_capacity_Ah - expected_capacity) < 0.01
    
    def test_pack_energy_calculation(self):
        """Test that pack energy = voltage × capacity / 1000."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('LFP_5AH'),
            target_energy_kWh=60.0,
        )
        
        expected_energy = config.pack_voltage_nominal_V * config.pack_capacity_Ah / 1000.0
        assert abs(config.pack_energy_kWh - expected_energy) < 0.01
    
    def test_pack_weight_calculation(self):
        """Test that pack weight = total_cells × cell_weight + overhead."""
        lfp = CellPresets.get('LFP_5AH')
        config = PackSizer.size_pack(
            cell_preset=lfp,
            target_energy_kWh=50.0,
        )
        
        # Cells-only weight
        expected_pack_weight = config.total_cells * lfp.weight_kg
        assert abs(config.pack_weight_kg - expected_pack_weight) < 0.1
        
        # System weight = pack weight + 20% overhead
        expected_system_weight = expected_pack_weight * (1 + PackSizer.SYSTEM_OVERHEAD_WEIGHT_FRACTION)
        assert abs(config.system_weight_kg - expected_system_weight) < 0.1
    
    def test_pack_volume_calculation(self):
        """Test that pack volume = total_cells × cell_volume + overhead."""
        nmc = CellPresets.get('NMC_5AH')
        config = PackSizer.size_pack(
            cell_preset=nmc,
            target_energy_kWh=60.0,
        )
        
        # Cells-only volume
        expected_pack_volume = config.total_cells * nmc.volume_L
        assert abs(config.pack_volume_L - expected_pack_volume) < 0.5
        
        # System volume = pack volume + 30% overhead
        expected_system_volume = expected_pack_volume * (1 + PackSizer.SYSTEM_OVERHEAD_VOLUME_FRACTION)
        assert abs(config.system_volume_L - expected_system_volume) < 1.0
    
    def test_pack_cost_calculation(self):
        """Test that pack cost = total_cells × cell_cost."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('LFP_5AH'),
            target_energy_kWh=60.0,
        )
        
        lfp = CellPresets.get('LFP_5AH')
        expected_cost = config.total_cells * lfp.cost_usd
        assert abs(config.pack_cost_usd - expected_cost) < 1.0  # $1 tolerance
    
    def test_energy_density_metrics(self):
        """Test energy density calculations."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
        )
        
        # Cells-only energy density
        expected_pack_density = (config.pack_energy_kWh * 1000) / config.pack_weight_kg
        assert abs(config.pack_energy_density_Wh_per_kg - expected_pack_density) < 0.1
        
        # System-level energy density (with overhead)
        expected_system_density = (config.pack_energy_kWh * 1000) / config.system_weight_kg
        assert abs(config.system_energy_density_Wh_per_kg - expected_system_density) < 0.1
        
        # System density should be lower than pack density (overhead penalty)
        assert config.system_energy_density_Wh_per_kg < config.pack_energy_density_Wh_per_kg
    
    def test_cost_per_kwh(self):
        """Test cost per kWh calculation."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('LFP_5AH'),
            target_energy_kWh=60.0,
        )
        
        expected_cost_per_kwh = config.pack_cost_usd / config.pack_energy_kWh
        assert abs(config.cost_per_kWh - expected_cost_per_kwh) < 1.0  # $1/kWh tolerance
    
    def test_voltage_range_constraint_narrow(self):
        """Test that narrow voltage range is respected."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('LFP_5AH'),
            target_energy_kWh=50.0,
            voltage_range=(350.0, 370.0),  # Narrow range
        )
        
        assert 350.0 <= config.pack_voltage_nominal_V <= 370.0
    
    def test_voltage_range_constraint_wide(self):
        """Test that wide voltage range works."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=75.0,
            voltage_range=(250.0, 450.0),  # Wide range
        )
        
        assert 250.0 <= config.pack_voltage_nominal_V <= 450.0
    
    def test_small_target_energy(self):
        """Test pack sizing with very small target energy."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=1.0,  # Very small: 1 kWh
        )
        
        # Should still work with minimal parallel
        assert config.n_parallel >= 1
        assert config.total_cells >= config.n_series


class TestPackSizingAPI:
    """Test pack_sizing method in AgentAPI."""
    
    def test_pack_sizing_returns_dual_format(self):
        """Test that pack_sizing returns DualFormatResult."""
        api = AgentAPI()
        result = api.pack_sizing(
            preset_name='LFP_5AH',
            target_energy_kWh=60.0,
        )
        
        # Check result structure
        assert hasattr(result, 'json_data')
        assert hasattr(result, 'markdown_text')
        assert hasattr(result, 'interpretation_hints')
    
    def test_pack_sizing_json_structure(self):
        """Test that JSON output has expected structure."""
        api = AgentAPI()
        result = api.pack_sizing(
            preset_name='NMC_5AH',
            target_energy_kWh=60.0,
        )
        
        json_data = result.json_data
        assert json_data['type'] == 'pack_sizing'
        assert json_data['preset'] == 'NMC_5AH'
        assert json_data['target_energy_kWh'] == 60.0
        
        # Check configuration fields
        config = json_data['configuration']
        assert 'n_series' in config
        assert 'n_parallel' in config
        assert 'total_cells' in config
        assert config['pack_energy_kWh'] >= 60.0
    
    def test_pack_sizing_markdown_readable(self):
        """Test that markdown output is readable and informative."""
        api = AgentAPI()
        result = api.pack_sizing(
            preset_name='LFP_5AH',
            target_energy_kWh=60.0,
        )
        
        markdown = result.markdown_text
        assert 'Pack Sizing' in markdown
        assert 'Configuration' in markdown
        assert 'Physical Metrics' in markdown
        assert 'Industry Benchmark' in markdown
        assert 'LFP_5AH' in markdown
        assert '60' in markdown
    
    def test_pack_sizing_different_chemistries(self):
        """Test pack_sizing with different chemistries."""
        api = AgentAPI()
        
        lfp_result = api.pack_sizing('LFP_5AH', 60.0)
        nmc_result = api.pack_sizing('NMC_5AH', 60.0)
        nca_result = api.pack_sizing('NCA_5AH', 60.0)
        
        # All should succeed
        assert 'configuration' in lfp_result.json_data
        assert 'configuration' in nmc_result.json_data
        assert 'configuration' in nca_result.json_data
        
        # LFP should have more series (lower voltage)
        lfp_s = lfp_result.json_data['configuration']['n_series']
        nmc_s = nmc_result.json_data['configuration']['n_series']
        nca_s = nca_result.json_data['configuration']['n_series']
        
        assert lfp_s > nmc_s  # LFP is 3.2V, NMC is 3.7V
        assert nmc_s >= nca_s  # Both NMC and NCA are similar voltage
    
    def test_pack_sizing_different_target_energies(self):
        """Test pack_sizing with different target energies."""
        api = AgentAPI()
        
        small = api.pack_sizing('NMC_5AH', 30.0)
        medium = api.pack_sizing('NMC_5AH', 60.0)
        large = api.pack_sizing('NMC_5AH', 100.0)
        
        # Larger packs should have more parallel
        small_p = small.json_data['configuration']['n_parallel']
        medium_p = medium.json_data['configuration']['n_parallel']
        large_p = large.json_data['configuration']['n_parallel']
        
        assert small_p < medium_p < large_p
    
    def test_pack_sizing_session_recording(self):
        """Test that pack_sizing records in session."""
        api = AgentAPI()
        result = api.pack_sizing('LFP_5AH', 60.0)
        
        # Should be recorded in session
        session_summary = api.session.get_investigation_history()
        assert len(session_summary) > 0
        assert any('pack_sizing' in str(inv) for inv in session_summary)


class TestPackConfigurationEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_very_high_target_energy(self):
        """Test pack sizing with very high target energy (e.g., semi-truck)."""
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=500.0,  # Large pack
        )
        
        # Should scale appropriately
        assert config.total_cells > 10000
        assert config.system_weight_kg > 1000  # Heavy pack
    
    def test_different_voltage_ranges(self):
        """Test that different voltage ranges produce different configurations."""
        # Lower voltage range (fewer series, more parallel)
        config_low = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
            voltage_range=(200.0, 300.0),  # Midpoint 250V
        )
        
        # Higher voltage range (more series, fewer parallel)
        config_high = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
            voltage_range=(350.0, 450.0),  # Midpoint 400V
        )
        
        # Lower voltage range should have fewer series
        assert config_low.n_series < config_high.n_series
        
        # Parallel should be higher in low-voltage case to maintain energy
        assert config_low.n_parallel > config_high.n_parallel
        
        # Both should meet energy target
        assert config_low.pack_energy_kWh >= 60.0
        assert config_high.pack_energy_kWh >= 60.0
    
    def test_all_presets_can_be_sized(self):
        """Test that all presets can be sized successfully."""
        for preset_name in CellPresets.list_all():
            preset = CellPresets.get(preset_name)
            
            # Should be able to size all presets
            config = PackSizer.size_pack(
                cell_preset=preset,
                target_energy_kWh=60.0,
            )
            
            assert config.total_cells >= 1
            assert config.pack_voltage_nominal_V > 0
            assert config.pack_energy_kWh > 0


class TestPackSizingIndustryRealism:
    """Test that pack sizing produces realistic industry values."""
    
    def test_realistic_energy_density(self):
        """Test that system energy density matches industry benchmarks."""
        # Typical EV packs: 120-185 Wh/kg
        
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
        )
        
        # System-level should be in realistic range
        assert 80 < config.system_energy_density_Wh_per_kg < 250
        
        # Typical modern EV: 150-170 Wh/kg
        # Our calculation should be reasonable
        assert config.system_energy_density_Wh_per_kg > 100
    
    def test_realistic_pack_count(self):
        """Test that pack counts match real EV configurations."""
        # Tesla Model 3: ~96S configuration
        # Typical EV: 80-120S for 300-400V packs
        
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
            voltage_range=(300.0, 400.0),
        )
        
        # NMC 3.7V nominal → 300-400V range needs ~81-108S
        assert 75 <= config.n_series <= 120
    
    def test_realistic_cell_count_60kwh(self):
        """Test that total cell count is realistic for 60 kWh pack."""
        # Typical: 1500-2000 cells for 60 kWh pack
        
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
        )
        
        # 60 kWh ÷ (5Ah × 3.7V = 18.5Wh) ≈ 3243 cells
        # But with rounding and constraints, should be in reasonable range
        assert 1000 < config.total_cells < 10000
    
    def test_realistic_weight_60kwh(self):
        """Test that 60 kWh pack weight is realistic."""
        # Typical 60 kWh pack: 300-450 kg
        
        config = PackSizer.size_pack(
            cell_preset=CellPresets.get('NMC_5AH'),
            target_energy_kWh=60.0,
        )
        
        # With overhead, should be in realistic range
        assert 200 < config.system_weight_kg < 600
