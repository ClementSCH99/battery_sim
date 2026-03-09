"""
LAYER 2: INVESTIGATION TOOLS - Core Operations for LLM Reasoning

TEACHING FOCUS: How to build investigative operations

WHY THIS LAYER EXISTS:
Layer 1 (API Schema) answered: "What CAN I do?"
Layer 2 answers: "HOW do I do it?"

An LLM needs operations that let it:
1. Compare presets (which chemistry is best?)
2. Analyze sensitivity (does this parameter matter?)
3. Check constraints (is this scenario feasible?)
4. Explore systematically (find good parameters)
5. Run batches (test multiple hypotheses)

DESIGN PRINCIPLE: These are INVESTIGATION PRIMITIVES.
They're not optimizers (we're not "solving" for best parameters).
They're not simulators (that's B9-B11's job).
They're EXPLORATION tools that let the LLM learn through experimentation.

KEY INSIGHT: The best insights come from trying multiple things and
comparing results. These tools make that process systematic and reportable.

---

EXAMPLE: How investigation tools guide reasoning

SCENARIO: "I need a cell for high power. What's the best chemistry?"

WITHOUT TOOLS:
  LLM: "You should use NCA"
  Engineer: "Why?"
  LLM: "Because it has high energy density"
  Engineer: "But I need power, not energy!"
  (Reasoning is unsupported)

WITH TOOLS:
  LLM: "Let me explore" [uses compare_presets]
  LLM: "NCA has 25W peak power, NMC has 18W, LFP has 12W"
  LLM: "NCA is 40% more powerful"
  LLM: "But temperature analysis shows [uses sensitivity_analysis]"
  LLM: "NCA loses 8% efficiency at 40°C, NMC only 3%"
  LLM: "For your typical 35°C operating point, NMC is actually better"
  (Reasoning is grounded in data)
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Any, Optional, Tuple, Callable

from battery_sim.core.simulation import Simulation
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend


# ============================================================================
# BATCH SIMULATOR: Run multiple simulations efficiently
# ============================================================================

@dataclass
class BatchSimulationConfig:
    """
    Configuration for running multiple simulations.
    
    TEACHING: When you want to run 10 different scenarios, you don't set up
    each one manually. You describe what you want, and the tool sets them up.
    
    This is about automating the "boring" setup so you can focus on analysis.
    """
    protocol: Protocol
    environment: Environment = field(default_factory=lambda: Environment(temperature_C=25.0))
    model: Model = Model.SPM
    solver_config: SolverConfig = field(default_factory=SolverConfig)
    backend: PyBaMMBackend = field(default_factory=PyBaMMBackend)


class BatchSimulator:
    """
    Run multiple simulations with different parameters in batch.
    
    TEACHING: Batch processing is faster than sequential, and you can
    compare results systematically. The LLM might say:
    "Run NMC, NCA, and LFP each at 25°C and 40°C"
    
    BatchSimulator translates that into 6 simulations and runs them.
    """
    
    @staticmethod
    def run_presets(
        preset_names: List[str],
        config: BatchSimulationConfig,
    ) -> List[Tuple[str, Any]]:  # (preset_name, SimulationRun)
        """
        Run simulations for multiple cell presets.
        
        TEACHING: This is a specialized batch operation. "Run these presets
        with the same environment and protocol."
        
        Args:
            preset_names: List of preset names (e.g., ['LFP_5AH', 'NMC_5AH'])
            config: Simulation configuration (protocol, environment, solver)
        
        Returns:
            List of (preset_name, simulation_run) tuples
        """
        results = []
        
        for preset_name in preset_names:
            # Create cell from preset
            cell = Cell.preset(preset_name)
            
            # Create simulation
            sim = Simulation(
                cell=cell,
                model=config.model,
                protocol=config.protocol,
                environment=config.environment,
                backend=config.backend,
                solver_config=config.solver_config,
            )
            
            # Run and store
            try:
                run = sim.run()
                results.append((preset_name, run))
            except Exception as e:
                # TEACHING: Handle failures gracefully
                # Log the error but continue with other presets
                print(f"Warning: Failed to simulate {preset_name}: {str(e)}")
                results.append((preset_name, None))
        
        return results
    
    @staticmethod
    def run_parameter_variations(
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: List[Any],
        config: BatchSimulationConfig,
    ) -> List[Tuple[Any, Any]]:  # (parameter_value, SimulationRun)
        """
        Run simulations with one parameter varying.
        
        TEACHING: "I want to see what happens as I change temperature from 0 to 50"
        
        Args:
            baseline_cell: Starting cell to modify
            parameter_name: Parameter to vary (e.g., 'nominal_capacity_Ah')
            parameter_values: Values to test
            config: Simulation configuration
        
        Returns:
            List of (parameter_value, simulation_run) tuples
        """
        results = []
        
        for value in parameter_values:
            # Determine if this is a cell or environment parameter
            cell_params = ['nominal_capacity_Ah', 'nominal_voltage_V', 'internal_resistance_Ohm', 'chemistry']
            env_params = ['temperature_C']
            
            modified_cell = baseline_cell
            modified_env = config.environment
            
            # If it's a cell parameter, modify the cell
            if parameter_name in cell_params:
                modified_cell = replace(baseline_cell, **{parameter_name: value})
            
            # If it's an environment parameter, modify the environment
            elif parameter_name in env_params:
                modified_env = replace(config.environment, **{parameter_name: value})
            
            # Create and run simulation
            sim = Simulation(
                cell=modified_cell,
                model=config.model,
                protocol=config.protocol,
                environment=modified_env,
                backend=config.backend,
                solver_config=config.solver_config,
            )
            
            try:
                run = sim.run()
                results.append((value, run))
            except Exception as e:
                print(f"Warning: Failed for {parameter_name}={value}: {str(e)}")
                results.append((value, None))
        
        return results


# ============================================================================
# SIMULATION COMPARISON: Side-by-side analysis
# ============================================================================

@dataclass(frozen=True)
class ComparisonMetric:
    """
    One metric extracted from simulation results.
    
    TEACHING: When comparing two batteries, you extract specific numbers
    (efficiency, power, etc) and put them side by side.
    """
    name: str                      # e.g., 'peak_power_W'
    value: Optional[float]         # Extracted value
    unit: str                      # e.g., 'W'
    
    def relative_to_baseline(self, baseline_value: float) -> Optional[float]:
        """Calculate relative difference from baseline (useful for comparison)."""
        if baseline_value == 0 or self.value is None:
            return None
        return (self.value - baseline_value) / baseline_value * 100  # As percentage


class SimulationComparison:
    """
    Compare two or more simulations side-by-side.
    
    TEACHING: This is how humans make decisions. "NMC vs NCA: which is better?"
    You run both and compare. This tool automates the comparison.
    
    QUESTION TO ASK: "What does 'better' mean?"
    Different applications prioritize different metrics:
    - High-power tool: maximize peak_power_W
    - Long-range EV: maximize energy_Wh
    - Safe application: minimize temperature_impact
    
    The comparison tool extracts all metrics, and the LLM decides what matters.
    """
    
    @staticmethod
    def extract_metrics(
        simulation_run: Any,  # SimulationRun from B11
    ) -> Dict[str, float]:
        """
        TEACHING: Extract all key metrics from a simulation result.
        
        This is like a "profile" of the battery. You can compare profiles.
        
        Args:
            simulation_run: Result from simulation.run()
        
        Returns:
            Dict mapping metric names to values
        """
        if not simulation_run:
            return {}
        
        result = simulation_run.result  # Get underlying Result from SimulationRun
        
        # Extract all available metrics
        metrics = {}
        
        # Basic signals
        try:
            metrics['peak_voltage_V'] = result.peak_voltage()
        except:
            metrics['peak_voltage_V'] = None
        
        try:
            metrics['peak_current_A'] = result.peak_current()
        except:
            metrics['peak_current_A'] = None
        
        try:
            metrics['peak_power_W'] = result.peak_power()
        except:
            metrics['peak_power_W'] = None
        
        try:
            metrics['total_energy_Wh'] = result.total_energy_Wh()
        except:
            metrics['total_energy_Wh'] = None
        
        try:
            metrics['efficiency_percent'] = result.efficiency()
        except:
            metrics['efficiency_percent'] = None
        
        # Metadata quality metrics
        if simulation_run.metadata:
            metrics['solver_time_s'] = simulation_run.metadata.duration_s
            metrics['success'] = simulation_run.metadata.success
        
        # Diagnostics
        if simulation_run.diagnostics:
            metrics['stiffness'] = (
                'stiff' if simulation_run.diagnostics.is_stiff() else 'well-behaved'
            )
            metrics['avg_iterations'] = simulation_run.diagnostics.avg_newton_iterations
        
        # Errors (count)
        if simulation_run.errors:
            critical = len([e for e in simulation_run.errors if e.severity == 'critical'])
            warnings = len([e for e in simulation_run.errors if e.severity == 'warning'])
            metrics['critical_errors'] = critical
            metrics['warnings'] = warnings
        else:
            metrics['critical_errors'] = 0
            metrics['warnings'] = 0
        
        return metrics
    
    @staticmethod
    def compare_batch_results(
        results: List[Tuple[str, Any]],  # (name/label, SimulationRun)
        metric_filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compare multiple simulations.
        
        TEACHING: Given a batch of results, extract all metrics and compute
        relative differences.
        
        Args:
            results: List of (label, simulation_run) tuples
            metric_filters: Only compare these metrics (None = all)
        
        Returns:
            Dict with comparison data (metrics, relative diffs, rankings)
        """
        
        # Extract metrics from all results
        all_metrics = {}
        for label, run in results:
            metrics = SimulationComparison.extract_metrics(run)
            all_metrics[label] = metrics
        
        # Identify common metrics
        common_metrics = set()
        for metrics in all_metrics.values():
            common_metrics.update(metrics.keys())
        
        if metric_filters:
            common_metrics = common_metrics.intersection(set(metric_filters))
        
        # Build comparison
        comparison = {
            'scenarios': list(all_metrics.keys()),
            'metrics': {}
        }
        
        # For each metric, gather values and compute statistics
        for metric_name in sorted(common_metrics):
            values = {}
            numbers = []
            
            for label, metrics in all_metrics.items():
                value = metrics.get(metric_name)
                values[label] = value
                
                # Track numeric values for stats
                if isinstance(value, (int, float)) and value is not None:
                    numbers.append((label, value))
            
            # Store metric data
            metric_data = {
                'values': values,
                'type': 'numeric' if numbers else 'categorical',
            }
            
            # Compute stats for numeric metrics
            if numbers:
                numeric_values = [v for _, v in numbers]
                metric_data['min'] = min(numeric_values)
                metric_data['max'] = max(numeric_values)
                metric_data['range'] = metric_data['max'] - metric_data['min']
                
                # Relative to first
                if len(numeric_values) > 0:
                    baseline = numeric_values[0]
                    if baseline != 0:
                        metric_data['relative_to_first'] = {
                            label: ((value - baseline) / baseline * 100)
                            for label, value in numbers
                        }
            
            comparison['metrics'][metric_name] = metric_data
        
        return comparison


