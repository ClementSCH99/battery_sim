"""Focused classification behavior."""

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

class ClassificationMixin:
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
