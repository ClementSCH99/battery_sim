"""Focused discovery methods of the engineering API."""

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

class DiscoveryToolsMixin:
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of available tools that the LLM can call.

        TEACHING: This is how LLMs discover what they can do.
        They can call get_available_tools() and inspect the results.

        Returns:
            List of tool descriptions (suitable for Claude's tool_use)
        """

        return discover_agent_tools(self)
    @agent_tool(
        description="Describe the entire battery_sim API",
        examples=["Tell me what battery simulation can do"],
        maturity="core",
    )
    def describe_api(self) -> DualFormatResult:
        """
        Get a comprehensive description of the API.

        Returns:
            DualFormatResult with API documentation
        """

        return self._discovery_tools.describe()
    @agent_tool(
        description="Build a reviewable electrochemical experiment plan without executing it",
        examples=["Plan a 1C NMC discharge and report voltage and electrolyte concentration"],
        maturity="core",
    )
    def plan_experiment(
        self,
        question: str,
        preset_name: Optional[str] = None,
        investigation_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature_C: Optional[float] = None,
        c_rate: Optional[float] = None,
        requested_signals: Optional[List[str]] = None,
    ) -> DualFormatResult:
        """Propose assumptions, model, protocol and signals before execution."""
        return self._planning_tools.create(
            question=question,
            preset_name=preset_name,
            investigation_type=investigation_type,
            model=model,
            temperature_C=temperature_C,
            c_rate=c_rate,
            requested_signals=requested_signals,
        )
    @agent_tool(
        description="Compare a simulated CC cell discharge with measured voltage/current samples",
        examples=["Compare an NMC_CHEN_LGM50 5 A discharge with cycler data"],
        maturity="core",
    )
    def compare_test_data(
        self,
        preset_name: str,
        source: str,
        time_s: List[float],
        voltage_V: List[float],
        applied_current_A: float,
        measured_current_A: Optional[List[float]] = None,
        current_sign_convention: str = "discharge_positive",
        temperature_C: float = 25.0,
        test_id: Optional[str] = None,
        voltage_rmse_limit_V: Optional[float] = None,
    ) -> DualFormatResult:
        """Compare CC-discharge simulation and test only over their shared time range."""
        return self._test_comparison_tools.compare_cc_discharge(
            preset_name=preset_name,
            source=source,
            time_s=time_s,
            voltage_V=voltage_V,
            applied_current_A=applied_current_A,
            measured_current_A=measured_current_A,
            current_sign_convention=current_sign_convention,
            temperature_C=temperature_C,
            test_id=test_id,
            voltage_rmse_limit_V=voltage_rmse_limit_V,
        )