# ============================================================================
# SENSITIVITY ANALYZER: Quantify parameter impacts
# ============================================================================

@dataclass(frozen=True)
class SensitivityResult:
    """
    Results from sensitivity analysis on one parameter.
    
    TEACHING: Sensitivity tells you "how much does X matter?"
    A high sensitivity means small changes in X cause big changes in output.
    A low sensitivity means X doesn't matter much.
    
    EXAMPLE: Temperature sensitivity
    - If efficiency changes 50% as T goes 0→50°C: HIGH sensitivity
    - If efficiency changes 2% as T goes 0→50°C: LOW sensitivity
    """
    parameter_name: str
    parameter_values: List[float]
    metric_name: str
    metric_values: List[Optional[float]]
    
    # Statistics
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    range_value: Optional[float] = None
    sensitivity_coefficient: Optional[float] = None  # (max-min)/baseline * 100
    
    def interpretation(self) -> str:
        """
        Human-readable interpretation of sensitivity.
        
        TEACHING: This is how we help the LLM understand the result.
        """
        if self.sensitivity_coefficient is None:
            return "Could not compute sensitivity (insufficient data)"
        
        if self.sensitivity_coefficient < 1:
            return "VERY LOW sensitivity - parameter barely affects result"
        elif self.sensitivity_coefficient < 5:
            return "LOW sensitivity - small impact"
        elif self.sensitivity_coefficient < 20:
            return "MODERATE sensitivity - meaningful impact"
        elif self.sensitivity_coefficient < 50:
            return "HIGH sensitivity - significant impact"
        else:
            return "VERY HIGH sensitivity - dramatic impact"


