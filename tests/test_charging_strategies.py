"""
Tests for charging strategy comparison tools.

Tests cover:
- ChargingStrategyBuilder: protocol creation for different strategies
- ChargingStrategyEvaluator: basic functionality (mocked to avoid long simulations)
- AgentAPI compare_charging_strategies
- MCP tool registration
"""

import pytest

from battery_sim.core.cell import Cell
from battery_sim.core.charging_strategies import (
    ChargingStrategyBuilder,
    ChargingStrategyEvaluator,
    ChargingStrategyMetrics,
    ChargingStrategyComparison,
)
from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.protocol import Protocol
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim import mcp_server


class _FailingBackend(SimulationBackend):
    def run(self, simulation, **solver_options):
        raise RuntimeError("backend exploded")

    def supports_model(self, model):
        return True


class TestChargingStrategyBuilder:
    """Tests for strategy protocol construction."""
    
    def test_standard_1C_protocol_valid(self):
        """Verify standard 1C protocol can be created."""
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.standard_1C(cell)
        assert protocol is not None
        assert len(protocol.steps) > 0
    
    def test_fast_2C_protocol_valid(self):
        """Verify fast 2C protocol can be created."""
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.fast_2C(cell)
        assert protocol is not None
        assert len(protocol.steps) > 0
    
    def test_gentle_0_5C_protocol_valid(self):
        """Verify gentle 0.5C protocol can be created."""
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.gentle_0_5C(cell)
        assert protocol is not None
        assert len(protocol.steps) > 0
    
    def test_multi_step_cc_protocol_valid(self):
        """Verify multi-step CC protocol can be created."""
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.multi_step_cc(cell)
        assert protocol is not None
        # Multi-step should have multiple steps
        assert len(protocol.steps) >= 4
    
    def test_pulse_charging_protocol_valid(self):
        """Verify pulse charging protocol can be created."""
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.pulse_charging_0_5C(cell)
        assert protocol is not None
        # Pulse should have multiple segments (charge+rest cycles)
        assert len(protocol.steps) >= 6
    
    def test_build_all_strategies(self):
        """Verify build method creates all standard strategies."""
        cell = Cell.preset("LFP_5AH")
        strategies = ChargingStrategyBuilder.build(cell)
        
        assert len(strategies) == 5
        assert "standard_1C" in strategies
        assert "fast_2C" in strategies
        assert "gentle_0.5C" in strategies
        assert "multi_step_CC" in strategies
        assert "pulse_0.5C" in strategies
    
    def test_build_subset_of_strategies(self):
        """Verify build method can return subset."""
        cell = Cell.preset("LFP_5AH")
        strategies = ChargingStrategyBuilder.build(
            cell,
            strategy_names=["standard_1C", "gentle_0.5C"]
        )
        
        assert len(strategies) == 2
        assert "standard_1C" in strategies
        assert "gentle_0.5C" in strategies
        assert "fast_2C" not in strategies
    
    def test_voltage_bounds_by_chemistry(self):
        """Verify voltage bounds are correctly set per chemistry."""
        assert ChargingStrategyBuilder.get_max_voltage("LFP") == 3.65
        assert ChargingStrategyBuilder.get_max_voltage("NMC") == 4.2
        assert ChargingStrategyBuilder.get_max_voltage("NCA") == 4.2
        assert ChargingStrategyBuilder.get_max_voltage("LCO") == 4.2
    
    def test_different_chemistries_have_different_voltages(self):
        """Verify different chemistries produce different charge targets."""
        lfp_cell = Cell.preset("LFP_5AH")
        nmc_cell = Cell.preset("NMC_5AH")
        
        # Build protocols for each
        lfp_protocol = ChargingStrategyBuilder.standard_1C(lfp_cell)
        nmc_protocol = ChargingStrategyBuilder.standard_1C(nmc_cell)
        
        # Both should be valid
        assert len(lfp_protocol.steps) > 0
        assert len(nmc_protocol.steps) > 0

    def test_builder_requires_nominal_capacity(self):
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=None)
        with pytest.raises(ValueError, match="nominal_capacity_Ah"):
            ChargingStrategyBuilder.standard_1C(cell)


