# battery_sim/core/parameter_sweep.py
"""
Parameter Sweep & Sensitivity Analysis

This module provides tools for systematic variation of cell and environment
parameters to analyze their impact on simulation results.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Any, Callable, Optional, Tuple
import json
from battery_sim.core.application_services import ParameterSweepService
from battery_sim.core.application_services import SimulationExecutionService
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.simulation_backend import SimulationBackend


@dataclass(frozen=True)
class ParameterOverride:
    """
    Tracks which parameters were overridden in a simulation.
    
    Enables reproducibility and understanding of parameter changes.
    """
    cell_parameters: Dict[str, Any] = field(default_factory=dict)
    environment_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "cell_parameters": self.cell_parameters,
            "environment_parameters": self.environment_parameters,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ParameterOverride":
        """Create from dictionary."""
        return ParameterOverride(
            cell_parameters=data.get("cell_parameters", {}),
            environment_parameters=data.get("environment_parameters", {})
        )

    def summary(self) -> str:
        """Get human-readable summary of changes."""
        lines = []
        if self.cell_parameters:
            lines.append("Cell parameters:")
            for key, value in self.cell_parameters.items():
                lines.append(f"  {key}: {value}")
        if self.environment_parameters:
            lines.append("Environment parameters:")
            for key, value in self.environment_parameters.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines) if lines else "(No overrides)"


@dataclass
class SweepResult:
    """Result of a parameter sweep simulation run."""
    parameter_name: str
    parameter_value: Any
    simulation_result: SimulationRun
    override: ParameterOverride


class ParameterSweep:
    """
    Execute sensitivity analysis by varying one or more parameters.
    
    Supports both single-parameter sweeps and multi-dimensional sweeps.
    """

    def __init__(self, backend: SimulationBackend) -> None:
        self._execution_service = SimulationExecutionService(backend)
        self._sweep_service = ParameterSweepService(self._execution_service)

    def sweep_cell_parameter(
        self,
        baseline_simulation: Simulation,
        parameter_name: str,
        values: List[Any],
        verbose: bool = False,
    ) -> List[SweepResult]:
        """
        Sweep a single cell parameter across multiple values.
        
        Args:
            baseline_simulation: Template simulation to modify
            parameter_name: Name of cell parameter to vary (e.g., 'nominal_capacity_Ah')
            values: List of values to test
            verbose: Print progress information
            
        Returns:
            List of SweepResult objects with SimulationRun outputs and overrides
            
        Example:
            >>> sim = Simulation(...)
            >>> results = ParameterSweep.sweep_cell_parameter(
            ...     sim, 
            ...     'nominal_capacity_Ah',
            ...     [4.0, 5.0, 6.0]
            ... )
            >>> for r in results:
            ...     print(f"{r.parameter_value} Ah: {r.simulation_result.peak_power()} W")
        """
        raw_results = self._sweep_service.sweep_parameter(
            baseline_simulation,
            "cell",
            parameter_name,
            values,
        )
        sweep_results = []

        for i, (value, result, cell_overrides, env_overrides) in enumerate(raw_results):
            if verbose:
                print(f"  [{i+1}/{len(values)}] {parameter_name} = {value}... Done")

            sweep_results.append(
                SweepResult(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    simulation_result=result,
                    override=ParameterOverride(
                        cell_parameters=cell_overrides,
                        environment_parameters=env_overrides,
                    ),
                )
            )

        return sweep_results

    def sweep_environment_parameter(
        self,
        baseline_simulation: Simulation,
        parameter_name: str,
        values: List[Any],
        verbose: bool = False,
    ) -> List[SweepResult]:
        """
        Sweep a single environment parameter across multiple values.
        
        Args:
            baseline_simulation: Template simulation to modify
            parameter_name: Name of environment parameter to vary (e.g., 'temperature_C')
            values: List of values to test
            verbose: Print progress information
            
        Returns:
            List of SweepResult objects
            
        Example:
            >>> sweep_results = ParameterSweep.sweep_environment_parameter(
            ...     sim,
            ...     'temperature_C',
            ...     [0, 25, 40, 60]
            ... )
        """
        raw_results = self._sweep_service.sweep_parameter(
            baseline_simulation,
            "environment",
            parameter_name,
            values,
        )
        sweep_results = []

        for i, (value, result, cell_overrides, env_overrides) in enumerate(raw_results):
            if verbose:
                print(f"  [{i+1}/{len(values)}] {parameter_name} = {value}... Done")

            sweep_results.append(
                SweepResult(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    simulation_result=result,
                    override=ParameterOverride(
                        cell_parameters=cell_overrides,
                        environment_parameters=env_overrides,
                    ),
                )
            )

        return sweep_results

    def multi_parameter_sweep(
        self,
        baseline_simulation: Simulation,
        parameters: Dict[str, List[Any]],
        verbose: bool = False,
    ) -> List[Tuple[Dict[str, Any], SimulationRun, ParameterOverride]]:
        """
        Execute multi-dimensional parameter sweep.
        
        Args:
            baseline_simulation: Template simulation
            parameters: Dict mapping parameter names to lists of values.
                       Format: {
                           'cell::nominal_capacity_Ah': [4.0, 5.0, 6.0],
                           'environment::temperature_C': [25, 40],
                       }
                       Prefix 'cell::' or 'environment::' indicates which object
            verbose: Print progress
            
        Returns:
            List of tuples: (parameter_dict, simulation_run, override)
            
        Example:
            >>> params = {
            ...     'cell::nominal_capacity_Ah': [4.0, 5.0, 6.0],
            ...     'environment::temperature_C': [25, 40],
            ... }
            >>> results = ParameterSweep.multi_parameter_sweep(sim, params, verbose=True)
            >>> # 3 × 2 = 6 simulations total
        """
        raw_results = self._sweep_service.multi_parameter_sweep(
            baseline_simulation,
            parameters,
        )
        results = []

        for index, (parameter_dict, result, cell_overrides, env_overrides) in enumerate(raw_results, start=1):
            if verbose:
                print(f"  [{index}/{len(raw_results)}] ", end="", flush=True)
                for key, value in parameter_dict.items():
                    print(f"{key}={value} ", end="", flush=True)
                print("... Done")

            results.append(
                (
                    parameter_dict,
                    result,
                    ParameterOverride(
                        cell_parameters=cell_overrides,
                        environment_parameters=env_overrides,
                    ),
                )
            )

        return results

    @staticmethod
    def analyze_sensitivity(
        sweep_results: List[SweepResult],
        metric_func: Callable[[SimulationRun], float],
        metric_name: str = "Metric",
    ) -> Dict[str, Any]:
        """
        Analyze sensitivity to a parameter based on metrics.
        
        Args:
            sweep_results: List of SweepResult from a sweep
            metric_func: Function that extracts a metric from SimulationRun
            metric_name: Human-readable metric name
            
        Returns:
            Dictionary with sensitivity analysis:
            {
                'metric_name': 'Metric',
                'parameter_name': 'capacity',
                'parameter_values': [4.0, 5.0, 6.0],
                'metric_values': [17.5, 21.2, 25.0],
                'min': 17.5,
                'max': 25.0,
                'range': 7.5,
                'sensitivity': 0.75,  # range / baseline_value
            }
        """
        param_name = sweep_results[0].parameter_name
        param_values = []
        metric_values = []
        
        for sr in sweep_results:
            try:
                metric_value = metric_func(sr.simulation_result)
                if metric_value is not None:
                    param_values.append(sr.parameter_value)
                    metric_values.append(metric_value)
            except Exception:
                # Skip results that fail metric calculation
                continue
        
        if not metric_values:
            return {
                'metric_name': metric_name,
                'parameter_name': param_name,
                'error': 'No valid metric values computed'
            }
        
        min_val = min(metric_values)
        max_val = max(metric_values)
        range_val = max_val - min_val
        baseline = metric_values[0] if metric_values else 1.0
        
        return {
            'metric_name': metric_name,
            'parameter_name': param_name,
            'parameter_values': param_values,
            'metric_values': metric_values,
            'min': min_val,
            'max': max_val,
            'range': range_val,
            'sensitivity': range_val / baseline if baseline != 0 else 0,
            'baseline_value': baseline,
        }