class SensitivityAnalyzer:
    """
    Analyze how much a parameter affects results.
    
    TEACHING: This is crucial for reasoning about BMS calibration.
    "Which parameters should I tune first?"
    "Which parameters barely matter?"
    
    You answer by analyzing sensitivity.
    """
    
    @staticmethod
    def analyze_single_parameter(
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: List[float],
        config: BatchSimulationConfig,
        metric_extractor: Callable[[Any], float],
    ) -> SensitivityResult:
        """
        Analyze how one parameter affects a metric.
        
        TEACHING: This is systematic exploration.
        1. Vary the parameter over a range
        2. Extract the metric you care about  
        3. Compute sensitivity
        
        Args:
            baseline_cell: Starting point
            parameter_name: Parameter to vary
            parameter_values: Values to test
            config: Simulation config
            metric_extractor: Function to extract the metric of interest
        
        Returns:
            SensitivityResult with statistics
        """
        
        # Run batch with parameter variations
        results = BatchSimulator.run_parameter_variations(
            baseline_cell,
            parameter_name,
            parameter_values,
            config,
        )
        
        # Extract metric values
        metric_values = []
        valid_values = []
        
        for param_value, run in results:
            if run:
                try:
                    metric = metric_extractor(run)
                    metric_values.append(metric)
                    if metric is not None:
                        valid_values.append(metric)
                except:
                    metric_values.append(None)
            else:
                metric_values.append(None)
        
        # Compute sensitivity
        sensitivity_coeff = None
        min_val = None
        max_val = None
        range_val = None
        
        if valid_values and len(valid_values) > 0:
            min_val = min(valid_values)
            max_val = max(valid_values)
            range_val = max_val - min_val
            
            # Sensitivity coefficient
            if valid_values[0] != 0:
                sensitivity_coeff = (range_val / abs(valid_values[0])) * 100
        
        return SensitivityResult(
            parameter_name=parameter_name,
            parameter_values=parameter_values,
            metric_name=metric_extractor.__name__,
            metric_values=metric_values,
            min_value=min_val,
            max_value=max_val,
            range_value=range_val,
            sensitivity_coefficient=sensitivity_coeff,
        )