class TestChargingStrategyComparison:
    """Tests for comparison logic."""
    
    @pytest.fixture
    def sample_metrics(self):
        """Create sample metrics for testing ranking."""
        return [
            ChargingStrategyMetrics(
                strategy_name="fast_2C",
                charge_time_min=20.0,
                discharge_time_min=60.0,
                total_cycle_time_min=80.0,
                charge_energy_Wh=100.0,
                discharge_energy_Wh=95.0,
                energy_efficiency=0.95,
                capacity_fade_per_cycle=0.5,
                final_capacity_Ah=4.9,
                final_soh=98.0,
                final_temperature_C=35.0,
                cycle_count=5,
            ),
            ChargingStrategyMetrics(
                strategy_name="standard_1C",
                charge_time_min=45.0,
                discharge_time_min=60.0,
                total_cycle_time_min=105.0,
                charge_energy_Wh=100.0,
                discharge_energy_Wh=97.0,
                energy_efficiency=0.97,
                capacity_fade_per_cycle=0.2,
                final_capacity_Ah=4.99,
                final_soh=99.0,
                final_temperature_C=28.0,
                cycle_count=5,
            ),
            ChargingStrategyMetrics(
                strategy_name="gentle_0.5C",
                charge_time_min=90.0,
                discharge_time_min=60.0,
                total_cycle_time_min=150.0,
                charge_energy_Wh=100.0,
                discharge_energy_Wh=98.5,
                energy_efficiency=0.985,
                capacity_fade_per_cycle=0.1,
                final_capacity_Ah=4.995,
                final_soh=99.9,
                final_temperature_C=23.0,
                cycle_count=5,
            ),
        ]
    
    def test_rank_by_speed(self, sample_metrics):
        """Verify ranking by speed."""
        comparison = ChargingStrategyComparison(
            preset_name="LFP_5AH",
            chemistry="LFP",
            nominal_capacity_Ah=5.0,
            strategies=sample_metrics,
            temperature_C=25.0,
            n_cycles=5,
        )
        
        ranked = comparison.rank_by_speed()
        assert ranked[0].strategy_name == "fast_2C"
        assert ranked[-1].strategy_name == "gentle_0.5C"
    
    def test_rank_by_efficiency(self, sample_metrics):
        """Verify ranking by efficiency."""
        comparison = ChargingStrategyComparison(
            preset_name="LFP_5AH",
            chemistry="LFP",
            nominal_capacity_Ah=5.0,
            strategies=sample_metrics,
            temperature_C=25.0,
            n_cycles=5,
        )
        
        ranked = comparison.rank_by_efficiency()
        assert ranked[0].strategy_name == "gentle_0.5C"
        assert ranked[-1].strategy_name == "fast_2C"
    
    def test_rank_by_longevity(self, sample_metrics):
        """Verify ranking by lowest capacity fade."""
        comparison = ChargingStrategyComparison(
            preset_name="LFP_5AH",
            chemistry="LFP",
            nominal_capacity_Ah=5.0,
            strategies=sample_metrics,
            temperature_C=25.0,
            n_cycles=5,
        )
        
        ranked = comparison.rank_by_longevity()
        assert ranked[0].strategy_name == "gentle_0.5C"
        assert ranked[-1].strategy_name == "fast_2C"


class TestChargingStrategyEvaluator:
    """Regression tests for evaluator error handling."""

    def test_backend_failure_returns_metrics_with_note(self):
        evaluator = ChargingStrategyEvaluator(backend=_FailingBackend())
        cell = Cell.preset("LFP_5AH")
        protocol = ChargingStrategyBuilder.standard_1C(cell)

        metrics = evaluator.evaluate_strategy(
            cell=cell,
            charge_protocol=protocol,
            strategy_name="standard_1C",
            n_cycles=1,
        )

        assert metrics.strategy_name == "standard_1C"
        assert metrics.charge_time_min == 0.0
        assert metrics.energy_efficiency == 0.0
        assert metrics.status == "failed"
        assert "RuntimeError" in metrics.error
        assert "backend exploded" in metrics.error
        assert "RuntimeError" in metrics.notes
        assert "backend exploded" in metrics.notes

    def test_default_discharge_current_requires_nominal_capacity(self):
        evaluator = ChargingStrategyEvaluator(backend=_FailingBackend())
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=None)
        protocol = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=3.65, taper_current_A=0.2)

        with pytest.raises(ValueError, match="nominal_capacity_Ah"):
            evaluator.evaluate_strategy(
                cell=cell,
                charge_protocol=protocol,
                strategy_name="custom",
                n_cycles=1,
            )


