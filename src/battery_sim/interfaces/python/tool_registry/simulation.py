"""Focused simulation methods of the engineering API."""

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

class SimulationToolsMixin:
    @agent_tool(
        description="Run a single battery simulation and return performance metrics",
        examples=["Run a simulation with LFP_5AH", "Simulate NMC_5AH at 40°C"],
        maturity="core",
    )
    def run_simulation(
        self,
        preset_name: str,
        current_A: Optional[float] = None,
        duration_s: Optional[float] = None,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Run a single battery simulation and return key performance metrics.

        Args:
            preset_name: Cell chemistry preset name (e.g. 'LFP_5AH')
            current_A: Discharge current in Amps (defaults to protocol default)
            duration_s: Simulation duration in seconds (defaults to protocol default)
            temperature_C: Ambient temperature in °C (default 25)

        Returns:
            DualFormatResult with simulation metrics
        """
        return self._simulation_tool.run(
            preset_name=preset_name,
            current_A=current_A,
            duration_s=duration_s,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Experimentally extrapolate an aging trend from a short simulated cycle window",
        examples=[
            "Explore aging for NMC_OKANE_AGING under typical daily cycling",
            "Extrapolate the short-run capacity trend with explicit limits",
        ]
    )
    def predict_lifetime(
        self,
        preset_name: str,
        usage_profile: Optional[Dict[str, Any]] = None,
        n_representative_cycles: int = 50,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Delegate experimental aging extrapolation to its interface handler."""
        return self._degradation_tools.predict_lifetime(
            preset_name=preset_name,
            usage_profile=usage_profile,
            n_representative_cycles=n_representative_cycles,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Screen an ideal nominal pack topology from a cell preset and target energy",
        examples=[
            "Size a 60 kWh pack using NMC_5AH cells",
            "How many cells needed for 100 kWh with LFP?",
        ]
    )
    def pack_sizing(
        self,
        preset_name: str,
        target_energy_kWh: float = 60.0,
        voltage_range: tuple = (300.0, 400.0),
    ) -> DualFormatResult:
        """Delegate experimental pack topology screening to its handler."""
        return self._vehicle_tools.pack_sizing(
            preset_name=preset_name,
            target_energy_kWh=target_energy_kWh,
            voltage_range=voltage_range,
        )
    @agent_tool(
        description="Experimentally rank cell presets against explicit pack and vehicle assumptions",
        examples=[
            "Which cell chemistry is best for a 400 km range, 150 kW power, 500 kg weight budget?",
            "Compare LFP vs NMC for 8-year warranty with fast charging",
        ]
    )
    def cell_selection_wizard(
        self,
        range_km: float = 400.0,
        power_kW: float = 150.0,
        weight_budget_kg: float = 500.0,
        lifetime_years: float = 8.0,
        volume_budget_L: Optional[float] = None,
        cost_budget_usd: Optional[float] = None,
        charge_time_min: Optional[float] = None,
    ) -> DualFormatResult:
        """Delegate experimental cell-to-vehicle screening to its handler."""
        return self._vehicle_tools.cell_selection(
            range_km=range_km,
            power_kW=power_kW,
            weight_budget_kg=weight_budget_kg,
            lifetime_years=lifetime_years,
            volume_budget_L=volume_budget_L,
            cost_budget_usd=cost_budget_usd,
            charge_time_min=charge_time_min,
        )
    @agent_tool(
        description="Experimentally screen a warranty target using an unvalidated linear aging extrapolation",
        examples=[
            "Screen NMC_OKANE_AGING for 8 years / 160k km / 80% SOH",
            "Explore a warranty scenario at 35°C with aggressive usage",
        ]
    )
    def warranty_analysis(
        self,
        preset_name: str,
        warranty_years: float = 8.0,
        warranty_km: float = 160000.0,
        warranty_soh_threshold: float = 0.80,
        usage_profile: Optional[Dict[str, Any]] = None,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Delegate experimental warranty screening to its interface handler."""
        return self._degradation_tools.warranty_analysis(
            preset_name=preset_name,
            warranty_years=warranty_years,
            warranty_km=warranty_km,
            warranty_soh_threshold=warranty_soh_threshold,
            usage_profile=usage_profile,
            temperature_C=temperature_C,
        )
    @agent_tool(
        description="Experimentally screen single-charge CC-CV duration over a current grid",
        examples=[
            "Screen CC-CV charge rates for LFP_5AH",
            "Compare feasible charging currents without claiming aging optimization",
        ]
    )
    def optimize_charging(
        self,
        preset_name: str,
        charge_current_range_A: tuple[float, float] = (1.0, 10.0),
        n_sweep_points: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Delegate experimental single-charge rate screening."""
        return self._charging_tools.optimize_charging(
            preset_name=preset_name,
            charge_current_range_A=charge_current_range_A,
            n_sweep_points=n_sweep_points,
            temperature_C=temperature_C,
        )
