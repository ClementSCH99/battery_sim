"""Charging strategy builder."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import numpy as np
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol, CC_CV, ConstantCurrent, Rest, PowerStep
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import SolverConfig
from battery_sim.core.simulation import Simulation
from battery_sim.core.experiment import DegradationConfig
from battery_sim.core.simulation import SimulationBackend
from battery_sim.experimental.charging.strategies.models import (
    ChargingStrategyComparison, ChargingStrategyMetrics,
)

class ChargingStrategyBuilder:
    """Factory for creating predefined charging strategies."""

    @staticmethod
    def _require_nominal_capacity(cell: Cell) -> float:
        """Charging strategy comparisons require an explicit nominal capacity."""
        capacity = cell.nominal_capacity_Ah
        if capacity is None or capacity <= 0:
            raise ValueError(
                "Charging strategy evaluation requires cell.nominal_capacity_Ah > 0"
            )
        return capacity
    
    @staticmethod
    def get_max_voltage(chemistry: str) -> float:
        """Get safe charging voltage for chemistry."""
        bounds = {
            'LFP': 3.65,
            'NMC': 4.2,
            'NCA': 4.2,
            'LCO': 4.2,
        }
        return bounds.get(chemistry, 4.2)
    
    @staticmethod
    def standard_1C(cell: Cell) -> Protocol:
        """Standard CC-CV charging at 1C (rated capacity per hour)."""
        max_voltage = ChargingStrategyBuilder.get_max_voltage(cell.chemistry)
        charge_current = ChargingStrategyBuilder._require_nominal_capacity(cell)
        taper_current = charge_current * 0.2  # 20% of CC current
        return Protocol.cccv(charge_current, max_voltage, taper_current)
    
    @staticmethod
    def fast_2C(cell: Cell) -> Protocol:
        """Fast CC-CV charging at 2C."""
        max_voltage = ChargingStrategyBuilder.get_max_voltage(cell.chemistry)
        charge_current = 2.0 * ChargingStrategyBuilder._require_nominal_capacity(cell)
        taper_current = charge_current * 0.2
        return Protocol.cccv(charge_current, max_voltage, taper_current)
    
    @staticmethod
    def gentle_0_5C(cell: Cell) -> Protocol:
        """Gentle CC-CV charging at 0.5C."""
        max_voltage = ChargingStrategyBuilder.get_max_voltage(cell.chemistry)
        charge_current = 0.5 * ChargingStrategyBuilder._require_nominal_capacity(cell)
        taper_current = charge_current * 0.2
        return Protocol.cccv(charge_current, max_voltage, taper_current)
    
    @staticmethod
    def multi_step_cc(cell: Cell) -> Protocol:
        """
        Multi-step constant current charging: start fast, reduce step-wise.
        
        Approximation: Use time-based PowerStep segments instead of true SOC-based.
        Reduces high-voltage-high-current stress which damages battery faster.
        
        Profile: 2C for 1min → 1.5C for 2min → 1C for 3min → 0.5C until full
        """
        capacity = ChargingStrategyBuilder._require_nominal_capacity(cell)
        
        # Time-based approximation of multi-step charging
        step_1_current = 2.0 * capacity
        step_2_current = 1.5 * capacity
        step_3_current = 1.0 * capacity
        step_4_current = 0.5 * capacity
        
        steps = [
            ConstantCurrent(current_A=-step_1_current, _duration_s=60),    # 1 min at 2C
            ConstantCurrent(current_A=-step_2_current, _duration_s=120),   # 2 min at 1.5C
            ConstantCurrent(current_A=-step_3_current, _duration_s=180),   # 3 min at 1C
            ConstantCurrent(current_A=-step_4_current, _duration_s=600),   # 10 min at 0.5C (to ~full)
            Rest(_duration_s=600),  # Post-charge rest
        ]
        return Protocol(steps=steps)
    
    @staticmethod
    def pulse_charging_0_5C(cell: Cell) -> Protocol:
        """
        Pulse charging: brief rest periods during charge reduce lithium plating.
        
        Profile: 0.5C current, 5 min pulse + 30s rest, repeat until full
        Uses approximation: 3 pulses then gentle to full
        """
        capacity = ChargingStrategyBuilder._require_nominal_capacity(cell)
        charge_current = 0.5 * capacity
        
        steps = []
        # 3 pulse cycles
        for _ in range(3):
            steps.append(ConstantCurrent(current_A=-charge_current, _duration_s=300))  # 5 min pulse
            steps.append(Rest(_duration_s=30))  # 30s rest
        
        # Final gentle top-up with CC-CV
        max_voltage = ChargingStrategyBuilder.get_max_voltage(cell.chemistry)
        taper_current = charge_current * 0.2
        steps.append(CC_CV(charge_current, max_voltage, taper_current))
        
        return Protocol(steps=steps)
    
    @classmethod
    def build(cls, cell: Cell, strategy_names: Optional[List[str]] = None) -> Dict[str, Protocol]:
        """
        Build a set of charging protocols for the cell.
        
        Args:
            cell: Battery cell
            strategy_names: Which strategies to include (None = all built-in)
        
        Returns:
            Dict mapping strategy name to Protocol
        """
        all_strategies = {
            "standard_1C": cls.standard_1C(cell),
            "fast_2C": cls.fast_2C(cell),
            "gentle_0.5C": cls.gentle_0_5C(cell),
            "multi_step_CC": cls.multi_step_cc(cell),
            "pulse_0.5C": cls.pulse_charging_0_5C(cell),
        }
        
        if strategy_names is None:
            return all_strategies
        unknown = sorted(set(strategy_names) - set(all_strategies))
        if unknown:
            available = ", ".join(all_strategies)
            raise ValueError(
                f"Unknown charging strategies: {', '.join(unknown)}. Available: {available}"
            )
        return {name: all_strategies[name] for name in strategy_names}
