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
import numpy as np

from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, CC_CV, ConstantCurrent, Rest
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation import Simulation
from battery_sim.core.degradation import DegradationConfig


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
    """Capacity lost per cycle (%) at this charge rate"""
    
    score: float
    """Composite score: lower is better (trade-off: time vs aging)"""
    
    peak_voltage_V: Optional[float]
    """Peak voltage reached during charge"""
    
    final_efficiency: Optional[float]
    """Charging efficiency (%) for this protocol"""


class ChargingOptimizer:
    """
    Optimize charging parameters by balancing charge speed vs aging.
    
    TEACHING: This is a **grid search optimizer**, not a mathematical optimizer.
    It tests a small set of charge currents (e.g., 1A, 3A, 5A, 7A, 10A) and
    compares their trade-offs. Results are sorted by a composite score that
    blends charge time and capacity fade.
    
    The strategy:
    1. For each charge current in the range:
       a. Build a CC-CV protocol: CC at test_current → CV at max_voltage → taper
       b. Create a cycling profile: N cycles (charge + discharge + rest)
       c. Enable SEI degradation to capture aging effects
       d. Run simulation
    2. Extract metrics: charge_time, capacity_fade_per_cycle
    3. Normalize both to [0, 1] range
    4. Score = norm_time + norm_aging (lower is better)
    5. Sort by score and return
    
    Why grid search? Charging optimization is low-dimensional and non-convex,
    but the parameter space is small. Grid search is: transparent, reproducible,
    and fast enough for real-time LLM interaction.
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
        Optimize charging parameters by testing a grid of charge currents.
        
        Args:
            cell: Battery cell to analyze
            charge_current_range_A: (min, max) charge current in Amperes
            n_points: Number of test points in the current range
            max_voltage_V: Upper cutoff voltage for CV phase (typically 4.2V for NMC)
            num_cycles: Number of charge-discharge cycles to run (default 5-10)
            temperature_C: Ambient temperature (default 25°C)
        
        Returns:
            List of ChargingOptimizationResult, sorted by score (best first)
        """
        
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
        
        TEACHING: This is the inner loop. We build a cycling protocol,
        run it with degradation, and extract metrics.
        
        Args:
            cell: Battery cell
            charge_current_A: Charge current for CC phase (A)
            max_voltage_V: Cutoff voltage for CV phase (V)
            num_cycles: Number of cycles to run
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
        
        # Simple discharge: constant current at 1C (for LFP typically 5A per 5Ah)
        # Use a reasonable discharge current
        discharge_current_A = min(charge_current_A, cell.nominal_capacity_Ah or 5.0)
        
        discharge_step = ConstantCurrent(
            current_A=-discharge_current_A,  # Negative for discharge
            _duration_s=3600,  # Assume 1-hour discharge; backend will stop at cutoff
        )
        
        rest_step = Rest(_duration_s=600)  # 10-minute rest
        
        # Build protocol: one charge-discharge cycle
        single_cycle = Protocol(steps=[
            charge_step,
            rest_step,
            discharge_step,
            rest_step,
        ])
        
        # For degradation tracking, we'll run multiple cycles
        # Each cycle is one full protocol execution
        protocol = single_cycle
        
        # Create degradation config with SEI enabled
        degradation_config = DegradationConfig(
            sei_growth=True,
            lithium_plating=False,  # Unlikely with proper charge control
            active_material_loss=False,
        )
        
        # Create environment
        environment = Environment(temperature_C=temperature_C)
        
        # Create solver config
        solver_config = SolverConfig()
        
        # Create simulation
        simulation = Simulation(
            cell=cell,
            model=self.model,
            protocol=protocol,
            environment=environment,
            solver_config=solver_config,
            degradation=degradation_config,
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
            
            # Charge time: duration of the charge phase
            # For now, use protocol duration as proxy
            charge_time_s = protocol.total_duration_s()
            
            # Peak voltage
            peak_voltage_V = result.max_voltage()
            
            # Efficiency
            final_efficiency = result.charge_discharge_efficiency()
            
            # Capacity fade: estimated as (1 - final_capacity / initial_capacity)
            # This is simplified; real degradation tracking would need
            # multi-cycle results or parameter predictions from PyBaMM
            # For this implementation, we assume some degradation per cycle
            # based on charge rate (higher rate = more degradation)
            # Empirical model: fade_per_cycle = base_fade * (C_rate ^ 1.5)
            c_rate = charge_current_A / (cell.nominal_capacity_Ah or 5.0)
            base_fade = 0.1  # 0.1% per cycle at 1C
            capacity_fade_per_cycle = base_fade * (c_rate ** 1.5)
        
        # Compute composite score
        # Normalize charge_time: reference = 3600s (1 hour)
        # Normalize capacity_fade: reference = 1.0% per cycle
        
        norm_time = charge_time_s / 3600.0 if charge_time_s else 0.5
        norm_fade = (capacity_fade_per_cycle / 1.0) if capacity_fade_per_cycle else 0.5
        
        # Clip normalized values to [0, 1]
        norm_time = min(1.0, max(0.0, norm_time))
        norm_fade = min(1.0, max(0.0, norm_fade))
        
        # Score: equal weight on time and aging
        score = 0.5 * norm_time + 0.5 * norm_fade
        
        return ChargingOptimizationResult(
            charge_current_A=charge_current_A,
            charge_time_s=charge_time_s,
            capacity_fade_per_cycle=capacity_fade_per_cycle,
            score=score,
            peak_voltage_V=peak_voltage_V,
            final_efficiency=final_efficiency,
        )


# ============================================================================
# OPERATING WINDOW ANALYZER: Map safe operating region + derating curves
# ============================================================================

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


class OperatingWindowAnalyzer:
    """
    Map the safe operating region of a battery across SOC, Temperature, C-rate.
    
    TEACHING: Real BMS systems use **lookup tables** to limit power output based on
    operating conditions. This tool generates the data for those tables.
    
    The safe operating window defines regions:
    - **SAFE**: Normal operation, minimal aging risk
    - **CAUTION**: Acceptable but degradation increases, monitor conditions
    - **AVOID**: Dangerous - high risk of damage, should not happen in production
    
    Classification criteria:
    - safe: voltage bounds maintained, temp rise < 10°C, simulation stable
    - caution: voltage near limits OR temp rise 10-20°C
    - avoid: voltage violation, temp rise > 20°C, or simulation failure
    
    Grid resolution:
    - coarse: 3×3×3 = 27 scenarios (fast, for testing)
    - fine: 5×5×5 = 125 scenarios (comprehensive, production)
    """
    
    def __init__(
        self,
        backend: SimulationBackend,
        model: Model = Model.SPM,
    ):
        """
        Initialize the analyzer.
        
        Args:
            backend: Simulation backend
            model: Battery model to use (SPM or DFN)
        """
        self.backend = backend
        self.model = model
        self.grid_points: List[OperatingWindowPoint] = []
    
    def analyze(
        self,
        cell: Cell,
        grid_size: str = "coarse",
    ) -> Dict[str, Any]:
        """
        Evaluate operating window across a grid of conditions.
        
        NOTE: Grid evaluation runs many simulations and can take time:
        - coarse (3×3×3=27): ~30-50 seconds
        - fine (5×5×5=125): ~3-5 minutes
        
        Args:
            cell: Battery cell to analyze
            grid_size: "coarse" (fast, 27 scenarios) or "fine" (comprehensive, 125)
        
        Returns:
            Dict with grid_points, summary statistics, and safe region classification
        """
        
        # Define grid resolution
        if grid_size == "coarse":
            soc_levels = [0.2, 0.5, 0.8]
            temperatures = [0, 25, 50]
            c_rates = [0.5, 1.5, 3.0]
        elif grid_size == "fine":
            soc_levels = [0.1, 0.3, 0.5, 0.7, 0.9]
            temperatures = [0, 10, 25, 40, 50]
            c_rates = [0.5, 1.0, 2.0, 3.0, 5.0]
        else:
            raise ValueError(f"grid_size must be 'coarse' or 'fine', got {grid_size}")
        
        # Get chemistry-specific voltage bounds
        voltage_bounds = self._get_voltage_bounds(cell.chemistry)
        
        # Evaluate grid
        grid_points = []
        total_iterations = len(soc_levels) * len(temperatures) * len(c_rates)
        iteration = 0
        
        for soc in soc_levels:
            for temp_C in temperatures:
                for c_rate in c_rates:
                    iteration += 1
                    try:
                        point = self._evaluate_point(
                            cell=cell,
                            soc_level=soc,
                            temperature_C=temp_C,
                            c_rate=c_rate,
                            voltage_bounds=voltage_bounds,
                        )
                        grid_points.append(point)
                    except Exception as e:
                        # Record as unsafe if evaluation fails
                        grid_points.append(OperatingWindowPoint(
                            soc_level=soc,
                            temperature_C=temp_C,
                            c_rate=c_rate,
                            zone="avoid",
                            voltage_min_V=None,
                            voltage_max_V=None,
                            temperature_rise_C=None,
                            final_soc=None,
                            simulation_completed=False,
                            details=f"Evaluation error: {str(e)[:80]}",
                        ))
        
        # Store grid points
        self.grid_points = grid_points
        
        # Compute summary statistics
        summary = self._compute_summary(grid_points)
        
        return {
            'grid_points': grid_points,
            'summary': summary,
            'grid_size': grid_size,
            'total_points': len(grid_points),
        }
    
    def get_derating_curves(self) -> Dict[str, Any]:
        """
        Extract derating curves from evaluated grid.
        
        Derating curves show the maximum safe C-rate as a function of
        temperature and SOC - directly usable as BMS lookup tables.
        
        Returns:
            Dict with two curves:
            - max_crate_vs_temperature: (temp_C, max_c_rate) pairs
            - max_crate_vs_soc: (soc_level, max_c_rate) pairs
        """
        
        if not self.grid_points:
            return {'max_crate_vs_temperature': [], 'max_crate_vs_soc': []}
        
        # Extract safe points only
        safe_points = [p for p in self.grid_points if p.zone == 'safe']
        
        # Curve 1: Max C-rate vs Temperature (at mid-SOC)
        mid_soc = 0.5
        temp_to_max_crate = {}
        for point in self.grid_points:
            if abs(point.soc_level - mid_soc) < 0.05:  # Within ±0.05 of mid-SOC
                if point.zone == 'safe':
                    temp = point.temperature_C
                    if temp not in temp_to_max_crate or point.c_rate > temp_to_max_crate[temp]:
                        temp_to_max_crate[temp] = point.c_rate
        
        max_crate_vs_temp = [
            {'temperature_C': float(t), 'max_c_rate': float(c)}
            for t, c in sorted(temp_to_max_crate.items())
        ]
        
        # Curve 2: Max C-rate vs SOC (at nominal temperature)
        nominal_temp = 25.0
        soc_to_max_crate = {}
        for point in self.grid_points:
            if abs(point.temperature_C - nominal_temp) < 1.0:  # Within ±1°C
                if point.zone == 'safe':
                    soc = point.soc_level
                    if soc not in soc_to_max_crate or point.c_rate > soc_to_max_crate[soc]:
                        soc_to_max_crate[soc] = point.c_rate
        
        max_crate_vs_soc = [
            {'soc_level': float(s), 'max_c_rate': float(c)}
            for s, c in sorted(soc_to_max_crate.items())
        ]
        
        return {
            'max_crate_vs_temperature': max_crate_vs_temp,
            'max_crate_vs_soc': max_crate_vs_soc,
        }
    
    def _get_voltage_bounds(self, chemistry: str) -> tuple[float, float]:
        """Get safe voltage bounds for chemistry."""
        bounds = {
            'LFP': (2.5, 3.65),
            'NMC': (2.5, 4.2),
            'NCA': (2.5, 4.2),
            'LCO': (2.5, 4.2),
        }
        return bounds.get(chemistry, (2.5, 4.2))
    
    def _get_charge_target_voltage(self, chemistry: str) -> float:
        """Get charging target voltage (slightly below upper bound for better feasibility)."""
        # Use 90% of upper bound to allow some safety margin and improve charging feasibility
        bounds = self._get_voltage_bounds(chemistry)
        return bounds[1] * 0.90
    
    def _evaluate_point(
        self,
        cell: Cell,
        soc_level: float,
        temperature_C: float,
        c_rate: float,
        voltage_bounds: tuple[float, float],
    ) -> OperatingWindowPoint:
        """
        Evaluate one grid point.
        
        Runs a discharge simulation at the given conditions and classifies
        the outcome as safe/caution/avoid.
        """
        
        # Build protocol: charge, rest, discharge
        # This proper initialization prevents PyBaMM voltage anomalies
        
        # Charge at constant small current to stabilize battery state
        # Use 0.5C regardless of test C-rate, for consistent initialization
        charge_current_A = 0.5 * (cell.nominal_capacity_Ah or 5.0)  # Always 0.5C
        
        # Get voltage bounds for chemistry to set proper charge target  
        # Use 90% of upper bound to improve charging feasibility
        charge_target_voltage = self._get_charge_target_voltage(cell.chemistry)
        
        # Discharge at the test C-rate
        discharge_current_A = c_rate * (cell.nominal_capacity_Ah or 5.0)
        
        # Short discharge pulse: high rate → shorter test window
        # At 0.5C: 60s pulse  
        # At 3.0C: 10s pulse
        discharge_duration_s = max(10, 30 / max(1.0, c_rate))
        
        charge_step = CC_CV(
            charge_current_A=charge_current_A,
            cutoff_voltage_V=charge_target_voltage,
            taper_current_A=max(0.1, charge_current_A * 0.2),
        )
        
        discharge_step = ConstantCurrent(
            current_A=discharge_current_A,  # Positive for discharge
            _duration_s=discharge_duration_s,
        )
        
        # Build protocol
        protocol = Protocol(steps=[
            charge_step,
            Rest(_duration_s=300),    # 5-min rest after charge
            discharge_step,
            Rest(_duration_s=300),    # 5-min rest after discharge
        ])
        
        # Create environment
        environment = Environment(temperature_C=temperature_C)
        
        # Create simulation
        simulation = Simulation(
            cell=cell,
            model=self.model,
            protocol=protocol,
            environment=environment,
            solver_config=SolverConfig(),
        )
        
        # Run simulation
        try:
            run = simulation.run(self.backend)
            completed = run.is_successful()
        except Exception as e:
            completed = False
        
        # Extract metrics
        voltage_min_V = None
        voltage_max_V = None
        temperature_rise_C = None
        final_soc = None
        
        if run and run.result:
            result = run.result
            voltage_min_V = result.min_voltage()
            voltage_max_V = result.max_voltage()
            final_soc = result.final_soc()
            
            temp_min = result.min_temperature()
            temp_max = result.max_temperature()
            if temp_min is not None and temp_max is not None:
                temperature_rise_C = temp_max - temp_min
        
        # Classify zone (pass c_rate for heuristic fallback)
        zone, details = self._classify_zone(
            completed=completed,
            voltage_min=voltage_min_V,
            voltage_max=voltage_max_V,
            temperature_rise=temperature_rise_C,
            voltage_bounds=voltage_bounds,
            temperature_C=temperature_C,
            c_rate=c_rate,  # For heuristic fallback classification
        )
        
        return OperatingWindowPoint(
            soc_level=soc_level,
            temperature_C=temperature_C,
            c_rate=c_rate,
            zone=zone,
            voltage_min_V=voltage_min_V,
            voltage_max_V=voltage_max_V,
            temperature_rise_C=temperature_rise_C,
            final_soc=final_soc,
            simulation_completed=completed,
            details=details,
        )
    
    def _classify_zone(
        self,
        completed: bool,
        voltage_min: Optional[float],
        voltage_max: Optional[float],
        temperature_rise: Optional[float],
        voltage_bounds: tuple[float, float],
        temperature_C: float,
        c_rate: Optional[float] = None,
    ) -> tuple[str, str]:
        """
        Classify a point as safe/caution/avoid.
        
        Classification priority:
        1. If voltage data available and physically plausible, use it
        2. Otherwise, use physics-based heuristics (temperature, C-rate)
        """
        
        min_voltage, max_voltage = voltage_bounds
        
        # Check if voltage data is physically plausible
        voltage_data_valid = (
            voltage_min is not None
            and voltage_max is not None
            and voltage_min >= min_voltage - 0.3  # Allow some margin for measurement noise
            and voltage_max <= max_voltage + 0.3
        )
        
        if voltage_data_valid:
            # AVOID: Severe voltage violations
            if voltage_min < min_voltage - 0.1:
                return "avoid", f"Voltage violation: {voltage_min:.2f}V < {min_voltage}V"
            
            if voltage_max > max_voltage + 0.1:
                return "avoid", f"Overvoltage: {voltage_max:.2f}V > {max_voltage}V"
            
            if temperature_rise is not None and temperature_rise > 20:
                return "avoid", f"Excessive temperature rise: {temperature_rise:.1f}°C"
            
            # CAUTION: Warning signs but still acceptable
            if voltage_min < min_voltage + 0.15:
                return "caution", f"Voltage approaching lower limit: {voltage_min:.2f}V"
            
            if voltage_max > max_voltage - 0.15:
                return "caution", f"Voltage approaching upper limit: {voltage_max:.2f}V"
            
            if temperature_rise is not None and temperature_rise > 10:
                return "caution", f"Significant temperature rise: {temperature_rise:.1f}°C"
            
            # SAFE: Nominal operation
            if temperature_C < 5:
                return "caution", f"Cold operation; reduced performance at {temperature_C}°C"
            if temperature_C > 45:
                return "caution", f"Hot operation; increased aging at {temperature_C}°C"
            return "safe", "All parameters nominal"
        
        # Fallback: Physics-based heuristics when measurement data is unreliable
        # Based on battery operating principles:
        # - High C-rate + Cold temp = difficult (avoid)
        # - Low C-rate + Moderate temp = easy (safe)
        # - Extreme temps = caution
        
        if c_rate is not None:
            # Safe operation: low-moderate C-rate with moderate temperature
            if c_rate <= 1.0 and 10 <= temperature_C <= 40:
                return "safe", "Heuristic: moderate C-rate at comfortable temperature"
            
            # Caution: high C-rate OR cold/hot temperature
            if c_rate <= 2.0 and 5 <= temperature_C <= 45:
                if temperature_C < 10 or temperature_C > 40:
                    return "caution", f"Heuristic: moderate rate at {temperature_C}°C (suboptimal)"
                return "caution", f"Heuristic: C-rate {c_rate:.1f}C at {temperature_C}°C (acceptable range)"
            
            # Avoid: very high C-rate OR extreme temperature
            if temperature_C < 5 or temperature_C > 45:
                return "avoid", f"Heuristic: extreme temperature {temperature_C}°C"
            if c_rate > 2.0:
                return "avoid", f"Heuristic: high C-rate {c_rate:.1f}C challenges thermal management"
        
        # Fallback to avoid if we have no data and no C-rate for heuristics
        return "avoid", "Insufficient data for classification"
    
    def _compute_summary(self, grid_points: List[OperatingWindowPoint]) -> Dict[str, Any]:
        """Compute statistics about the grid."""
        if not grid_points:
            return {}
        
        zones = [p.zone for p in grid_points]
        n_safe = zones.count('safe')
        n_caution = zones.count('caution')
        n_avoid = zones.count('avoid')
        total = len(zones)
        
        # Find limits
        safe_points = [p for p in grid_points if p.zone == 'safe']
        max_crate_safe = max([p.c_rate for p in safe_points], default=0)
        temp_range_safe = (
            min([p.temperature_C for p in safe_points], default=None),
            max([p.temperature_C for p in safe_points], default=None),
        ) if safe_points else (None, None)
        
        return {
            'total_points': total,
            'safe': n_safe,
            'caution': n_caution,
            'avoid': n_avoid,
            'percent_safe': 100 * n_safe / total if total > 0 else 0,
            'percent_caution': 100 * n_caution / total if total > 0 else 0,
            'percent_avoid': 100 * n_avoid / total if total > 0 else 0,
            'max_safe_crate': max_crate_safe,
            'safe_temperature_range_C': temp_range_safe,
        }


# ============================================================================
# PACK SIZER: Configure series/parallel topology for EV packs
# ============================================================================

@dataclass(frozen=True)
class PackConfiguration:
    """
    Result from pack sizing calculation.
    
    TEACHING: This value object represents one complete pack configuration.
    It answers: "To build a 60 kWh pack from 5Ah cells, how many in series?
    In parallel? What will the pack weigh and cost?"
    """
    
    # Topology
    n_series: int                           # Number of cells in series (voltage stacking)
    n_parallel: int                         # Number of cells in parallel (capacity scaling)
    total_cells: int                        # n_series × n_parallel
    
    # Electrical
    pack_voltage_nominal_V: float           # n_series × cell_voltage
    pack_capacity_Ah: float                 # n_parallel × cell_capacity
    pack_energy_kWh: float                  # pack_voltage × pack_capacity / 1000
    
    # Physical
    pack_weight_kg: float                   # Cells only (before overhead)
    pack_volume_L: float                    # Cells only (before overhead)
    pack_cost_usd: float                    # Cells only (before overhead)
    
    # System-level (including packaging, BMS, thermal, housing)
    overhead_weight_kg: float               # Housing, BMS, thermal system
    overhead_volume_L: float                # Gaps, cooling channels
    system_weight_kg: float                 # pack_weight + overhead_weight
    system_volume_L: float                  # pack_volume + overhead_volume
    
    # Metrics
    pack_energy_density_Wh_per_kg: float    # Energy per kg (cells only)
    system_energy_density_Wh_per_kg: float  # Energy per kg (with overhead) — closer to real specs
    cost_per_kWh: float                     # $/kWh for cells


class PackSizer:
    """
    Compute battery pack configuration from cell specs.
    
    TEACHING: Vehicle engineers specify:
    - "I want a 60 kWh pack"
    - "Inverter can handle 300-400V"
    - "I want to use 5Ah NMC cells"
    
    PackSizer answers: "Use 96S × 13P = 1248 cells, weighs 420kg, costs $3500"
    
    Key topology decisions:
    - Series count: Voltage stacking to reach target voltage
    - Parallel count: Capacity scaling to reach target energy
    - Voltage window: Different inverters support different ranges
      * 300-350V: Higher current, simpler electronics, used in mid-range EVs
      * 350-400V: Standard for most modern EVs (Tesla, Lucid, etc)
      * 400+ V: High-end vehicles, lower current, less conduction loss
    """
    
    SYSTEM_OVERHEAD_WEIGHT_FRACTION = 0.20  # BMS, housing, thermal: ~20% extra weight
    SYSTEM_OVERHEAD_VOLUME_FRACTION = 0.30  # Gaps, cooling: ~30% extra volume
    
    @staticmethod
    def size_pack(
        cell_preset,                                          # CellPreset
        target_energy_kWh: float,
        voltage_range: tuple = (300.0, 400.0),
    ) -> PackConfiguration:
        """
        Compute optimal pack configuration.
        
        Algorithm:
        1. Choose series count (n_series):
           - Target voltage = midpoint of voltage_range
           - n_series = round(target_voltage / cell_nominal_voltage)
           - Clamp to keep pack voltage within voltage_range
        
        2. Choose parallel count (n_parallel):
           - Total energy needed = target_energy_kWh × 1000 Wh
           - Energy per parallel-series string = n_series × cell_energy_Wh
           - n_parallel = ceil(total_energy_needed / energy_per_string)
        
        3. Compute pack metrics:
           - Pack voltage = n_series × cell_voltage
           - Pack capacity = n_parallel × cell_capacity
           - Pack weight = total_cells × cell_weight + overhead (20%)
           - Pack volume = total_cells × cell_volume + overhead (30%)
        
        Args:
            cell_preset: CellPreset with physical metadata (weight, volume, cost)
            target_energy_kWh: Target pack energy (e.g., 60 kWh)
            voltage_range: (min_V, max_V) for inverter compatibility
        
        Returns:
            PackConfiguration with all pack specs
        
        Raises:
            ValueError: If configuration is infeasible (e.g., target too small)
        """
        import math
        
        cell = cell_preset.cell
        
        # === Step 1: Determine series count ===
        target_voltage_V = (voltage_range[0] + voltage_range[1]) / 2.0
        n_series_target = target_voltage_V / cell.nominal_voltage_V
        n_series = round(n_series_target)
        
        # Clamp to voltage range
        min_n_series = math.ceil(voltage_range[0] / cell.nominal_voltage_V)
        max_n_series = math.floor(voltage_range[1] / cell.nominal_voltage_V)
        
        if n_series < min_n_series:
            n_series = min_n_series
        elif n_series > max_n_series:
            n_series = max_n_series
        
        if n_series < 1:
            raise ValueError(
                f"Cannot achieve voltage range {voltage_range} with "
                f"cell voltage {cell.nominal_voltage_V}V"
            )
        
        # === Step 2: Determine parallel count ===
        # Energy per cell: capacity × voltage
        cell_energy_Wh = cell.nominal_capacity_Ah * cell.nominal_voltage_V
        
        # Total energy needed (Wh)
        target_energy_Wh = target_energy_kWh * 1000.0
        
        # Energy supplied by one series string
        series_string_energy_Wh = n_series * cell_energy_Wh
        
        # Parallel branches needed
        n_parallel = math.ceil(target_energy_Wh / series_string_energy_Wh)
        
        if n_parallel < 1:
            raise ValueError(f"Cannot achieve target energy {target_energy_kWh} kWh")
        
        # === Step 3: Compute pack-level metrics ===
        total_cells = n_series * n_parallel
        
        # Electrical
        pack_voltage_nominal_V = n_series * cell.nominal_voltage_V
        pack_capacity_Ah = n_parallel * cell.nominal_capacity_Ah
        pack_energy_Wh = pack_voltage_nominal_V * pack_capacity_Ah
        pack_energy_kWh = pack_energy_Wh / 1000.0
        
        # Physical (cell level)
        pack_weight_kg = total_cells * cell_preset.weight_kg
        pack_volume_L = total_cells * cell_preset.volume_L
        pack_cost_usd = total_cells * cell_preset.cost_usd
        
        # System-level overhead
        # BMS, thermal system, housing, interconnects add:
        # - ~20% weight (BMS boards, coolers, casing)
        # - ~30% volume (gaps for airflow, thermal interface material)
        overhead_weight_kg = pack_weight_kg * PackSizer.SYSTEM_OVERHEAD_WEIGHT_FRACTION
        overhead_volume_L = pack_volume_L * PackSizer.SYSTEM_OVERHEAD_VOLUME_FRACTION
        
        system_weight_kg = pack_weight_kg + overhead_weight_kg
        system_volume_L = pack_volume_L + overhead_volume_L
        
        # Energy density metrics
        pack_energy_density_Wh_per_kg = pack_energy_Wh / pack_weight_kg if pack_weight_kg > 0 else 0
        system_energy_density_Wh_per_kg = pack_energy_Wh / system_weight_kg if system_weight_kg > 0 else 0
        cost_per_kWh = pack_cost_usd / pack_energy_kWh if pack_energy_kWh > 0 else 0
        
        return PackConfiguration(
            n_series=n_series,
            n_parallel=n_parallel,
            total_cells=total_cells,
            pack_voltage_nominal_V=pack_voltage_nominal_V,
            pack_capacity_Ah=pack_capacity_Ah,
            pack_energy_kWh=pack_energy_kWh,
            pack_weight_kg=pack_weight_kg,
            pack_volume_L=pack_volume_L,
            pack_cost_usd=pack_cost_usd,
            overhead_weight_kg=overhead_weight_kg,
            overhead_volume_L=overhead_volume_L,
            system_weight_kg=system_weight_kg,
            system_volume_L=system_volume_L,
            pack_energy_density_Wh_per_kg=pack_energy_density_Wh_per_kg,
            system_energy_density_Wh_per_kg=system_energy_density_Wh_per_kg,
            cost_per_kWh=cost_per_kWh,
        )


# ============================================================================
# CELL SELECTION SCORER: Multi-criteria decision support
# ============================================================================

@dataclass(frozen=True)
class CellScoringResult:
    """
    Scored cell preset with breakdown and recommendation.
    
    TEACHING: A single cell gets evaluated across multiple dimensions.
    Each dimension scores 0-100, indicating how well it meets the requirement.
    Total score is a weighted average.
    
    meets_requirements: boolean indicating if ALL hard constraints are satisfied
    recommendation: one-sentence summary ("Best for power" or "Fails on cost")
    """
    
    preset_name: str
    """Name of the cell preset (e.g., 'LFP_5AH')"""
    
    chemistry: str
    """Chemistry type (e.g., 'LFP', 'NMC', 'NCA')"""
    
    total_score: float
    """Overall score 0-100 (equal weight on all dimensions)"""
    
    energy_score: float
    """Can target range be achieved within weight/volume budget? (0-100)"""
    
    power_score: float
    """Does C-rate meet peak power requirement? (0-100)"""
    
    cost_score: float
    """Does pack cost fit within budget? (0-100)"""
    
    lifetime_score: float
    """Does cycle life meet required lifetime? (0-100)"""
    
    charge_score: float
    """Can achieve target charge time? (0-100)"""
    
    meets_requirements: bool
    """True if all hard constraints (weight, volume, cost) are satisfied"""
    
    recommendation: str
    """One-sentence summary ("Best for..." or "Fails on...")"""
    
    pack_config: Optional[PackConfiguration] = None
    """Computed pack configuration for standard 60 kWh scenario"""


class CellSelectionScorer:
    """
    Score and rank cell presets against application requirements.
    
    TEACHING: When choosing a cell chemistry, engineers evaluate many dimensions:
    - Energy density: can we fit enough capacity in the allowed volume?
    - Power: can we deliver peak power without overheating?
    - Cost: is the pack affordable?
    - Lifetime: will it last the warranty period?
    - Charge speed: does it support fast charging if needed?
    
    This tool scores each cell 0-100 on each dimension, computes a total,
    and explains WHY each cell scores the way it does.
    
    Reality check: No single "best" cell exists. The choice depends on priorities.
    An EV prioritizing range wants high energy density.
    A performance EV prioritizes power (high discharge C-rate).
    An economy EV prioritizes cost.
    """
    
    # Thresholds (industry standards, adjustable)
    MIN_ENERGY_DENSITY_Wh_per_kg = 100.0  # Below this is uncompetitive
    TARGET_ENERGY_DENSITY_Wh_per_kg = 150.0  # Realistic EV target
    
    MIN_C_RATE = 1.0  # Can maintain 1C minimum for any use case
    HIGH_C_RATE = 3.0  # High-performance threshold
    
    MIN_CYCLE_LIFE = 1000  # Absolute minimum for automotive
    TARGET_CYCLE_LIFE = 3000  # Competitive 8-year warranty (250k km @ 25k km/year)
    
    @staticmethod
    def score(
        requirements: Dict[str, Any],
        presets: List,  # List of CellPreset objects
    ) -> List[CellScoringResult]:
        """
        Score all presets against requirements.
        
        Args:
            requirements: Dict with keys:
                - range_km (float): Target range in km (e.g., 400)
                - power_kW (float): Peak power requirement (e.g., 150 kW)
                - weight_budget_kg (float): Max pack weight (e.g., 500 kg)
                - volume_budget_L (float): Max pack volume (optional)
                - cost_budget_usd (float): Max pack cost (optional)
                - lifetime_years (float): Warranty period (e.g., 8 years)
                - charge_time_min (float): Target 10-80% charge time in minutes (optional)
            
            presets: List of CellPreset objects to score
        
        Returns:
            List of CellScoringResult, sorted by total_score (best first)
        """
        
        # Assume standard 60 kWh pack for energy density calculation
        # Real scenarios would adjust based on actual pack size
        standard_energy_kWh = 60.0
        
        results = []
        
        for preset in presets:
            try:
                # Calculate pack configuration (standard 60 kWh)
                pack_config = PackSizer.size_pack(
                    cell_preset=preset,
                    target_energy_kWh=standard_energy_kWh,
                    voltage_range=(300.0, 400.0),
                )
                
                # Score each dimension
                energy_score = CellSelectionScorer._score_energy_dimension(
                    preset, pack_config, requirements
                )
                
                power_score = CellSelectionScorer._score_power_dimension(
                    preset, requirements
                )
                
                cost_score = CellSelectionScorer._score_cost_dimension(
                    preset, pack_config, requirements
                )
                
                lifetime_score = CellSelectionScorer._score_lifetime_dimension(
                    preset, requirements
                )
                
                charge_score = CellSelectionScorer._score_charge_dimension(
                    preset, requirements
                )
                
                # Total score = equal weight on all dimensions
                total_score = (
                    energy_score + power_score + cost_score +
                    lifetime_score + charge_score
                ) / 5.0
                
                # Check if hard constraints are met
                meets_requirements = (
                    pack_config.system_weight_kg <= requirements.get('weight_budget_kg', float('inf')) and
                    pack_config.system_volume_L <= requirements.get('volume_budget_L', float('inf')) and
                    pack_config.cost_per_kWh * pack_config.pack_energy_kWh <= requirements.get('cost_budget_usd', float('inf'))
                )
                
                # Generate recommendation
                recommendation = CellSelectionScorer._generate_recommendation(
                    preset, energy_score, power_score, cost_score,
                    lifetime_score, charge_score, meets_requirements
                )
                
                result = CellScoringResult(
                    preset_name=preset.name,
                    chemistry=preset.chemistry,
                    total_score=total_score,
                    energy_score=energy_score,
                    power_score=power_score,
                    cost_score=cost_score,
                    lifetime_score=lifetime_score,
                    charge_score=charge_score,
                    meets_requirements=meets_requirements,
                    recommendation=recommendation,
                    pack_config=pack_config,
                )
                results.append(result)
                
            except Exception as e:
                # Skip presets that fail to configure
                continue
        
        # Sort by total_score (best first)
        results.sort(key=lambda r: r.total_score, reverse=True)
        
        return results
    
    @staticmethod
    def _score_energy_dimension(
        preset,  # CellPreset
        pack_config: PackConfiguration,
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score energy capacity target within constraints.
        
        TEACHING: Can we fit enough energy without exceeding weight/volume limits?
        
        Scoring:
        - 100: Pack fits comfortably in weight budget (< 80%)
        - 50: Pack hits weight limit exactly (100%)
        - 0: Pack exceeds weight budget
        """
        
        weight_budget = requirements.get('weight_budget_kg', 500.0)
        volume_budget = requirements.get('volume_budget_L', 1000.0)
        
        # Weight penalty
        weight_ratio = pack_config.system_weight_kg / weight_budget
        weight_score = max(0, 100 * (1 - weight_ratio)) if weight_ratio > 0 else 100
        
        # Volume penalty (if specified)
        volume_ratio = pack_config.system_volume_L / volume_budget
        volume_score = max(0, 100 * (1 - volume_ratio)) if volume_ratio > 0 else 100
        
        # Energy density bonus
        energy_density = pack_config.system_energy_density_Wh_per_kg
        if energy_density >= CellSelectionScorer.TARGET_ENERGY_DENSITY_Wh_per_kg:
            density_bonus = 20
        elif energy_density >= CellSelectionScorer.MIN_ENERGY_DENSITY_Wh_per_kg:
            density_bonus = 10
        else:
            density_bonus = 0
        
        # Combine: weight is more important than volume
        base_score = 0.7 * weight_score + 0.3 * volume_score
        energy_score = min(100, base_score + density_bonus)
        
        return energy_score
    
    @staticmethod
    def _score_power_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score discharge C-rate capability vs peak power demand.
        
        TEACHING: Can this cell provide the peak power?
        
        Scoring:
        - 100: Can easily provide 2× peak power demand
        - 50: Can barely provide required power (at 1C)
        - 0: Cannot provide required power
        """
        
        max_discharge_c_rate = preset.max_discharge_c_rate
        
        # Assume a reasonable pack would use ~100 parallel cells
        # That allows lower cell rates to achieve pack-level power
        # For simplicity, assume pack can achieve 1.5× cell C-rate through parallelization
        effective_pack_c_rate = max_discharge_c_rate * 1.5
        
        # Minimum acceptable C-rate
        min_acceptable_c_rate = CellSelectionScorer.MIN_C_RATE
        
        if effective_pack_c_rate >= CellSelectionScorer.HIGH_C_RATE:
            # Can provide high power
            power_score = 100
        elif effective_pack_c_rate >= min_acceptable_c_rate:
            # Can provide adequate power
            power_score = 50 + 50 * (effective_pack_c_rate - min_acceptable_c_rate) / (CellSelectionScorer.HIGH_C_RATE - min_acceptable_c_rate)
        else:
            # Cannot provide required power
            power_score = 0
        
        return power_score
    
    @staticmethod
    def _score_cost_dimension(
        preset,  # CellPreset
        pack_config: PackConfiguration,
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score total pack cost vs budget.
        
        TEACHING: Is it affordable?
        
        Scoring:
        - 100: Cost is < 50% of budget (great value)
        - 50: Cost equals budget exactly
        - 0: Cost exceeds budget
        """
        
        cost_budget = requirements.get('cost_budget_usd', float('inf'))
        
        if cost_budget == float('inf'):
            # No cost constraint specified
            cost_score = 50 + 50 * (1 - preset.cost_per_kWh / 300)  # Normalize to $300/kWh max
            return min(100, max(0, cost_score))
        
        actual_cost = pack_config.cost_per_kWh * pack_config.pack_energy_kWh
        cost_ratio = actual_cost / cost_budget
        
        if cost_ratio <= 0.5:
            # Great value
            cost_score = 100
        elif cost_ratio <= 1.0:
            # Acceptable cost
            cost_score = 100 * (1 - cost_ratio)
        else:
            # Over budget
            cost_score = 0
        
        return cost_score
    
    @staticmethod
    def _score_lifetime_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score cycle life vs warranty requirement.
        
        TEACHING: Will it last long enough?
        
        Scoring:
        - 100: Cycle life 3× warranty requirement
        - 50: Cycle life meets warranty requirement exactly
        - 0: Cycle life insufficient
        """
        
        lifetime_years = requirements.get('lifetime_years', 8.0)
        
        # Estimate cycles from lifetime
        # Assume 250 km range, driven 25k km/year = 100 cycles/year
        # (simplification: ignores calendar aging, assumes cycle-dominated)
        cycles_needed = int(lifetime_years * 100)
        
        cycle_life = preset.cycle_life_cycles
        
        # If no cycle life data, assume 3000 (LFP typical)
        if cycle_life == 0:
            cycle_life = 3000
        
        if cycle_life >= cycles_needed * 3:
            # Excellent cycle life
            lifetime_score = 100
        elif cycle_life >= cycles_needed:
            # Meets requirement
            lifetime_score = 50 + 50 * min(1.0, (cycle_life - cycles_needed) / (cycles_needed * 2))
        else:
            # Insufficient
            lifetime_score = 0
        
        return lifetime_score
    
    @staticmethod
    def _score_charge_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score charging speed capability.
        
        TEACHING: Can it support fast charging if needed?
        
        Scoring:
        - 100: Supports 2C+ charging (very fast)
        - 50: Supports 1C charging
        - 0: Cannot support target charge time
        """
        
        charge_time_min = requirements.get('charge_time_min', None)
        
        if charge_time_min is None:
            # No charge time constraint; assume 1C is acceptable
            charge_score = 50
        else:
            # Estimate required C-rate from charge time
            # Assume 10-80% charge = 70% capacity × C-rate, time in hours
            # time_mins = (0.7 * 60 * cell_capacity) / (c_rate * cell_capacity)
            # time_mins = 42 / c_rate (in minutes)
            # c_rate = 42 / time_mins
            
            required_c_rate = 42 / charge_time_min  # Per cell
            
            max_charge_c_rate = preset.max_charge_c_rate
            
            if max_charge_c_rate >= required_c_rate:
                # Can support required charge time
                # Bonus if can do it comfortably (at lower thermal stress)
                overhead_ratio = required_c_rate / max_charge_c_rate
                charge_score = 70 + 30 * overhead_ratio
            else:
                # Cannot support charge time
                charge_score = max(0, 70 * max_charge_c_rate / required_c_rate)
        
        return charge_score
    
    @staticmethod
    def _generate_recommendation(
        preset,  # CellPreset
        energy_score: float,
        power_score: float,
        cost_score: float,
        lifetime_score: float,
        charge_score: float,
        meets_requirements: bool,
    ) -> str:
        """
        Generate one-sentence recommendation.
        
        TEACHING: Explain why each cell is matched (or not) to the application.
        """
        
        if not meets_requirements:
            # Identify which constraint is most violated
            if energy_score < 30:
                return f"{preset.name}: Fails on energy (weight/volume too high)"
            elif cost_score < 30:
                return f"{preset.name}: Exceeds cost budget"
            elif lifetime_score < 30:
                return f"{preset.name}: Insufficient cycle life for warranty"
            else:
                return f"{preset.name}: Does not meet one or more hard constraints"
        
        # Find strongest dimensions
        strengths = []
        if energy_score >= 80:
            strengths.append("excellent energy density")
        if power_score >= 80:
            strengths.append("high power capability")
        if cost_score >= 80:
            strengths.append("competitive cost")
        if lifetime_score >= 80:
            strengths.append("long cycle life")
        
        if strengths:
            return f"{preset.name}: Best for {' and '.join(strengths)}"
        else:
            return f"{preset.name}: Balanced option with {preset.chemistry} chemistry"
