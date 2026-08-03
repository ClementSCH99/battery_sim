"""Focused comparison methods of the engineering API."""

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

class ComparisonToolsMixin:
    @agent_tool(
        description="List available cell chemistry presets",
        maturity="core",
    )
    def list_presets(self, chemistry: Optional[str] = None) -> DualFormatResult:
        """
        List available cell presets.

        Args:
            chemistry: Filter by chemistry (e.g., 'LFP', 'NMC')

        Returns:
            DualFormatResult with preset listing
        """

        return self._cell_tools.list_presets(chemistry=chemistry)
    @agent_tool(
        description="Compare multiple cell chemistry presets side-by-side",
        examples=[
            "Compare LFP_5AH, NMC_5AH, and NCA_5AH",
            "Which is better for high power?",
        ],
        maturity="experimental",
    )
    def compare_presets(
        self,
        preset_names: List[str],
        environment_temp_C: Optional[float] = None,
    ) -> DualFormatResult:
        """
        Compare multiple cell presets with EV-specific metrics.

        TEACHING: This is a high-level tool. The LLM says what presets to compare.
        The API handles all the simulation details and EV-relevant metrics.

        Args:
            preset_names: List of preset names
            environment_temp_C: Ambient temperature around the cell (default 25°C)

        Returns:
            DualFormatResult with comparison including EV metrics and Ragone data
        """

        return self._investigation_tools.compare_presets(
            preset_names=preset_names,
            environment_temp_C=environment_temp_C,
        )
    @staticmethod
    def _compute_ev_metrics(preset_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Compute EV-specific metrics for each preset.

        Metrics:
        - Gravimetric energy density (Wh/kg) — weight impact
        - Volumetric energy density (Wh/L) — space impact
        - Cost per kWh ($/kWh) — affordability
        - Max charge/discharge C-rate — power capability
        - Estimated cycle life — durability

        Returns:
            Dict mapping preset names to their EV metrics
        """
        return EVAssumptions.compute(preset_names)
    @staticmethod
    def _generate_ragone_data(preset_names: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Generate Ragone plot data (power density vs energy density).

        Ragone data shows the power-energy trade-off:
        - Y-axis: Power density (W/kg)
        - X-axis: Energy density (Wh/kg)

        For each preset, we estimate power density from:
        - Discharge C-rate capability
        - Energy density

        Returns:
            Dict with Ragone coordinates for each preset
        """
        return EVAssumptions.ragone(preset_names)
    @agent_tool(
        description="Analyze sensitivity of battery performance to parameter variations",
        maturity="experimental",
    )
    def sensitivity_analysis(
        self,
        preset_name: str,
        parameters: List[str],
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Analyze how parameters affect battery performance.

        TEACHING: This tells us "which parameters matter?"
        A high-sensitivity parameter is critical to get right.
        A low-sensitivity parameter can be ignored.

        Args:
            preset_name: Cell chemistry to analyze
            parameters: List of parameters to vary
            temperature_C: Ambient baseline for non-temperature sweeps

        Returns:
            DualFormatResult with sensitivity analysis
        """

        return self._investigation_tools.sensitivity_analysis(
            preset_name=preset_name,
            parameters=parameters,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Check if a cell/environment combination is physically feasible",
        maturity="experimental",
    )
    def check_feasibility(
        self,
        preset_name: str,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Check physical constraints.

        TEACHING: Not all parameter combinations are feasible.
        This tool checks: "Can I actually build a battery with these specs?"

        Args:
            preset_name: Cell chemistry
            temperature_C: Ambient temperature around the cell

        Returns:
            DualFormatResult with feasibility report
        """

        return self._cell_tools.check_feasibility(
            preset_name=preset_name,
            temperature_C=temperature_C,
        )
