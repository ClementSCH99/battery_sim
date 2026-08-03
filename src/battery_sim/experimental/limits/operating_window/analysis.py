"""Focused analysis behavior."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import ConstantCurrent, Protocol, Rest
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig

from battery_sim.experimental.limits.operating_window.models import (
    OperatingWindowPoint,
)

class AnalysisMixin:
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
