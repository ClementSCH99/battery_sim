# battery_sim/core/parameter_sweep.py
"""
Parameter Sweep & Sensitivity Analysis

This module provides tools for systematic variation of cell and environment
parameters to analyze their impact on simulation results.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Any, Callable, Optional, Tuple
import json
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.core.result import Result


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
    """Result of a parameter sweep simulation."""
    parameter_name: str
    parameter_value: Any
    simulation_result: Result
    override: ParameterOverride


class ParameterSweep:
    """
    Execute sensitivity analysis by varying one or more parameters.
    
    Supports both single-parameter sweeps and multi-dimensional sweeps.
    """

    @staticmethod
    def sweep_cell_parameter(
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
            List of SweepResult objects with simulations and outcomes
            
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
        sweep_results = []
        
        for i, value in enumerate(values):
            if verbose:
                print(f"  [{i+1}/{len(values)}] {parameter_name} = {value}...", end=" ", flush=True)
            
            # Create modified cell
            modified_cell = replace(baseline_simulation.cell, **{parameter_name: value})
            
            # Create modified simulation
            modified_sim = replace(baseline_simulation, cell=modified_cell)
            
            # Run simulation
            result = modified_sim.run()
            
            # Track override
            override = ParameterOverride(
                cell_parameters={parameter_name: value}
            )
            
            sweep_results.append(
                SweepResult(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    simulation_result=result,
                    override=override
                )
            )
            
            if verbose:
                print("✓")
        
        return sweep_results

    @staticmethod
    def sweep_environment_parameter(
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
        sweep_results = []
        
        for i, value in enumerate(values):
            if verbose:
                print(f"  [{i+1}/{len(values)}] {parameter_name} = {value}...", end=" ", flush=True)
            
            # Create modified environment
            modified_env = replace(baseline_simulation.environment, **{parameter_name: value})
            
            # Create modified simulation
            modified_sim = replace(baseline_simulation, environment=modified_env)
            
            # Run simulation
            result = modified_sim.run()
            
            # Track override
            override = ParameterOverride(
                environment_parameters={parameter_name: value}
            )
            
            sweep_results.append(
                SweepResult(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    simulation_result=result,
                    override=override
                )
            )
            
            if verbose:
                print("✓")
        
        return sweep_results

    @staticmethod
    def multi_parameter_sweep(
        baseline_simulation: Simulation,
        parameters: Dict[str, List[Any]],
        verbose: bool = False,
    ) -> List[Tuple[Dict[str, Any], Result, ParameterOverride]]:
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
            List of tuples: (parameter_dict, result, override)
            
        Example:
            >>> params = {
            ...     'cell::nominal_capacity_Ah': [4.0, 5.0, 6.0],
            ...     'environment::temperature_C': [25, 40],
            ... }
            >>> results = ParameterSweep.multi_parameter_sweep(sim, params, verbose=True)
            >>> # 3 × 2 = 6 simulations total
        """
        # Parse parameters into cell and environment dicts
        cell_params = {}
        env_params = {}
        param_names = list(parameters.keys())
        
        for param_name in param_names:
            if param_name.startswith('cell::'):
                clean_name = param_name[6:]
                cell_params[clean_name] = parameters[param_name]
            elif param_name.startswith('environment::'):
                clean_name = param_name[13:]
                env_params[clean_name] = parameters[param_name]
            else:
                raise ValueError(
                    f"Parameter {param_name} must start with 'cell::' or 'environment::'"
                )
        
        # Generate all combinations
        results = []
        
        def generate_combinations(param_dict: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
            """Generate all combinations of parameter values."""
            if not param_dict:
                return [{}]
            
            items = list(param_dict.items())
            first_name, first_values = items[0]
            rest = {k: v for k, v in items[1:]}
            rest_combos = generate_combinations(rest)
            
            combos = []
            for value in first_values:
                for combo in rest_combos:
                    new_combo = {first_name: value, **combo}
                    combos.append(new_combo)
            return combos
        
        cell_combos = generate_combinations(cell_params)
        env_combos = generate_combinations(env_params)
        
        total = len(cell_combos) * len(env_combos)
        count = 0
        
        for cell_combo in cell_combos:
            for env_combo in env_combos:
                count += 1
                if verbose:
                    print(f"  [{count}/{total}] ", end="", flush=True)
                    for k, v in {**cell_combo, **env_combo}.items():
                        print(f"{k}={v} ", end="", flush=True)
                    print("...", end=" ", flush=True)
                
                # Build modified simulation
                modified_cell = (
                    replace(baseline_simulation.cell, **cell_combo)
                    if cell_combo else baseline_simulation.cell
                )
                modified_env = (
                    replace(baseline_simulation.environment, **env_combo)
                    if env_combo else baseline_simulation.environment
                )
                modified_sim = replace(
                    baseline_simulation,
                    cell=modified_cell,
                    environment=modified_env
                )
                
                # Run simulation
                result = modified_sim.run()
                
                # Track overrides
                override = ParameterOverride(
                    cell_parameters=cell_combo,
                    environment_parameters=env_combo
                )
                
                results.append(
                    ({**cell_combo, **env_combo}, result, override)
                )
                
                if verbose:
                    print("✓")
        
        return results

    @staticmethod
    def analyze_sensitivity(
        sweep_results: List[SweepResult],
        metric_func: Callable[[Result], float],
        metric_name: str = "Metric",
    ) -> Dict[str, Any]:
        """
        Analyze sensitivity to a parameter based on metrics.
        
        Args:
            sweep_results: List of SweepResult from a sweep
            metric_func: Function that extracts a metric from Result
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
