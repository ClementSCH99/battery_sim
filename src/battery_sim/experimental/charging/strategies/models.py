"""Charging strategy models."""

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
@dataclass(frozen=True)
class ChargingStrategyMetrics:
    """Extracted metrics from one charging strategy evaluation."""
    strategy_name: str
    charge_time_min: float
    discharge_time_min: float
    total_cycle_time_min: float
    charge_energy_Wh: float  # Energy input during charge
    discharge_energy_Wh: float  # Energy output during discharge
    energy_efficiency: float  # discharge_energy / charge_energy, 0-1
    capacity_fade_per_cycle: float  # Percentage of capacity lost per cycle
    final_capacity_Ah: float  # Remaining capacity after n_cycles
    final_soh: float  # State of health as % of nominal
    final_temperature_C: float  # Peak temperature during cycling
    cycle_count: int  # Number of cycles simulated
    status: str = "ok"
    error: str = ""
    notes: str = ""
    timing_observed: bool = True
    energy_observed: bool = True
    capacity_fade_observed: bool = True
    resolved_protocol: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChargingStrategyComparison:
    """Results from comparing multiple charging strategies."""
    preset_name: str
    chemistry: str
    nominal_capacity_Ah: float
    strategies: List[ChargingStrategyMetrics]
    temperature_C: float
    n_cycles: int

    def successful_strategies(self) -> List[ChargingStrategyMetrics]:
        """Return only simulations that produced usable metrics."""
        return [strategy for strategy in self.strategies if strategy.status == "ok"]
    
    def rank_by_speed(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by fastest charge time."""
        return sorted(
            [s for s in self.successful_strategies() if s.timing_observed],
            key=lambda s: s.charge_time_min,
        )
    
    def rank_by_efficiency(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by energy efficiency (highest to lowest)."""
        return sorted(
            [s for s in self.successful_strategies() if s.energy_observed],
            key=lambda s: s.energy_efficiency,
            reverse=True,
        )
    
    def rank_by_longevity(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by best cycle life (lowest capacity fade)."""
        return sorted(
            [s for s in self.successful_strategies() if s.capacity_fade_observed],
            key=lambda s: s.capacity_fade_per_cycle,
        )
    
    def rank_balanced(self) -> List[ChargingStrategyMetrics]:
        """Rank by balanced score: speed + efficiency + longevity."""
        successful = [
            strategy
            for strategy in self.successful_strategies()
            if strategy.timing_observed
            and strategy.energy_observed
            and strategy.capacity_fade_observed
        ]
        scores = []
        for s in successful:
            # Normalize each metric 0-1
            # Speed: fast is good (invert time, normalize to max)
            charge_speeds = [x.charge_time_min for x in successful]
            speed_score = 1.0 - (s.charge_time_min / max(charge_speeds)) if max(charge_speeds) > 0 else 0.5
            
            # Efficiency: high is good
            efficiency_score = s.energy_efficiency
            
            # Longevity: low fade is good (invert fade, normalize to max)
            fades = [x.capacity_fade_per_cycle for x in successful]
            longevity_score = 1.0 - (s.capacity_fade_per_cycle / max(fades)) if max(fades) > 0 else 0.5
            
            # Weighted average: 40% speed, 20% efficiency, 40% longevity
            balanced_score = 0.4 * speed_score + 0.2 * efficiency_score + 0.4 * longevity_score
            scores.append((s, balanced_score))
        
        return [s for s, _ in sorted(scores, key=lambda x: x[1], reverse=True)]
