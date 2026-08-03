"""Cell voltage-pulse operating-window screening logic."""

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


class OperatingWindowAnalyzer:
    """
    Screen voltage response across SOC, ambient temperature and discharge C-rate.
    
    The labels produced here are exploratory voltage-pulse classifications. They
    are not safety qualification results or calibrated BMS limits.
    
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
    - fine: 5×5×5 = 125 scenarios (more detailed screening)
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
        voltage_bounds = self._get_voltage_bounds(cell)
        
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
        Extract candidate derating samples from the evaluated grid.
        
        Derating curves show the maximum safe C-rate as a function of
        temperature and SOC. They require cell-test validation before any BMS use.
        
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
    
    def _get_voltage_bounds(self, cell: Cell) -> tuple[float, float]:
        """Get voltage bounds from preset provenance, then chemistry fallback."""
        if "min_voltage_v" in cell.metadata and "max_voltage_v" in cell.metadata:
            return (
                float(cell.metadata["min_voltage_v"]),
                float(cell.metadata["max_voltage_v"]),
            )
        bounds = {
            'LFP': (2.5, 3.65),
            'NMC': (2.5, 4.2),
            'NCA': (2.5, 4.2),
            'LCO': (2.5, 4.2),
        }
        return bounds.get(cell.chemistry, (2.5, 4.2))
    
    def _get_charge_target_voltage(self, chemistry: str) -> float:
        """Get charging target voltage (slightly below upper bound for better feasibility)."""
        # Use 90% of upper bound to allow some safety margin and improve charging feasibility
        bounds = {
            'LFP': (2.5, 3.65),
            'NMC': (2.5, 4.2),
            'NCA': (2.5, 4.2),
            'LCO': (2.5, 4.2),
        }.get(chemistry, (2.5, 4.2))
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
        
        # Discharge at the test C-rate
        if cell.nominal_capacity_Ah is None or cell.nominal_capacity_Ah <= 0:
            raise ValueError("Operating-window pulses require nominal_capacity_Ah > 0")
        discharge_current_A = c_rate * cell.nominal_capacity_Ah
        
        # Short discharge pulse: high rate → shorter test window
        # At 0.5C: 60s pulse  
        # At 3.0C: 10s pulse
        discharge_duration_s = max(10, 30 / max(1.0, c_rate))
        
        discharge_step = ConstantCurrent(
            current_A=discharge_current_A,  # Positive for discharge
            _duration_s=discharge_duration_s,
        )
        
        # The requested SOC is set directly in SolverConfig. Charging first
        # would erase the SOC dimension that this grid is meant to study.
        protocol = Protocol(steps=[
            discharge_step,
            Rest(_duration_s=60),
        ])
        
        # Create environment
        environment = Environment(temperature_C=temperature_C)
        
        # Create simulation
        simulation = Simulation(
            cell=cell,
            model=self.model,
            protocol=protocol,
            environment=environment,
            solver_config=SolverConfig(initial_soc=soc_level),
        )
        
        # Run simulation
        run = None
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
        
        # Classify from the simulated voltage evidence. No heuristic promotes a
        # failed or data-free point into a safe class.
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
        
        A completed simulation with physically plausible voltage data is required.
        """
        
        min_voltage, max_voltage = voltage_bounds

        if not completed:
            return "avoid", "Simulation failed or returned critical diagnostics"
        
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
        
        return "avoid", "Missing or implausible voltage evidence; no safe fallback applied"
    
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

