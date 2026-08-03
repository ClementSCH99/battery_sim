"""Charging strategy evaluator."""

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
from battery_sim.experimental.charging.strategies.builder import ChargingStrategyBuilder

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
        timing_observed = False
        energy_observed = False
        capacity_fade_observed = False
        
        if run and run.result:
            result = run.result
            
            # Estimate timing from simulation time
            # This is approximate: PyBaMM doesn't directly expose per-step times
            time_vector_fn = getattr(result, "time_vector", None)
            time_vector = time_vector_fn() if callable(time_vector_fn) else []
            if not isinstance(time_vector, (list, tuple, np.ndarray)) or len(time_vector) == 0:
                for signal in result.available_signals():
                    series = result.get(signal)
                    if series.time_s:
                        time_vector = series.time_s
                        break
            total_time_s = float(time_vector[-1]) if isinstance(time_vector, (list, tuple, np.ndarray)) and len(time_vector) > 0 else 0.0
            charge_time_min = (total_time_s / 2) / 60 if total_time_s > 0 else 0  # Rough estimate
            discharge_time_min = (total_time_s / 2) / 60 if total_time_s > 0 else 0
            timing_observed = total_time_s > 0
            
            # Energy from voltage/current product (approximation)
            charge_energy_fn = getattr(result, "charge_energy", None)
            if callable(charge_energy_fn):
                charge_energy_value = charge_energy_fn()
                if isinstance(charge_energy_value, (int, float, np.floating)):
                    charge_energy_Wh = float(charge_energy_value)
                    energy_observed = True

            discharge_energy_fn = getattr(result, "discharge_energy", None)
            if callable(discharge_energy_fn):
                discharge_energy_value = discharge_energy_fn()
                if isinstance(discharge_energy_value, (int, float, np.floating)):
                    discharge_energy_Wh = float(discharge_energy_value)
                    energy_observed = True
            
            # Capacity fade
            capacity_fade_fn = getattr(result, "capacity_fade", None)
            if callable(capacity_fade_fn):
                capacity_fade_value = capacity_fade_fn()
                if isinstance(capacity_fade_value, (int, float, np.floating)):
                    capacity_fade_fraction = float(capacity_fade_value)
                    final_capacity_Ah = (1.0 - capacity_fade_fraction) * nominal_capacity_Ah
                    final_soh = (1.0 - capacity_fade_fraction) * 100.0
                    capacity_fade_observed = True
            
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
            timing_observed=timing_observed,
            energy_observed=energy_observed,
            capacity_fade_observed=capacity_fade_observed,
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