# ============================================================================
# CONSTRAINT CHECKER: Is this scenario feasible?
# ============================================================================

@dataclass(frozen=True)
class ConstraintViolation:
    """
    Description of a constraint that's violated.
    
    TEACHING: Not all scenarios are feasible. A constraint checker answers:
    "Can I actually build a battery with these specs?"
    "Will this charge profile work?"
    """
    constraint_name: str
    violated: bool
    message: str
    severity: str  # 'critical' or 'warning'


class ConstraintChecker:
    """
    Check if a scenario satisfies physical constraints.
    
    TEACHING: This is like a feasibility check.
    
    Example constraints:
    - Cell voltage must stay in [2.5V, 4.2V]
    - Current must be positive/negative depending on charge/discharge
    - Temperature must not exceed thermal limits
    - Capacity must be positive
    - etc.
    """
    
    @staticmethod
    def check_cell_feasibility(cell: Cell) -> List[ConstraintViolation]:
        """
        Check if cell parameters are physically reasonable.
        
        TEACHING: These are soft constraints. The LLM can override if needed.
        """
        violations = []
        
        # Capacity positive
        if cell.nominal_capacity_Ah is not None and cell.nominal_capacity_Ah <= 0:
            violations.append(ConstraintViolation(
                constraint_name='capacity_positive',
                violated=True,
                message=f'Capacity must be positive, got {cell.nominal_capacity_Ah}',
                severity='warning',
            ))
        
        # Voltage reasonable for lithium
        if cell.nominal_voltage_V is not None and (cell.nominal_voltage_V < 2.0 or cell.nominal_voltage_V > 5.0):
            violations.append(ConstraintViolation(
                constraint_name='voltage_in_range',
                violated=True,
                message=f'Typical lithium cell voltage is 2.0-5.0V, got {cell.nominal_voltage_V}V',
                severity='warning',
            ))
        
        # Resistance physical
        if cell.internal_resistance_Ohm is not None and cell.internal_resistance_Ohm < 0:
            violations.append(ConstraintViolation(
                constraint_name='resistance_non_negative',
                violated=True,
                message=f'Resistance cannot be negative, got {cell.internal_resistance_Ohm} Ohm',
                severity='warning',
            ))
        
        return violations
    
    @staticmethod
    def check_protocol_feasibility(
        cell: Cell,
        environment: Environment,
    ) -> List[ConstraintViolation]:
        """
        Check if protocol can be executed with this cell.
        
        TEACHING: Give hints but don't be too restrictive. LLM may have 
        other resources to validate scenarios.
        """
        violations = []
        
        # Temperature operating hints
        if environment.temperature_C < -20 or environment.temperature_C > 70:
            violations.append(ConstraintViolation(
                constraint_name='temperature_extreme',
                violated=False,
                message=f'Temperature {environment.temperature_C}°C is unusual (typical -20 to 70°C)',
                severity='warning',
            ))
        
        return violations
    
    @staticmethod
    def get_feasibility_report(cell: Cell, environment: Environment) -> str:
        """
        Comprehensive feasibility report.
        
        TEACHING: User-friendly output for the engineer.
        """
        cell_violations = ConstraintChecker.check_cell_feasibility(cell)
        protocol_violations = ConstraintChecker.check_protocol_feasibility(cell, environment)
        
        all_violations = cell_violations + protocol_violations
        
        lines = ["=" * 70, "FEASIBILITY REPORT", "=" * 70, ""]
        
        if not all_violations:
            lines.append("All constraints satisfied - scenario is feasible")
        else:
            critical = [v for v in all_violations if v.severity == 'critical']
            warnings = [v for v in all_violations if v.severity == 'warning']
            
            if critical:
                lines.append(f"CRITICAL ISSUES ({len(critical)}):")
                for v in critical:
                    lines.append(f"  • {v.message}")
                lines.append("")
            
            if warnings:
                lines.append(f"WARNINGS ({len(warnings)}):")
                for v in warnings:
                    lines.append(f"  • {v.message}")
                lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# PARAMETER EXPLORER: Guided search through space
