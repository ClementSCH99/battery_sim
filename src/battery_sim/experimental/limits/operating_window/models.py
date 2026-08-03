"""Immutable values used by this capability."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import ConstantCurrent, Protocol, Rest
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig

@dataclass(frozen=True)
class OperatingWindowPoint:
    """
    Classification of a single grid point in operating window.
    
    TEACHING: Each (SOC, Temperature, C-rate) tuple is evaluated and classified
    as safe/caution/avoid based on simulation outcome.
    """
    soc_level: float
    """Representative SOC level (0.1=near discharge end, 0.9=freshly charged)"""
    
    temperature_C: float
    """Ambient temperature (°C)"""
    
    c_rate: float
    """Discharge C-rate (C_rate = current_A / capacity_Ah)"""
    
    zone: str
    """Classification: 'safe', 'caution', or 'avoid'"""
    
    voltage_min_V: Optional[float]
    """Minimum voltage during discharge (V)"""
    
    voltage_max_V: Optional[float]
    """Maximum voltage during discharge (V)"""
    
    temperature_rise_C: Optional[float]
    """Temperature rise during discharge (°C)"""
    
    final_soc: Optional[float]
    """Final SOC when simulation completed (%)"""
    
    simulation_completed: bool
    """Whether simulation completed successfully"""
    
    details: str
    """Human-readable classification reason"""
