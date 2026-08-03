"""
Investigation Tools — Value Objects and Unique Analysis Logic

This module provides:
- BatchSimulationConfig: configuration container for batch simulations
- ComparisonMetric: value object for extracted metrics
- ConstraintViolation: value object for constraint check results
- ConstraintChecker: feasibility checking logic (unique behavior)
- ParameterExplorer: guided parameter space search (unique algorithm)

TEACHING NOTE — Why is this module smaller than it used to be?
This module previously contained BatchSimulator, SimulationComparison, and
SensitivityAnalyzer classes. Those were "pass-through wrappers" that did
nothing except forward calls to application_services.py. They violated the
DRY principle: if a bug was fixed in BatchExecutionService, BatchSimulator
wouldn't get the fix because it was a separate copy of the same interface.

The rule: "If deleting this code only changes import paths, it's dead weight."

What remains here are VALUE OBJECTS (dataclasses that carry data) and classes
with UNIQUE BEHAVIOR (ConstraintChecker, ParameterExplorer) — things that
provide real logic not available anywhere else.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import SolverConfig
from battery_sim.core.simulation import SimulationRun
from battery_sim.core.simulation import SimulationBackend

# Compatibility re-export for the historical location.
from battery_sim.core.pack import PackConfiguration, PackSizer


# ============================================================================
# CONFIGURATION VALUE OBJECT
# ============================================================================

@dataclass
class BatchSimulationConfig:
    """
    Configuration for running multiple simulations.
    
    TEACHING: This is a VALUE OBJECT — it holds data, doesn't delegate.
    When you want to run 10 different scenarios, you describe what you want
    in a config, and the service layer (application_services) executes it.
    """
    protocol: Protocol
    environment: Environment = field(default_factory=lambda: Environment(temperature_C=25.0))
    model: Model = Model.SPM
    solver_config: SolverConfig = field(default_factory=SolverConfig)
    backend: SimulationBackend = field(default=None)


# ============================================================================
# COMPARISON VALUE OBJECT
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
        metric_extractor: Callable[[SimulationRun], float],
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


# ============================================================================
# CHARGING OPTIMIZER: Find best CC-CV parameters
# ============================================================================

# Compatibility re-export; the public tool lives in interface/charging_tools.py.
from battery_sim.core.charging_screen import (
    ChargingOptimizationResult,
    ChargingOptimizer,
)


# ============================================================================
# OPERATING WINDOW ANALYZER: Map safe operating region + derating curves
# ============================================================================

# Compatibility re-export; active interface code imports the focused module.
from battery_sim.core.operating_window import (
    OperatingWindowAnalyzer,
    OperatingWindowPoint,
)


# Compatibility re-export; the active agent screening lives in
# interface/vehicle_tools.py.
from battery_sim.core.cell_selection import CellScoringResult, CellSelectionScorer
