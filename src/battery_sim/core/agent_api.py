"""
LAYER 5: AGENT API - The Main Interface

TEACHING FOCUS: Clean, discoverable user interface

WHY THIS LAYER EXISTS:
Layers 1-4 are infrastructure. But how does the LLM actually USE them?

Layer 5 is the front door. It provides:
1. A clean Python API that the LLM calls
2. Built-in session management
3. Tool decorators (for MCP / Claude integration)
4. Tool output formatting (automatic JSON + Markdown)

The LLM says: "I want to compare presets"
AgentAPI handles: creating simulations, running them, and formatting SimulationRun-derived tool outputs

KEY DESIGN: Every method is designed to be a "tool" that an LLM can discover and call.

---

EXAMPLE: Using AgentAPI

api = AgentAPI()

# LLM discovers available tools
tools = api.get_available_tools()
# Returns descriptions of what the API can do

# LLM calls a tool
tool_output = api.compare_presets(['LFP_5AH', 'NMC_5AH'])

# Tool output is automatically formatted
print(tool_output.json_data)        # For LLM processing
print(tool_output.markdown_text)    # For engineer reading

# Session tracks everything
print(api.session.get_reasoning_chain())

The AgentAPI is the bridge between:
- LLM (which calls methods) 
- Simulation infrastructure (which returns SimulationRun objects)
- Session tracking (which remembers)
- Tool output formatting (which presents data)

Underlying simulation executions still return SimulationRun. AgentAPI methods
package those runs into DualFormatResult values for interface consumption.
"""

from typing import Dict, List, Any, Optional

from battery_sim.core.services import (
    ComparisonService,
    SensitivityService,
)
from battery_sim.core.api_schema import APISchema
from battery_sim.core.result_formatter import (
    DualFormatResult,
    InsightExtractor,
)
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.solver import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.interface.simulation_tool import SimulationToolHandler
from battery_sim.interface.cell_tools import CellToolHandler
from battery_sim.interface.charging_tools import ChargingToolHandler
from battery_sim.interface.degradation_tools import DegradationToolHandler
from battery_sim.interface.discovery_tools import DiscoveryToolHandler, discover_agent_tools
from battery_sim.interface.investigation_tools import EVAssumptions, InvestigationToolHandler
from battery_sim.interface.operating_tools import OperatingToolHandler
from battery_sim.interface.planning_tools import ExperimentPlanningToolHandler
from battery_sim.interface.session_tools import SessionToolHandler
from battery_sim.interface.test_comparison_tools import ModelTestComparisonToolHandler
from battery_sim.interface.vehicle_tools import VehicleToolHandler


# ============================================================================
# TOOL DECORATOR: Mark methods as discoverable by LLM
# ============================================================================

def agent_tool(
    description: str,
    examples: Optional[List[str]] = None,
    maturity: str = "experimental",
):
    """
    Decorator to mark a method as an LLM-accessible tool.
    
    TEACHING: This is how we tell the LLM "this method can be called."
    The decorator attaches metadata (description, examples) so the LLM
    knows what the tool does before calling it.
    
    Args:
        description: One-sentence description of what the tool does
        examples: List of example usage strings
        maturity: ``core`` for reviewed first-product capabilities, otherwise
            ``experimental`` until physical assumptions are reviewed.
    """
    if maturity not in {"core", "experimental", "legacy"}:
        raise ValueError(f"Unsupported tool maturity: {maturity}")
    def decorator(func):
        func._is_agent_tool = True
        func._tool_description = description
        func._tool_examples = examples or []
        func._tool_maturity = maturity
        return func
    return decorator


# ============================================================================
# AGENT API
# ============================================================================

class AgentAPI:
    """High-level, LLM-friendly API for battery simulation investigations.

    Stateful: maintains a ``SimulationSession`` that records every investigation.
    Every tool method returns a ``DualFormatResult`` (JSON + Markdown).

    Core tools:
        list_presets, run_simulation, compare_presets,
        sensitivity_analysis, check_feasibility.

    Session tools:
        get_session_summary, get_reasoning_chain, save_session.
    """
    
    def __init__(
        self,
        session_name: str = "Battery Investigation",
        default_protocol: Optional[Protocol] = None,
        default_model: Model = Model.SPM,
        default_solver_config: Optional[SolverConfig] = None,
        backend: Optional[SimulationBackend] = None,
    ):
        """
        Initialize AgentAPI with configuration.
        
        Args:
            session_name: Name for tracking this investigation
            default_protocol: Default discharge protocol (if None, uses standard)
            default_model: Battery model (SPM or DFN)
            default_solver_config: Solver configuration (if None, uses defaults)
            backend: Simulation engine adapter. Defaults to PyBaMM. Supplying a
                backend keeps the agent facade testable and independent from a
                particular simulation engine.
        """
        
        # Infrastructure
        self.schema = APISchema()
        self.session = SimulationSession(name=session_name)
        
        # Configuration
        self.default_protocol = default_protocol or Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=3600),  # 1-hour discharge
        ])
        self.default_model = default_model
        self.default_solver_config = default_solver_config or SolverConfig()
        self._backend = backend if backend is not None else PyBaMMBackend()
        self.comparison_service = ComparisonService(backend=self._backend)
        self.sensitivity_service = SensitivityService(backend=self._backend)
        self._cell_tools = CellToolHandler(schema=self.schema)
        self._discovery_tools = DiscoveryToolHandler(
            schema=self.schema,
            catalog_provider=self.get_available_tools,
        )
        self._degradation_tools = DegradationToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._charging_tools = ChargingToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._operating_tools = OperatingToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._session_tools = SessionToolHandler(session=self.session)
        self._planning_tools = ExperimentPlanningToolHandler(
            execution_model=self.default_model,
        )
        self._test_comparison_tools = ModelTestComparisonToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
        )
        self._vehicle_tools = VehicleToolHandler(
            session=self.session,
        )
        self._investigation_tools = InvestigationToolHandler(
            backend=self._backend,
            session=self.session,
            default_protocol=self.default_protocol,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
            comparison_service=self.comparison_service,
            sensitivity_service=self.sensitivity_service,
        )
        self._simulation_tool = SimulationToolHandler(
            backend=self._backend,
            session=self.session,
            default_protocol=self.default_protocol,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
        )
    
    # ========================================================================
    # DISCOVERY: What can I do?
    # ========================================================================
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of available tools that the LLM can call.
        
        TEACHING: This is how LLMs discover what they can do.
        They can call get_available_tools() and inspect the results.
        
        Returns:
            List of tool descriptions (suitable for Claude's tool_use)
        """
        
        return discover_agent_tools(self)
    
    # ========================================================================
    # INTROSPECTION TOOLS
    # ========================================================================
    
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
        requested_signals: Optional[List[str]] = None,
    ) -> DualFormatResult:
        """Propose assumptions, model, protocol and signals before execution."""
        return self._planning_tools.create(
            question=question,
            preset_name=preset_name,
            investigation_type=investigation_type,
            model=model,
            temperature_C=temperature_C,
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
    
    # ========================================================================
    # INVESTIGATION TOOLS
    # ========================================================================
    
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

    # ========================================================================
    # CHARGING STRATEGIES
    # ========================================================================

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

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

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