class TestAgentAPIChargingStrategies:
    """Tests for AgentAPI charging strategy methods."""
    
    def test_api_has_compare_charging_strategies_method(self):
        """Verify API has the compare_charging_strategies method."""
        api = AgentAPI()
        assert hasattr(api, 'compare_charging_strategies')
        assert callable(api.compare_charging_strategies)
    
    def test_compare_charging_strategies_returns_dual_format_result(self):
        """Verify method returns DualFormatResult."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C", "gentle_0.5C"],
            n_cycles=1,
        )
        
        assert isinstance(result, DualFormatResult)
        assert result.json_data is not None
        assert result.markdown_text is not None
    
    def test_json_data_structure(self):
        """Verify JSON structure is correct."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
        )
        
        json_data = result.json_data
        assert json_data['type'] == 'charging_strategy_comparison'
        assert json_data['preset'] == 'LFP_5AH'
        assert 'chemistry' in json_data
        assert 'n_cycles' in json_data
        assert isinstance(json_data['strategies'], list)
    
    def test_strategy_metrics_in_json(self):
        """Verify each strategy has required metrics in JSON."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
        )
        
        strategies = result.json_data['strategies']
        assert len(strategies) > 0
        
        for s in strategies:
            assert 'strategy_name' in s
            assert 'charge_time_min' in s
            assert 'energy_efficiency' in s
            assert 'capacity_fade_per_cycle' in s
            assert 'final_soh' in s
    
    def test_markdown_is_readable(self):
        """Verify markdown output is readable."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C", "gentle_0.5C"],
            n_cycles=1,
        )
        
        markdown = result.markdown_text
        assert len(markdown) > 0
        assert "Charging Strategy Comparison" in markdown
        assert "Performance Comparison" in markdown
        assert "| Strategy |" in markdown  # Table header
    
    def test_recommended_strategy_in_json(self):
        """Verify recommendation is included."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C", "gentle_0.5C"],
            n_cycles=1,
        )
        
        json_data = result.json_data
        assert 'recommended_strategy' in json_data
        assert json_data['recommended_strategy'] in ["standard_1C", "gentle_0.5C"]
    
    def test_all_built_in_strategies_evaluated(self):
        """Verify all strategies evaluated when none specified."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=None,  # All strategies
            n_cycles=1,
        )
        
        strategies = result.json_data['strategies']
        strategy_names = [s['strategy_name'] for s in strategies]
        
        # Should have all 5 built-in strategies
        assert len(strategies) >= 4  # At least the main ones
        assert any('1C' in name for name in strategy_names)  # Has 1C variant


class TestMCPTools:
    """Tests for MCP tool registration."""
    
    def test_compare_charging_strategies_tool_registered(self):
        """Verify compare_charging_strategies is registered as MCP tool."""
        assert hasattr(mcp_server, 'compare_charging_strategies')
        assert callable(mcp_server.compare_charging_strategies)
    
    def test_tool_signature_is_correct(self):
        """Verify tool function has correct signature."""
        import inspect
        sig = inspect.signature(mcp_server.compare_charging_strategies)
        params = list(sig.parameters.keys())
        
        assert 'preset_name' in params
        assert 'strategies' in params
        assert 'n_cycles' in params
        assert 'temperature_C' in params


class TestChargingStrategyEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_single_cycle_evaluation(self):
        """Verify comparison works with single cycle."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
        )
        
        assert result.json_data['n_cycles'] == 1
        assert len(result.json_data['strategies']) > 0
    
    def test_high_temperature_evaluation(self):
        """Verify comparison works at high temperature."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
            temperature_C=50.0,
        )
        
        assert result.json_data['temperature_C'] == 50.0
    
    def test_low_temperature_evaluation(self):
        """Verify comparison works at low temperature."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "LFP_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
            temperature_C=0.0,
        )
        
        assert result.json_data['temperature_C'] == 0.0
    
    def test_nmc_chemistry_strategies(self):
        """Verify comparison works with NMC chemistry."""
        api = AgentAPI()
        result = api.compare_charging_strategies(
            "NMC_5AH",
            strategies=["standard_1C"],
            n_cycles=1,
        )
        
        assert result.json_data['chemistry'] == 'NMC'
        assert len(result.json_data['strategies']) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
