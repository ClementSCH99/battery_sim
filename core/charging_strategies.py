"""
Charging Strategies — comparison and recommendation tools

This module provides:
- ChargingStrategyMetrics: value object for per-strategy metrics
- ChargingStrategyBuilder: factory for creating different charging protocols
- ChargingStrategyComparison: orchestrates multi-strategy evaluation

TEACHING NOTE — Why separate from investigation_tools.py?
This module focuses on a specific domain: charging strategy comparison.
Keeping it separate improves code organization and makes it easier to extend
with new strategies (e.g., pulse charging, BMS-adaptive profiles).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import numpy as np

from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, CC_CV, ConstantCurrent, Rest, PowerStep
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.core.simulation import Simulation
from battery_sim.core.degradation import DegradationConfig
from battery_sim.core.simulation_backend import SimulationBackend


# ============================================================================
# VALUE OBJECTS
# ============================================================================

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


@dataclass
class ChargingStrategyComparison:
    """Results from comparing multiple charging strategies."""
    preset_name: str
    chemistry: str
    nominal_capacity_Ah: float
    strategies: List[ChargingStrategyMetrics]
    temperature_C: float
    n_cycles: int
    
    def rank_by_speed(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by fastest charge time."""
        return sorted(self.strategies, key=lambda s: s.charge_time_min)
    
    def rank_by_efficiency(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by energy efficiency (highest to lowest)."""
        return sorted(self.strategies, key=lambda s: s.energy_efficiency, reverse=True)
    
    def rank_by_longevity(self) -> List[ChargingStrategyMetrics]:
        """Rank strategies by best cycle life (lowest capacity fade)."""
        return sorted(self.strategies, key=lambda s: s.capacity_fade_per_cycle)
    
    def rank_balanced(self) -> List[ChargingStrategyMetrics]:
        """Rank by balanced score: speed + efficiency + longevity."""
        scores = []
        for s in self.strategies:
            # Normalize each metric 0-1
            # Speed: fast is good (invert time, normalize to max)
            charge_speeds = [x.charge_time_min for x in self.strategies]
            speed_score = 1.0 - (s.charge_time_min / max(charge_speeds)) if max(charge_speeds) > 0 else 0.5
            
            # Efficiency: high is good
            efficiency_score = s.energy_efficiency
            
            # Longevity: low fade is good (invert fade, normalize to max)
            fades = [x.capacity_fade_per_cycle for x in self.strategies]
            longevity_score = 1.0 - (s.capacity_fade_per_cycle / max(fades)) if max(fades) > 0 else 0.5
            
            # Weighted average: 40% speed, 20% efficiency, 40% longevity
            balanced_score = 0.4 * speed_score + 0.2 * efficiency_score + 0.4 * longevity_score
            scores.append((s, balanced_score))
        
        return [s for s, _ in sorted(scores, key=lambda x: x[1], reverse=True)]


# ============================================================================
# CHARGING STRATEGY BUILDER
# ============================================================================

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
            ConstantCurrent(current_A=step_1_current, _duration_s=60),    # 1 min at 2C
            ConstantCurrent(current_A=step_2_current, _duration_s=120),   # 2 min at 1.5C
            ConstantCurrent(current_A=step_3_current, _duration_s=180),   # 3 min at 1C
            ConstantCurrent(current_A=step_4_current, _duration_s=600),   # 10 min at 0.5C (to ~full)
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
            steps.append(ConstantCurrent(current_A=charge_current, _duration_s=300))  # 5 min pulse
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
        
        return {name: all_strategies[name] for name in strategy_names if name in all_strategies}


# ============================================================================
# CHARGING STRATEGY COMPARISON
# ============================================================================

class ChargingStrategyEvaluator:
    """Evaluates multiple charging strategies on the same cell."""
    
    def __init__(
        self,
        backend: SimulationBackend,
        model: Model = Model.SPM,
    ):
        """
        Initialize evaluator.
        
        Args:
            backend: Simulation backend
            model: Battery model (SPM or DFN)
        """
        self.backend = backend
        self.model = model
    
    def evaluate_strategy(
        self,
        cell: Cell,
        charge_protocol: Protocol,
        strategy_name: str,
        discharge_current_A: Optional[float] = None,
        n_cycles: int = 10,
        temperature_C: float = 25.0,
    ) -> ChargingStrategyMetrics:
        """
        Evaluate one charging strategy through n_cycles.
        
        Args:
            cell: Cell to test
            charge_protocol: Charging protocol to evaluate
            strategy_name: Name of strategy (for reporting)
            discharge_current_A: Discharge current (if None, uses nominal 1C)
            n_cycles: Number of charge-discharge cycles
            temperature_C: Ambient temperature
        
        Returns:
            ChargingStrategyMetrics with extracted performance data
        """
        nominal_capacity_Ah = ChargingStrategyBuilder._require_nominal_capacity(cell)
        if discharge_current_A is None:
            discharge_current_A = nominal_capacity_Ah  # 1C default
        
        # Build discharge protocol (simple 1C discharge to cutoff)
        discharge_protocol = Protocol(steps=[
            ConstantCurrent(current_A=discharge_current_A, _duration_s=3600),  # 1-hour max
            Rest(_duration_s=600),  # Post-discharge rest
        ])
        
        # Create cycling protocol
        cycling_protocol = Protocol.cycle(
            charge=charge_protocol,
            discharge=discharge_protocol,
            n_cycles=n_cycles,
            rest_s=600,  # 10 min rest between cycles
        )
        
        # Create environment and simulation
        environment = Environment(temperature_C=temperature_C)
        
        # Enable SEI degradation to capture aging
        degradation_config = DegradationConfig(
            sei_model="ec reaction limited",  # Enable SEI growth
        )
        
        simulation = Simulation(
            cell=cell,
            model=self.model,
            protocol=cycling_protocol,
            environment=environment,
            degradation=degradation_config,
            solver_config=SolverConfig(),
        )
        
        # Run simulation
        run = None
        status = "ok"
        failure_error = ""
        failure_note = ""
        try:
            run = simulation.run(self.backend)
            if not run.is_successful():
                status = "failed"
                run_errors = [err.summary() for err in run.errors] if run.errors else []
                failure_error = "; ".join(run_errors) if run_errors else "SimulationRun marked unsuccessful"
                failure_note = f"Simulation failed: {failure_error}"
        except Exception as e:
            status = "failed"
            failure_error = f"{type(e).__name__}: {e}"
            failure_note = f"Simulation failed: {failure_error}"
        
        # Extract metrics
        charge_time_min = 0.0
        discharge_time_min = 0.0
        charge_energy_Wh = 0.0
        discharge_energy_Wh = 0.0
        final_temperature_C = environment.temperature_C
        final_capacity_Ah = nominal_capacity_Ah
        final_soh = 100.0
        
        if run and run.result:
            result = run.result
            
            # Estimate timing from simulation time
            # This is approximate: PyBaMM doesn't directly expose per-step times
            time_vector_fn = getattr(result, "time_vector", None)
            time_vector = time_vector_fn() if callable(time_vector_fn) else []
            total_time_s = float(time_vector[-1]) if isinstance(time_vector, (list, tuple, np.ndarray)) and len(time_vector) > 0 else 0.0
            charge_time_min = (total_time_s / 2) / 60 if total_time_s > 0 else 0  # Rough estimate
            discharge_time_min = (total_time_s / 2) / 60 if total_time_s > 0 else 0
            
            # Energy from voltage/current product (approximation)
            charge_energy_fn = getattr(result, "charge_energy", None)
            if callable(charge_energy_fn):
                charge_energy_value = charge_energy_fn()
                if isinstance(charge_energy_value, (int, float, np.floating)):
                    charge_energy_Wh = float(charge_energy_value)

            discharge_energy_fn = getattr(result, "discharge_energy", None)
            if callable(discharge_energy_fn):
                discharge_energy_value = discharge_energy_fn()
                if isinstance(discharge_energy_value, (int, float, np.floating)):
                    discharge_energy_Wh = float(discharge_energy_value)
            
            # Capacity fade
            capacity_fade_fn = getattr(result, "capacity_fade", None)
            if callable(capacity_fade_fn):
                capacity_fade_value = capacity_fade_fn()
                if isinstance(capacity_fade_value, (int, float, np.floating)):
                    capacity_fade_fraction = float(capacity_fade_value)
                    final_capacity_Ah = (1.0 - capacity_fade_fraction) * nominal_capacity_Ah
                    final_soh = (1.0 - capacity_fade_fraction) * 100.0
            
            # Temperature
            max_temperature_fn = getattr(result, "max_temperature", None)
            max_temperature = max_temperature_fn() if callable(max_temperature_fn) else None
            if isinstance(max_temperature, (int, float, np.floating)):
                final_temperature_C = float(max_temperature)
        
        # Calculate metrics
        capacity_fade_per_cycle = (1.0 - (final_capacity_Ah / nominal_capacity_Ah)) * 100.0 / max(n_cycles, 1)
        energy_efficiency = discharge_energy_Wh / charge_energy_Wh if charge_energy_Wh > 0 else 0
        total_cycle_time_min = charge_time_min + discharge_time_min
        
        return ChargingStrategyMetrics(
            strategy_name=strategy_name,
            charge_time_min=charge_time_min,
            discharge_time_min=discharge_time_min,
            total_cycle_time_min=total_cycle_time_min,
            charge_energy_Wh=charge_energy_Wh,
            discharge_energy_Wh=discharge_energy_Wh,
            energy_efficiency=energy_efficiency,
            capacity_fade_per_cycle=capacity_fade_per_cycle,
            final_capacity_Ah=final_capacity_Ah,
            final_soh=final_soh,
            final_temperature_C=final_temperature_C,
            cycle_count=n_cycles,
            status=status,
            error=failure_error,
            notes=failure_note,
        )
    
    def compare(
        self,
        cell: Cell,
        strategies: Optional[List[str]] = None,
        n_cycles: int = 10,
        temperature_C: float = 25.0,
    ) -> ChargingStrategyComparison:
        """
        Compare multiple charging strategies on the same cell.
        
        Args:
            cell: Cell to test
            strategies: List of strategy names (None = all built-in)
            n_cycles: Number of cycles per strategy
            temperature_C: Ambient temperature
        
        Returns:
            ChargingStrategyComparison with all results and rankings
        """
        # Build protocols
        protocols = ChargingStrategyBuilder.build(cell, strategies)
        
        # Evaluate each strategy
        results = []
        for strategy_name, protocol in protocols.items():
            metrics = self.evaluate_strategy(
                cell,
                protocol,
                strategy_name,
                n_cycles=n_cycles,
                temperature_C=temperature_C,
            )
            results.append(metrics)
        
        return ChargingStrategyComparison(
            preset_name=cell.chemistry,
            chemistry=cell.chemistry,
            nominal_capacity_Ah=ChargingStrategyBuilder._require_nominal_capacity(cell),
            strategies=results,
            temperature_C=temperature_C,
            n_cycles=n_cycles,
        )
