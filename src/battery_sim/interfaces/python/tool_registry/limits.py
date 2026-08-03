"""Focused limits methods of the engineering API."""

from typing import Dict, List, Any, Optional
from battery_sim.application.services import (
    ComparisonService,
    SensitivityService,
)
from battery_sim.interfaces.python.schema import APISchema
from battery_sim.interfaces.presenters.result import (
    DualFormatResult,
    InsightExtractor,
)
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol, ConstantCurrent
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig
from battery_sim.interfaces.python.simulation_tool import SimulationToolHandler
from battery_sim.interfaces.python.cell_tools import CellToolHandler
from battery_sim.interfaces.python.charging_tools import ChargingToolHandler
from battery_sim.interfaces.python.degradation_tools import DegradationToolHandler
from battery_sim.interfaces.python.discovery_tools import DiscoveryToolHandler, discover_agent_tools
from battery_sim.interfaces.python.investigation_tools import EVAssumptions, InvestigationToolHandler
from battery_sim.interfaces.python.operating_tools import OperatingToolHandler
from battery_sim.interfaces.python.planning_tools import ExperimentPlanningToolHandler
from battery_sim.interfaces.python.session_tools import SessionToolHandler
from battery_sim.interfaces.python.test_comparison_tools import ModelTestComparisonToolHandler
from battery_sim.interfaces.python.vehicle_tools import VehicleToolHandler
from battery_sim.interfaces.python.tool_registry.decorators import agent_tool

class LimitsToolsMixin:
    @agent_tool(
        description="Experimentally screen cell voltage response across SOC, temperature, and discharge C-rate"
    )
    def operating_window(
        self,
        preset_name: str,
        grid_size: str = "coarse",
    ) -> DualFormatResult:
        """Delegate exploratory operating-point screening."""
        return self._operating_tools.operating_window(
            preset_name=preset_name,
            grid_size=grid_size,
        )
    @agent_tool(
        description="Derive experimental candidate derating samples from voltage-pulse screening"
    )
    def derating_curves(
        self,
        preset_name: str,
        grid_size: str = "coarse",
    ) -> DualFormatResult:
        """Delegate candidate derating-curve extraction."""
        return self._operating_tools.derating_curves(
            preset_name=preset_name,
            grid_size=grid_size,
        )
    @agent_tool(
        description="Screen EV range by integrating a synthetic pack-level power profile",
        examples=[
            "How far can I go with a 96S40P NMC pack on a WLTP cycle?",
            "Estimate range for LFP_5AH with 150 kW peak power",
        ]
    )
    def estimate_range(
        self,
        preset_name: str,
        cycle_name: str = "WLTP",
        n_series: int = 96,
        n_parallel: int = 40,
        vehicle_mass_kg: float = 1800.0,
        peak_power_kW: float = 150.0,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Delegate experimental pack-to-vehicle range screening to its handler."""
        return self._vehicle_tools.estimate_range(
            preset_name=preset_name,
            cycle_name=cycle_name,
            n_series=n_series,
            n_parallel=n_parallel,
            vehicle_mass_kg=vehicle_mass_kg,
            peak_power_kW=peak_power_kW,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Experimentally compare charging protocols and exclude failed simulations from ranking"
    )
    def compare_charging_strategies(
        self,
        preset_name: str,
        strategies: Optional[List[str]] = None,
        n_cycles: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Delegate experimental charging-strategy comparison."""
        return self._charging_tools.compare_strategies(
            preset_name=preset_name,
            strategies=strategies,
            n_cycles=n_cycles,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Summarize the current investigation session",
        maturity="core",
    )
    def get_session_summary(self) -> str:
        """Get a summary of the current investigation session."""
        return self._session_tools.get_summary()
    def save_session(self, filepath: str) -> None:
        """Save the current session to a file."""
        self.session.save_to_file(filepath)
    def get_reasoning_chain(self) -> str:
        """Get the reasoning chain from this investigation."""
        return self.session.get_reasoning_chain()
