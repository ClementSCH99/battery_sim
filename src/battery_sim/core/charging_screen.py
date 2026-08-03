"""Legacy-compatible single-charge CC-CV current screening."""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import CC_CV, Protocol
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig


@dataclass(frozen=True)
class ChargingOptimizationResult:
    """
    Result from optimizing charge parameters.
    
    TEACHING: This value object represents one candidate charging profile.
    The optimizer returns a list of these, sorted by score.
    """
    charge_current_A: float
    """Current (A) during constant-current phase"""
    
    charge_time_s: Optional[float]
    """Time (seconds) to fully charge at this current"""
    
    capacity_fade_per_cycle: Optional[float]
    """Unavailable in the single-charge screen; retained for compatibility"""
    
    score: float
    """Normalized charge-duration score; lower is faster"""
    
    peak_voltage_V: Optional[float]
    """Peak voltage reached during charge"""
    
    final_efficiency: Optional[float]
    """Charging efficiency (%) for this protocol"""


class ChargingOptimizer:
    """
    Legacy low-level single-charge CC-CV duration screen.

    The public agent tool now lives in ``interface.charging_tools``. This class
    remains import-compatible, but it no longer fabricates an empirical aging
    value or claims to optimize longevity.
    """
    
    def __init__(
        self,
        backend: SimulationBackend,
        model: Model = Model.SPM,
    ):
        """
        Initialize the optimizer.
        
        Args:
            backend: Simulation backend
            model: Battery model to use (SPM or DFN)
        """
        self.backend = backend
        self.model = model
    
    def optimize(
        self,
        cell: Cell,
        charge_current_range_A: tuple[float, float] = (1.0, 10.0),
        n_points: int = 5,
        max_voltage_V: float = 4.2,
        num_cycles: int = 5,
        temperature_C: float = 25.0,
    ) -> List[ChargingOptimizationResult]:
        """
        Screen a grid of charge currents by single-charge duration.
        
        Args:
            cell: Battery cell to analyze
            charge_current_range_A: (min, max) charge current in Amperes
            n_points: Number of test points in the current range
            max_voltage_V: Upper cutoff voltage for CV phase (typically 4.2V for NMC)
            num_cycles: Retained for API compatibility; no cycling is performed
            temperature_C: Ambient temperature (default 25°C)
        
        Returns:
            List of ChargingOptimizationResult, sorted by score (best first)
        """
        
        if n_points < 1:
            raise ValueError("n_points must be >= 1")
        if charge_current_range_A[0] <= 0 or charge_current_range_A[0] > charge_current_range_A[1]:
            raise ValueError("charge_current_range_A must contain positive min <= max")

        # Create test currents
        charge_currents = np.linspace(
            charge_current_range_A[0],
            charge_current_range_A[1],
            n_points
        ).tolist()
        
        # Run simulation for each charge current
        results = []
        
        for charge_current in charge_currents:
            try:
                result = self._evaluate_charge_profile(
                    cell=cell,
                    charge_current_A=charge_current,
                    max_voltage_V=max_voltage_V,
                    num_cycles=num_cycles,
                    temperature_C=temperature_C,
                )
                results.append(result)
            except Exception as e:
                # If a single scenario fails, log and continue
                print(f"Warning: Charging optimization failed at {charge_current}A: {e}")
                continue
        
        if not results:
            return []
        
        # Sort by score (best first)
        results.sort(key=lambda r: r.score)
        
        return results
    
    def _evaluate_charge_profile(
        self,
        cell: Cell,
        charge_current_A: float,
        max_voltage_V: float,
        num_cycles: int,
        temperature_C: float,
    ) -> ChargingOptimizationResult:
        """
        Evaluate one charge current profile.
        
        Build one CC-CV charge from 20% SOC and extract observed duration.
        
        Args:
            cell: Battery cell
            charge_current_A: Charge current for CC phase (A)
            max_voltage_V: Cutoff voltage for CV phase (V)
            num_cycles: Retained for compatibility; ignored
            temperature_C: Temperature (°C)
        
        Returns:
            ChargingOptimizationResult with metrics
        """
        
        # Build CC-CV charge protocol
        # Taper current is typically 20% of CC current
        taper_current_A = max(0.1, charge_current_A * 0.2)
        
        charge_step = CC_CV(
            charge_current_A=charge_current_A,
            cutoff_voltage_V=max_voltage_V,
            taper_current_A=taper_current_A,
        )
        
        protocol = Protocol(steps=[charge_step])
        
        # Create environment
        environment = Environment(temperature_C=temperature_C)
        
        # Create solver config
        solver_config = SolverConfig(initial_soc=0.2)
        
        # Create simulation
        simulation = Simulation(
            cell=cell,
            model=self.model,
            protocol=protocol,
            environment=environment,
            solver_config=solver_config,
        )
        
        # Run simulation
        run = simulation.run(self.backend)
        
        # Extract metrics
        charge_time_s = None
        peak_voltage_V = None
        final_efficiency = None
        capacity_fade_per_cycle = None
        
        if run.result:
            result = run.result
            
            voltage = result.voltage()
            if voltage is not None and voltage.time_s:
                charge_time_s = float(voltage.time_s[-1])
            
            # Peak voltage
            peak_voltage_V = result.max_voltage()
            

        # One hour is the score reference. This ranks duration only.
        score = min(2.5, max(0.0, charge_time_s / 3600.0)) if charge_time_s else 2.5
        
        return ChargingOptimizationResult(
            charge_current_A=charge_current_A,
            charge_time_s=charge_time_s,
            capacity_fade_per_cycle=capacity_fade_per_cycle,
            score=score,
            peak_voltage_V=peak_voltage_V,
            final_efficiency=final_efficiency,
        )