# ============================================================================

class ParameterExplorer:
    """
    Systematically explore parameter space.
    
    TEACHING: Instead of random guessing, we can search intelligently.
    The LLM might say: "I want a battery with >20W peak power and >90% efficiency"
    
    The ParameterExplorer can:
    1. Scan the space quickly (coarse grid)
    2. Identify promising regions
    3. Refine those regions (finer grid)
    
    This is guided search, not optimization.
    """
    
    @staticmethod
    def grid_search(
        cell_template: Cell,
        parameter_ranges: Dict[str, List[float]],
        config: BatchSimulationConfig,
        metric_extractor: Callable[[Any], float],
    ) -> Dict[str, Any]:
        """
        Scan parameter space on a grid.
        
        TEACHING: Try a bunch of combinations and see which looks best.
        The result is reported so the LLM can decide next steps.
        
        Args:
            cell_template: Start with this cell
            parameter_ranges: Dict like {'capacity': [3,4,5,6], 'ir': [0.01, 0.05, 0.1]}
            config: Simulation config
            metric_extractor: What metric to track?
        
        Returns:
            Dict with results and best candidates
        """
        
        # This would be a complex multi-dimensional search
        # For now, simplified version
        
        results = {
            'scenarios_tested': 0,
            'best_scenarios': [],
            'results': []
        }
        
        # In full implementation, would use itertools.product to generate
        # all combinations and test them
        
        return results
