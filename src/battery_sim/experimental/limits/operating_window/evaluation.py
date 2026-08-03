"""Focused evaluation behavior."""

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

class EvaluationMixin:
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
