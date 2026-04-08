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

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable
import time

from battery_sim.core.application_services import ComparisonService, SimulationExecutionService
from battery_sim.core.application_services import SensitivityService, CyclingAnalyzer
from battery_sim.core.api_schema import APISchema
from battery_sim.core.investigation_tools import (
    BatchSimulationConfig,
    ConstraintChecker,
    ChargingOptimizer,
    ChargingOptimizationResult,
    OperatingWindowAnalyzer,
    OperatingWindowPoint,
    PackSizer,
    PackConfiguration,
    CellSelectionScorer,
    CellScoringResult,
)
from battery_sim.core.charging_strategies import (
    ChargingStrategyBuilder,
    ChargingStrategyEvaluator,
    ChargingStrategyMetrics,
    ChargingStrategyComparison,
)
from battery_sim.core.result_formatter import (
    DualFormatResult,
    ComparisonFormatter,
    SensitivityFormatter,
    InsightExtractor,
)
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest, CC_CV
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.core.solver import SolverConfig
from battery_sim.core.degradation import UsageProfile, DegradationConfig
from battery_sim.core.drive_cycles import (
    get_drive_cycle, 
    list_drive_cycles,
    scale_drive_cycle,
)
from battery_sim.core.cell_presets import CellPresets
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.types.signal import Signal


# ============================================================================
# CONSTANTS: Drive cycle distances in km
# ============================================================================

DRIVE_CYCLE_DISTANCES_KM = {
    "WLTP": 23.3,      # Worldwide Harmonized Light-duty vehicle Test Procedure
    "WLTP_CLASS3": 23.3,
    "US06": 12.9,      # EPA Supplemental Federal Test Procedure  
    "UDDS": 12.0,      # Urban Dynamometer Driving Schedule
}


# ============================================================================
# TOOL DECORATOR: Mark methods as discoverable by LLM
# ============================================================================

def agent_tool(
    description: str,
    examples: Optional[List[str]] = None,
):
    """
    Decorator to mark a method as an LLM-accessible tool.
    
    TEACHING: This is how we tell the LLM "this method can be called."
    The decorator attaches metadata (description, examples) so the LLM
    knows what the tool does before calling it.
    
    Args:
        description: One-sentence description of what the tool does
        examples: List of example usage strings
    """
    def decorator(func):
        func._is_agent_tool = True
        func._tool_description = description
        func._tool_examples = examples or []
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
    ):
        """
        Initialize AgentAPI with configuration.
        
        Args:
            session_name: Name for tracking this investigation
            default_protocol: Default discharge protocol (if None, uses standard)
            default_model: Battery model (SPM or DFN)
            default_solver_config: Solver configuration (if None, uses defaults)
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
        self._backend = PyBaMMBackend()
        self.comparison_service = ComparisonService(backend=self._backend)
        self.sensitivity_service = SensitivityService(backend=self._backend)
    
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
        
        return self.schema.get_tools()
    
    # ========================================================================
    # INTROSPECTION TOOLS
    # ========================================================================
    
    @agent_tool(
        description="Describe the entire battery_sim API",
        examples=["Tell me what battery simulation can do"]
    )
    def describe_api(self) -> DualFormatResult:
        """
        Get a comprehensive description of the API.
        
        Returns:
            DualFormatResult with API documentation
        """
        
        md_lines = [
            "# Battery Simulation API Overview",
            "",
            "This API enables investigation of battery chemistry choices and performance characteristics.",
            "",
            "## Key Concepts",
            "",
            "1. **Presets**: Pre-configured cell chemistries (LFP, NMC, NCA, etc.)",
            "2. **Parameters**: Tunable properties (capacity, temperature, resistance)",
            "3. **Metrics**: Measurable outcomes (voltage, current, power, efficiency, etc.)",
            "4. **Investigations**: Tools to explore and understand trade-offs",
            "",
            "## Available Investigations",
            "",
            "- **compare_presets**: Which chemistry is best?",
            "- **sensitivity_analysis**: Which parameters matter most?",
            "- **check_feasibility**: Will this scenario work?",
            "",
            self.schema.full_summary(),
        ]
        
        return DualFormatResult(
            json_data={
                'type': 'api_description',
                'tools': self.get_available_tools(),
            },
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Start with exploration to understand available options",
                "Use comparison to evaluate trade-offs",
                "Analyze sensitivity to understand parameter impacts",
            ],
        )
    
    @agent_tool(
        description="List available cell chemistry presets"
    )
    def list_presets(self, chemistry: Optional[str] = None) -> DualFormatResult:
        """
        List available cell presets.
        
        Args:
            chemistry: Filter by chemistry (e.g., 'LFP', 'NMC')
        
        Returns:
            DualFormatResult with preset listing
        """
        
        preset_catalog = self.schema.get_presets()
        
        if chemistry:
            presets = preset_catalog.by_chemistry(chemistry)
            title = f"Presets: {chemistry}"
        else:
            presets = {p.name: p for p in preset_catalog.list_presets()}
            title = "All Available Presets"
        
        json_data = {
            'type': 'preset_list',
            'chemistries': list(preset_catalog.list_chemistries()) if not chemistry else [chemistry],
            'presets': [
                {
                    'name': p.name,
                    'chemistry': p.chemistry,
                    'description': p.description,
                    'capacity_Ah': p.cell.nominal_capacity_Ah,
                    'nominal_voltage_V': p.cell.nominal_voltage_V,
                    'internal_resistance_Ohm': p.cell.internal_resistance_Ohm,
                }
                for p in presets.values()
            ]
        }
        
        markdown = preset_catalog.summary(chemistry=chemistry)
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown,
            interpretation_hints=[
                "Different chemistries show different trade-offs",
                "Compare metrics across scenarios to identify patterns",
                "Consider which metrics matter most for your application",
            ],
        )
    
    # ========================================================================
    # INVESTIGATION TOOLS
    # ========================================================================
    
    @agent_tool(
        description="Compare multiple cell chemistry presets side-by-side",
        examples=[
            "Compare LFP_5AH, NMC_5AH, and NCA_5AH",
            "Which is better for high power?",
        ]
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
        
        # Measure timing for session tracking
        start_time = time.time()
        
        # Set up environment
        environment = Environment(temperature_C=environment_temp_C or 25.0)
        
        # Create batch configuration
        config = BatchSimulationConfig(
            protocol=self.default_protocol,
            environment=environment,
            model=self.default_model,
            solver_config=self.default_solver_config,
            backend=self._backend,
        )
        
        comparison = self.comparison_service.compare_presets(preset_names, config)
        
        # Add EV-specific metrics to comparison
        ev_metrics = self._compute_ev_metrics(preset_names)
        comparison['ev_metrics'] = ev_metrics
        
        # Generate Ragone data for 2+ presets
        if len(preset_names) >= 2:
            ragone_data = self._generate_ragone_data(preset_names)
            comparison['ragone_data'] = ragone_data
        
        # Format results
        formatted = ComparisonFormatter.format_comparison_with_ev(
            preset_names,
            comparison['metrics'],
            ev_metrics=ev_metrics,
            ragone_data=comparison.get('ragone_data'),
        )
        
        # Record in session
        duration = time.time() - start_time
        self.session.record_investigation(
            investigation_type='compare_presets',
            parameters={
                'presets': preset_names,
                'ambient_temperature_C': environment_temp_C or 25.0,
            },
            result_summary=formatted.json_data,
            result_markdown=formatted.markdown_text,
            duration_seconds=duration,
            key_findings=formatted.interpretation_hints,
        )
        
        return formatted
    
    @staticmethod
    def _compute_ev_metrics(preset_names: List[str]) -> Dict[str, Dict[str, float]]:
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
        from battery_sim.core.cell_presets import CellPresets
        
        ev_metrics = {}
        for preset_name in preset_names:
            preset = CellPresets.get(preset_name)
            ev_metrics[preset_name] = {
                'energy_density_Wh_per_kg': preset.energy_density_Wh_per_kg,
                'energy_density_Wh_per_L': preset.energy_density_Wh_per_L,
                'cost_per_kWh': preset.cost_per_kWh,
                'max_charge_c_rate': preset.max_charge_c_rate,
                'max_discharge_c_rate': preset.max_discharge_c_rate,
                'cycle_life_cycles': preset.cycle_life_cycles,
                'nominal_energy_Wh': preset.nominal_energy_Wh,
            }
        
        return ev_metrics
    
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
        from battery_sim.core.cell_presets import CellPresets
        
        ragone_data = {}
        for preset_name in preset_names:
            preset = CellPresets.get(preset_name)
            
            # Power = Energy × C-rate
            # Power density = (Energy × C-rate) / Weight
            energy_Wh = preset.nominal_energy_Wh
            weight_kg = preset.weight_kg
            
            if weight_kg > 0 and energy_Wh > 0:
                # Peak power assuming max discharge C-rate
                peak_power_W = energy_Wh * preset.max_discharge_c_rate
                power_density_W_per_kg = peak_power_W / weight_kg
                
                # Energy density
                energy_density_Wh_per_kg = preset.energy_density_Wh_per_kg
                
                ragone_data[preset_name] = {
                    'energy_density_Wh_per_kg': energy_density_Wh_per_kg,
                    'power_density_W_per_kg': power_density_W_per_kg,
                }
        
        return ragone_data
    
    @agent_tool(
        description="Analyze sensitivity of battery performance to parameter variations"
    )
    def sensitivity_analysis(
        self,
        preset_name: str,
        parameters: List[str],
    ) -> DualFormatResult:
        """
        Analyze how parameters affect battery performance.
        
        TEACHING: This tells us "which parameters matter?"
        A high-sensitivity parameter is critical to get right.
        A low-sensitivity parameter can be ignored.
        
        Args:
            preset_name: Cell chemistry to analyze
            parameters: List of parameters to vary
        
        Returns:
            DualFormatResult with sensitivity analysis
        """
        
        start_time = time.time()
        
        # Get cell from preset
        baseline_cell = Cell.preset(preset_name)
        
        # Configuration
        config = BatchSimulationConfig(
            protocol=self.default_protocol,
            environment=Environment(temperature_C=25.0),
            model=self.default_model,
            solver_config=self.default_solver_config,
            backend=self._backend,
        )
        
        # Define ranges for parameters
        parameter_ranges = {
            'temperature_C': [0, 15, 25, 40, 55],
            'nominal_capacity_Ah': [3.0, 4.0, 5.0, 6.0, 7.0],
            'internal_resistance_Ohm': [0.02, 0.05, 0.08, 0.12],
        }
        
        # Run sensitivity analysis for each parameter
        sensitivity_results = []
        for param in parameters:
            if param not in parameter_ranges:
                continue
            
            # Create metric extractor
            def make_metric_extractor(run):
                if run and hasattr(run, 'result'):
                    try:
                        return float(run.result.peak_power() or 0)
                    except:
                        return 0.0
                return 0.0
            
            result = self.sensitivity_service.analyze_single_parameter(
                baseline_cell,
                param,
                parameter_ranges[param],
                config,
                make_metric_extractor,
            )
            sensitivity_results.append(result)
        
        # Format results
        formatted = SensitivityFormatter.format_sensitivity(sensitivity_results)
        
        # Record in session
        duration = time.time() - start_time
        self.session.record_investigation(
            investigation_type='sensitivity_analysis',
            parameters={
                'preset': preset_name,
                'parameters': parameters,
            },
            result_summary=formatted.json_data,
            result_markdown=formatted.markdown_text,
            duration_seconds=duration,
            key_findings=formatted.interpretation_hints,
        )
        
        return formatted
    
    @agent_tool(
        description="Check if a cell/environment combination is physically feasible"
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
        
        # Get cell
        cell = Cell.preset(preset_name)
        environment = Environment(temperature_C=temperature_C)
        
        # Check constraints
        violations = ConstraintChecker.check_cell_feasibility(cell)
        violations += ConstraintChecker.check_protocol_feasibility(cell, environment)
        
        # Format as result
        is_feasible = not any(v.violated and v.severity == 'critical' for v in violations)
        
        json_data = {
            'type': 'feasibility_check',
            'preset': preset_name,
            'ambient_temperature_C': temperature_C,
            'feasible': is_feasible,
            'critical_violations': [v.message for v in violations if v.severity == 'critical'],
            'warnings': [v.message for v in violations if v.severity == 'warning'],
        }
        
        markdown = ConstraintChecker.get_feasibility_report(cell, environment)
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown,
            interpretation_hints=[
                "Review reported violations and constraints",
                "Consider if alternative parameters might improve feasibility",
            ],
        )
    
    @agent_tool(
        description="Run a single battery simulation and return performance metrics",
        examples=["Run a simulation with LFP_5AH", "Simulate NMC_5AH at 40°C"]
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
        start_time = time.time()

        cell = Cell.preset(preset_name)

        if current_A is not None or duration_s is not None:
            protocol = Protocol(steps=[
                ConstantCurrent(
                    current_A=current_A or self.default_protocol.steps[0].current_A,
                    _duration_s=duration_s or self.default_protocol.steps[0]._duration_s,
                ),
            ])
        else:
            protocol = self.default_protocol

        environment = Environment(temperature_C=temperature_C)
        simulation = Simulation(
            cell=cell,
            model=self.default_model,
            protocol=protocol,
            environment=environment,
            solver_config=self.default_solver_config,
        )

        execution_service = SimulationExecutionService(backend=self._backend)
        run = execution_service.execute(simulation)

        metrics = ComparisonService.extract_metrics(run)

        json_data = {
            'type': 'simulation_result',
            'preset': preset_name,
            'temperature_C': temperature_C,
            'metrics': metrics,
        }

        md_lines = [
            f"# Simulation Result: {preset_name}",
            "",
            f"**Temperature**: {temperature_C}°C",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        for key, value in metrics.items():
            if isinstance(value, float):
                md_lines.append(f"| {key} | {value:.4f} |")
            else:
                md_lines.append(f"| {key} | {value} |")

        duration = time.time() - start_time

        self.session.record_investigation(
            investigation_type='run_simulation',
            parameters={
                'preset': preset_name,
                'current_A': current_A,
                'duration_s': duration_s,
                'temperature_C': temperature_C,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[],
        )

        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Review peak_power_W and efficiency_percent for overall performance",
                "Compare with other presets using compare_presets for context",
            ],
        )

    @agent_tool(
        description="Predict battery lifetime based on degradation modeling and usage patterns",
        examples=[
            "Predict lifetime for LFP_5AH under typical daily cycling",
            "How many years will this cell last?",
        ]
    )
    def predict_lifetime(
        self,
        preset_name: str,
        usage_profile: Optional[Dict[str, Any]] = None,
        n_representative_cycles: int = 50,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Predict battery lifetime using representative cycling + extrapolation.

        TEACHING: Running 3000+ real cycles is slow. Instead, we:
        1. Run N representative cycles with degradation enabled
        2. Measure capacity fade trend (linear or sqrt fit)
        3. Extrapolate to 80% capacity retention (end-of-life)
        4. Convert cycles to calendar years using usage_profile

        Args:
            preset_name: Cell chemistry preset name
            usage_profile: Dict with daily_charge_cycles, storage_temperature_C, etc.
                          If None, uses UsageProfile defaults
            n_representative_cycles: Number of cycles to simulate (default 50)
            temperature_C: Operating temperature for cycling (°C)

        Returns:
            DualFormatResult with predicted_years, predicted_cycles, capacity_trajectory, etc.
        """
        import numpy as np

        start_time = time.time()

        # Load cell and normalize usage profile
        cell = Cell.preset(preset_name)
        usage = UsageProfile(**usage_profile) if usage_profile else UsageProfile()

        # Build representative cycling protocol using Protocol.cycle():
        # CC-CV charge + rest + CC discharge + rest, repeated n_representative_cycles times
        charge_current_A = cell.nominal_capacity_Ah * 0.5  # 0.5C charge
        discharge_current_A = cell.nominal_capacity_Ah * 0.5  # 0.5C discharge
        cv_voltage_V = cell.nominal_voltage_V * 1.05  # Slightly above nominal

        charge_protocol = Protocol.cccv(
            charge_current_A=charge_current_A,
            cutoff_voltage_V=cv_voltage_V,
            taper_current_A=charge_current_A * 0.1,
        )
        discharge_protocol = Protocol.cc(
            current_A=discharge_current_A,
            duration_s=3600,  # ~1 hour at 0.5C for ~2.5 Ah (50% capacity)
        )

        protocol = Protocol.cycle(
            charge=charge_protocol,
            discharge=discharge_protocol,
            n_cycles=n_representative_cycles,
            rest_s=600,  # 10 minutes rest after each charge/discharge
        )
        environment = Environment(temperature_C=temperature_C)

        # Enable degradation: SEI + calendar aging
        degradation_config = DegradationConfig(
            sei_growth=True,
            calendar_aging=True,
            storage_temperature_C=usage.storage_temperature_C,
            storage_soc=usage.storage_soc,
        )

        # Run simulation with degradation: SEI + calendar aging
        simulation = Simulation(
            cell=cell,
            model=self.default_model,
            protocol=protocol,
            environment=environment,
            solver_config=SolverConfig(initial_soc=0.2),  # Start at 20% SOC to avoid infeasibility
            degradation=degradation_config,
        )

        execution_service = SimulationExecutionService(backend=self._backend)
        run = execution_service.execute(simulation)

        # Extract cycling metrics
        cycling_summary = CyclingAnalyzer.cycling_summary(run)

        if "discharge_capacity_Ah" not in cycling_summary:
            return DualFormatResult(
                json_data={
                    'type': 'lifetime_prediction_error',
                    'error': 'No cycling data available',
                },
                markdown_text="Error: Unable to extract cycling data from simulation.",
                interpretation_hints=[],
            )

        capacities = np.array(cycling_summary["discharge_capacity_Ah"])
        cycles = np.arange(len(capacities))

        if len(capacities) < 2:
            return DualFormatResult(
                json_data={
                    'type': 'lifetime_prediction_error',
                    'error': 'Insufficient cycling data for extrapolation',
                },
                markdown_text="Error: Not enough cycles to fit degradation trend.",
                interpretation_hints=[],
            )

        # Fit linear degradation: capacity = a*cycle + b
        coeffs = np.polyfit(cycles, capacities, 1)
        slope, intercept = coeffs
        initial_capacity = capacities[0]

        if slope >= 0:
            # No degradation observed
            predicted_eol_cycles = 1e6
            capacity_fade_rate = 0.0
        else:
            # Extrapolate to 80% capacity retention
            eol_capacity = initial_capacity * 0.8
            predicted_eol_cycles = (eol_capacity - intercept) / slope
            predicted_eol_cycles = max(int(np.ceil(predicted_eol_cycles)), 1)
            capacity_fade_rate = abs(slope)

        # Convert to years
        cycles_per_day = usage.daily_charge_cycles
        days_to_eol = predicted_eol_cycles / cycles_per_day
        years_to_eol = days_to_eol / 365.25

        # Build capacity trajectory for JSON
        trajectory = [
            {
                'cycle': int(c),
                'discharge_capacity_Ah': float(cap),
                'capacity_retention_pct': float((cap / initial_capacity) * 100),
            }
            for c, cap in zip(cycles[:], capacities[:])
        ]

        # Format output
        json_data = {
            'type': 'lifetime_prediction',
            'preset': preset_name,
            'temperature_C': temperature_C,
            'n_representative_cycles': n_representative_cycles,
            'usage_profile': {
                'daily_km': usage.daily_km,
                'daily_charge_cycles': usage.daily_charge_cycles,
                'storage_temperature_C': usage.storage_temperature_C,
                'storage_soc': usage.storage_soc,
                'fast_charge_ratio': usage.fast_charge_ratio,
            },
            'estimated_years_to_eol': float(years_to_eol),
            'estimated_cycles_to_eol': int(predicted_eol_cycles),
            'capacity_fade_rate_per_cycle_Ah': float(capacity_fade_rate),
            'initial_capacity_Ah': float(initial_capacity),
            'eol_capacity_Ah': float(initial_capacity * 0.8),
            'capacity_trajectory': trajectory,
        }

        md_lines = [
            f"# Lifetime Prediction: {preset_name}",
            "",
            f"**Operating Temperature**: {temperature_C}°C",
            f"**Representative Cycles Simulated**: {n_representative_cycles}",
            "",
            "## Predicted Lifetime",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Estimated Years to EOL (80% capacity)** | {years_to_eol:.1f} |",
            f"| **Estimated Cycles to EOL** | {predicted_eol_cycles:,} |",
            f"| **Capacity Fade Rate** | {capacity_fade_rate:.6f} Ah/cycle |",
            f"| **Initial Capacity** | {initial_capacity:.2f} Ah |",
            f"| **EOL Capacity (80%)** | {initial_capacity * 0.8:.2f} Ah |",
            "",
            "## Usage Profile",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Daily Cycles | {usage.daily_charge_cycles} |",
            f"| Daily Distance | {usage.daily_km} km |",
            f"| Storage Temperature | {usage.storage_temperature_C}°C |",
            f"| Storage SOC | {usage.storage_soc * 100:.0f}% |",
            f"| Fast Charge Ratio | {usage.fast_charge_ratio * 100:.0f}% |",
            "",
            "## Capacity Degradation Trajectory",
            "",
            "| Cycle | Capacity (Ah) | Retention (%) |",
            "|-------|---------------|---------------|",
        ]

        for item in trajectory:
            md_lines.append(
                f"| {item['cycle']:,} | {item['discharge_capacity_Ah']:.3f} | {item['capacity_retention_pct']:.1f}% |"
            )

        duration = time.time() - start_time

        self.session.record_investigation(
            investigation_type='predict_lifetime',
            parameters={
                'preset': preset_name,
                'n_cycles': n_representative_cycles,
                'temperature_C': temperature_C,
                'usage_profile': usage_profile,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Estimated lifetime: {years_to_eol:.1f} years ({predicted_eol_cycles:,} cycles)",
                f"Capacity fade rate: {capacity_fade_rate:.6f} Ah/cycle at {temperature_C}°C",
            ],
        )

        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Higher operating temperatures accelerate aging (Arrhenius effect)",
                "Deep cycling worse than shallow cycling; frequent rest helps mitigate calendar aging",
                "This prediction assumes consistent usage profile; real-world variations will differ",
            ],
        )

    @agent_tool(
        description="Size a battery pack from cell preset and target energy",
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
        """
        Size a battery pack from cell preset and target energy.
        
        TEACHING: Vehicle engineers specify target energy (e.g., 60 kWh for a
        mid-range EV). This tool computes:
        - How many cells in series (voltage stacking)
        - How many cells in parallel (capacity scaling)
        - Pack weight, volume, cost, energy density
        
        Args:
            preset_name: Cell chemistry preset name (e.g., 'NMC_5AH')
            target_energy_kWh: Target pack energy (default 60 kWh)
            voltage_range: (min_V, max_V) for inverter compatibility (default 300-400V)
        
        Returns:
            DualFormatResult with pack configuration and metrics
        """
        start_time = time.time()
        
        # Get cell preset
        cell_preset = CellPresets.get(preset_name)
        
        # Size the pack
        config = PackSizer.size_pack(
            cell_preset=cell_preset,
            target_energy_kWh=target_energy_kWh,
            voltage_range=voltage_range,
        )
        
        # Industry benchmarks for reference
        industry_benchmarks = {
            'cell_energy_density_Wh_per_kg': {
                'typical': 250,
                'high': 280,
                'comment': 'Typical modern NMC/NCA cells',
            },
            'pack_energy_density_Wh_per_kg': {
                'low': 100,
                'typical': 150,
                'high': 200,
                'comment': 'Pack level (including BMS, thermal). Most EVs: 120-185 Wh/kg',
            },
            'cost_per_kwh': {
                'low': 80,
                'typical': 120,
                'high': 150,
                'comment': '2024 market: LFP $80-100, NMC $100-130, NCA $130-150/kWh',
            }
        }
        
        # JSON output
        json_data = {
            'type': 'pack_sizing',
            'preset': preset_name,
            'target_energy_kWh': target_energy_kWh,
            'voltage_range': voltage_range,
            'configuration': {
                'n_series': config.n_series,
                'n_parallel': config.n_parallel,
                'total_cells': config.total_cells,
                'pack_voltage_nominal_V': config.pack_voltage_nominal_V,
                'pack_capacity_Ah': config.pack_capacity_Ah,
                'pack_energy_kWh': config.pack_energy_kWh,
            },
            'physical_metrics': {
                'pack_weight_kg': config.pack_weight_kg,
                'pack_volume_L': config.pack_volume_L,
                'pack_cost_usd': config.pack_cost_usd,
                'system_weight_kg': config.system_weight_kg,
                'system_volume_L': config.system_volume_L,
                'system_energy_density_Wh_per_kg': round(config.system_energy_density_Wh_per_kg, 1),
                'cost_per_kwh': round(config.cost_per_kWh, 2),
            },
            'benchmarks': industry_benchmarks,
        }
        
        # Markdown output
        md_lines = [
            f"# Pack Sizing: {preset_name} → {target_energy_kWh} kWh",
            "",
            "## Configuration",
            "",
            "| Parameter | Value |",
            "|-----------|-------|",
            f"| Series (S) | {config.n_series} |",
            f"| Parallel (P) | {config.n_parallel} |",
            f"| Total cells | {config.total_cells:,} |",
            f"| Pack voltage (nominal) | {config.pack_voltage_nominal_V:.1f} V |",
            f"| Pack capacity | {config.pack_capacity_Ah:.1f} Ah |",
            f"| Actual pack energy | {config.pack_energy_kWh:.2f} kWh |",
            "",
            "## Physical Metrics (Cells Only)",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Weight | {config.pack_weight_kg:.1f} kg |",
            f"| Volume | {config.pack_volume_L:.1f} L |",
            f"| Cost | ${config.pack_cost_usd:,.0f} |",
            f"| Energy density | {config.pack_energy_density_Wh_per_kg:.1f} Wh/kg |",
            "",
            "## System-Level Metrics (with BMS, Thermal, Housing)",
            "",
            "| Metric | Value | Comment |",
            "|--------|-------|---------|",
            f"| System weight | {config.system_weight_kg:.1f} kg | +20% overhead |",
            f"| System volume | {config.system_volume_L:.1f} L | +30% overhead |",
            f"| System energy density | {config.system_energy_density_Wh_per_kg:.1f} Wh/kg | **Real-world spec** |",
            f"| Cost/kWh (cells) | ${config.cost_per_kWh:.2f}/kWh | Cell-level only |",
            "",
            "## Industry Benchmark Comparison",
            "",
            f"**System Energy Density**: {config.system_energy_density_Wh_per_kg:.1f} Wh/kg",
            f"- Typical EV pack: 120-185 Wh/kg",
            f"- Your pack: {'✓ Competitive' if 120 <= config.system_energy_density_Wh_per_kg <= 185 else '⚠ Outside typical range'} ",
            "",
            f"**Cost/kWh**: ${config.cost_per_kWh:.2f}",
            f"- LFP market: $80-100/kWh",
            f"- NMC market: $100-130/kWh",
            f"- NCA market: $130-150/kWh",
            "",
            "## Topology Explanation",
            "",
            "- **Series (96S)**: Cells connected positive-to-negative to stack voltage",
            "  - Pack voltage = 96 × 3.2V = 307.2V (for LFP nominal 3.2V)",
            "  - Each series string handles full pack current",
            "",
            "- **Parallel (13P)**: Series strings connected in parallel to scale capacity",
            "  - Pack capacity = 13 × 5Ah = 65Ah",
            "  - Each parallel branch can handle 1/13th of total current",
            "",
            "- **Why this topology?**",
            "  - Voltage constraint: Inverter (300-400V nominal) must convert DC to 3-phase AC",
            "  - Capacity constraint: Target 60 kWh energy determined by vehicle range",
            "  - Redundancy: If one parallel branch fails, pack continues at reduced capacity",
        ]
        
        # Record in session
        duration = time.time() - start_time
        self.session.record_investigation(
            investigation_type='pack_sizing',
            parameters={
                'preset': preset_name,
                'target_energy_kWh': target_energy_kWh,
                'voltage_range': voltage_range,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"{config.n_series}S × {config.n_parallel}P configuration",
                f"System weight: {config.system_weight_kg:.1f} kg",
                f"Energy density: {config.system_energy_density_Wh_per_kg:.1f} Wh/kg",
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                f"Pack uses {config.total_cells:,} cells in {config.n_series}S × {config.n_parallel}P topology",
                f"System-level energy density {config.system_energy_density_Wh_per_kg:.1f} Wh/kg is realistic for EV packs",
                f"Total system weight {config.system_weight_kg:.1f} kg includes 20% overhead for BMS/thermal/housing",
            ],
        )

    @agent_tool(
        description="Rank cell chemistries against application requirements (interactive wizard)",
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
        """
        Interactive cell selection wizard: rank presets against application requirements.
        
        TEACHING: When designing an EV, engineers must choose a cell chemistry.
        Each chemistry has different tradeoffs:
        - LFP: safe, long-lived, cheaper, but lower energy density
        - NMC: high energy density, higher cost, shorter life
        - NCA: very high energy density, most expensive, premium performance
        
        This tool scores each preset 0-100 across multiple dimensions and recommends
        the best options for the given application.
        
        Args:
            range_km: Target vehicle range in km (e.g., 400)
            power_kW: Peak power requirement in kW (e.g., 150)
            weight_budget_kg: Maximum pack weight in kg (e.g., 500)
            lifetime_years: Required warranty period in years (e.g., 8)
            volume_budget_L: Maximum pack volume in liters (optional)
            cost_budget_usd: Maximum pack cost in USD (optional)
            charge_time_min: Target 10-80% charge time in minutes (optional, for fast charging)
        
        Returns:
            DualFormatResult with ranked cell recommendations and comparison
        """
        
        start_time = time.time()
        
        # Build requirements dict
        requirements = {
            'range_km': range_km,
            'power_kW': power_kW,
            'weight_budget_kg': weight_budget_kg,
            'lifetime_years': lifetime_years,
        }
        
        if volume_budget_L is not None:
            requirements['volume_budget_L'] = volume_budget_L
        else:
            requirements['volume_budget_L'] = float('inf')
        
        if cost_budget_usd is not None:
            requirements['cost_budget_usd'] = cost_budget_usd
        else:
            requirements['cost_budget_usd'] = float('inf')
        
        if charge_time_min is not None:
            requirements['charge_time_min'] = charge_time_min
        
        # Get all presets
        all_presets = [CellPresets.get(name) for name in CellPresets.list_all()]
        
        # Score presets
        scored_results = CellSelectionScorer.score(requirements, all_presets)
        
        # Separate into "meets requirements" and "fails" groups
        meeting = [r for r in scored_results if r.meets_requirements]
        failing = [r for r in scored_results if not r.meets_requirements]
        
        # JSON output
        json_data = {
            'type': 'cell_selection',
            'requirements': {
                'range_km': range_km,
                'power_kW': power_kW,
                'weight_budget_kg': weight_budget_kg,
                'lifetime_years': lifetime_years,
                'volume_budget_L': volume_budget_L or 'unlimited',
                'cost_budget_usd': cost_budget_usd or 'unlimited',
                'charge_time_min': charge_time_min or 'no_constraint',
            },
            'rankings': [
                {
                    'rank': i + 1,
                    'preset_name': r.preset_name,
                    'chemistry': r.chemistry,
                    'total_score': round(r.total_score, 1),
                    'scores': {
                        'energy': round(r.energy_score, 1),
                        'power': round(r.power_score, 1),
                        'cost': round(r.cost_score, 1),
                        'lifetime': round(r.lifetime_score, 1),
                        'charge': round(r.charge_score, 1),
                    },
                    'meets_requirements': r.meets_requirements,
                    'recommendation': r.recommendation,
                    'pack_config': {
                        'n_series': r.pack_config.n_series,
                        'n_parallel': r.pack_config.n_parallel,
                        'system_weight_kg': round(r.pack_config.system_weight_kg, 1),
                        'system_volume_L': round(r.pack_config.system_volume_L, 1),
                        'system_energy_density_Wh_per_kg': round(r.pack_config.system_energy_density_Wh_per_kg, 1),
                        'cost_per_kWh': round(r.pack_config.cost_per_kWh, 2),
                    }
                }
                for i, r in enumerate(scored_results)
            ],
        }
        
        # Markdown output
        md_lines = [
            "# Cell Selection Wizard",
            "",
            "## Application Requirements",
            "",
            "| Requirement | Value |",
            "|-------------|-------|",
            f"| Target range | {range_km} km |",
            f"| Peak power | {power_kW} kW |",
            f"| Weight budget | {weight_budget_kg} kg |",
            f"| Warranty period | {lifetime_years} years |",
        ]
        
        if volume_budget_L is not None:
            md_lines.extend([
                f"| Volume budget | {volume_budget_L} L |",
            ])
        
        if cost_budget_usd is not None:
            md_lines.extend([
                f"| Cost budget | ${cost_budget_usd:,.0f} |",
            ])
        
        if charge_time_min is not None:
            md_lines.extend([
                f"| 10-80% charge time | {charge_time_min} min |",
            ])
        
        md_lines.extend([
            "",
            "## Rankings",
            "",
            "| Rank | Chemistry | Score | Energy | Power | Cost | Lifetime | Charge | Status |",
            "|------|-----------|-------|--------|-------|------|----------|--------|--------|",
        ])
        
        for i, r in enumerate(scored_results):
            status = "✓ Meets" if r.meets_requirements else "✗ Fails"
            md_lines.append(
                f"| {i+1} | {r.chemistry} {r.preset_name.split('_')[1]} | **{r.total_score:.0f}** | "
                f"{r.energy_score:.0f} | {r.power_score:.0f} | {r.cost_score:.0f} | {r.lifetime_score:.0f} | "
                f"{r.charge_score:.0f} | {status} |"
            )
        
        md_lines.extend([
            "",
            "## Recommendations",
            "",
        ])
        
        if meeting:
            md_lines.extend([
                "### ✓ Cells That Meet Requirements",
                "",
            ])
            for i, r in enumerate(meeting[:3]):  # Show top 3
                md_lines.extend([
                    f"**#{i+1}: {r.preset_name}**",
                    f"- {r.recommendation}",
                    f"- Total score: {r.total_score:.0f}/100",
                    f"- Configuration: {r.pack_config.n_series}S × {r.pack_config.n_parallel}P ({r.pack_config.total_cells:,} cells)",
                    f"- System weight: {r.pack_config.system_weight_kg:.0f} kg (budget: {weight_budget_kg} kg)",
                    f"- Energy density: {r.pack_config.system_energy_density_Wh_per_kg:.0f} Wh/kg",
                    f"- Cost/kWh: ${r.pack_config.cost_per_kWh:.2f}",
                    "",
                ])
        
        if failing:
            md_lines.extend([
                "### ✗ Cells That Fail Requirements",
                "",
            ])
            for r in failing[:3]:  # Show top 3 failures
                md_lines.extend([
                    f"**{r.preset_name}**: {r.recommendation}",
                ])
        
        # Executive summary
        best_cell = scored_results[0] if scored_results else None
        md_lines.extend([
            "",
            "## Executive Summary",
            "",
        ])
        
        if best_cell and best_cell.meets_requirements:
            md_lines.extend([
                f"✓ **Recommendation**: {best_cell.preset_name} is the best fit for this application.",
                f"- All requirements are met",
                f"- Strongest in: {', '.join([f for f, s in [('energy', best_cell.energy_score), ('power', best_cell.power_score), ('cost', best_cell.cost_score), ('lifetime', best_cell.lifetime_score), ('charge speed', best_cell.charge_score)] if s >= 70])}",
            ])
        elif meeting:
            md_lines.extend([
                f"✓ **Recommendation**: {meeting[0].preset_name} is the best option that meets your hard constraints.",
                f"- {len(meeting)} chemistry/capacity combinations meet requirements",
                f"- Consider {meeting[0].preset_name} for balanced tradeoffs",
            ])
        else:
            md_lines.extend([
                f"✗ **Issue**: No cell chemistry fully meets all hard constraints.",
                f"- Most promising: {best_cell.preset_name} ({best_cell.recommendation})",
                f"- Consider relaxing one constraint (e.g., cost or weight budget)",
            ])
        
        # Record in session
        duration = time.time() - start_time
        self.session.record_investigation(
            investigation_type='cell_selection_wizard',
            parameters=requirements,
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Best option: {best_cell.preset_name}" if best_cell else "No best option",
                f"Meeting requirements: {len(meeting)} option(s)" if meeting else "No options meet requirements",
                f"Top scorer: {scored_results[0].preset_name if scored_results else 'N/A'} ({scored_results[0].total_score:.0f}/100)" if scored_results else "N/A",
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                f"No single 'best' cell exists - optimize for your priority (energy, power, cost, or lifetime)",
                f"LFP batteries prioritize lifetime and safety; NMC/NCA prioritize energy density",
                f"Weight and volume constraints favor high energy density chemistries",
                f"Cost constraints favor LFP (cheaper) over NCA (premium)",
            ],
        )

    @agent_tool(
        description="Evaluate if a battery cell meets warranty requirements",
        examples=[
            "Check LFP_5AH warranty compliance for 8 years / 160k km / 80% SOH",
            "Warranty analysis for NMC_5AH at 35°C with aggressive usage",
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
        """
        Evaluate if a cell meets warranty requirements.

        TEACHING: Warranty analysis is a practical tool for EV engineers.
        Given typical warranty specs (8 years / 160k km / 80% SOH), determine:
        - Will this cell pass at end-of-warranty?
        - What's the safety margin?
        - Is it low/moderate/high risk?

        Args:
            preset_name: Cell chemistry preset name
            warranty_years: Warranty duration in years (default 8)
            warranty_km: Warranty distance in km (default 160,000)
            warranty_soh_threshold: SOH threshold (default 0.80 = 80%)
            usage_profile: dict with daily_charge_cycles, daily_km, storage_temperature_C, etc.
                          If None, uses UsageProfile defaults
            temperature_C: Operating temperature for lifetime prediction (°C)

        Returns:
            DualFormatResult with pass/fail, margin, risk level, recommendations
        """
        import numpy as np
        
        start_time = time.time()

        # Normalize usage profile
        usage = UsageProfile(**usage_profile) if usage_profile else UsageProfile()

        # Call predict_lifetime internally to get capacity trajectory
        # Use moderate cycle count for speed (10 cycles is enough for extrapolation)
        lt_result = self.predict_lifetime(
            preset_name=preset_name,
            usage_profile=None,  # Will use defaults internally
            n_representative_cycles=10,
            temperature_C=temperature_C,
        )

        # Check if lifetime prediction succeeded
        if lt_result.json_data.get("type") == "lifetime_prediction_error":
            return DualFormatResult(
                json_data={
                    'type': 'warranty_analysis_error',
                    'error': 'Could not predict lifetime',
                },
                markdown_text="Error: Unable to perform warranty analysis due to lifetime prediction failure.",
                interpretation_hints=[],
            )

        lt_data = lt_result.json_data

        # Extract capacity trajectory
        trajectory = lt_data.get("capacity_trajectory", [])
        if not trajectory:
            return DualFormatResult(
                json_data={
                    'type': 'warranty_analysis_error',
                    'error': 'No capacity trajectory available',
                },
                markdown_text="Error: Unable to extract capacity trajectory.",
                interpretation_hints=[],
            )

        # Build cycle -> capacity mapping for interpolation
        cycles_array = np.array([item["cycle"] for item in trajectory])
        retention_array = np.array([item["capacity_retention_pct"] / 100.0 for item in trajectory])

        # Calculate warranty cycles and km
        warranty_cycles = int(warranty_years * 365.25 * usage.daily_charge_cycles)
        warranty_km_actual = warranty_years * 365.25 * usage.daily_km

        # Interpolate SOH at warranty end
        if warranty_cycles <= cycles_array[-1]:
            # Within simulated range, interpolate
            predicted_soh_at_warranty = float(np.interp(warranty_cycles, cycles_array, retention_array))
        else:
            # Beyond simulated range, use linear extrapolation
            coeffs = np.polyfit(cycles_array, retention_array, 1)
            slope, intercept = coeffs
            predicted_soh_at_warranty = max(0.0, slope * warranty_cycles + intercept)

        # Determine pass/fail
        passes_warranty = predicted_soh_at_warranty >= warranty_soh_threshold

        # Calculate safety margin (%)
        if warranty_soh_threshold > 0:
            safety_margin_percent = (predicted_soh_at_warranty - warranty_soh_threshold) / warranty_soh_threshold * 100.0
        else:
            safety_margin_percent = 0.0

        # Risk assessment based on margin
        if safety_margin_percent > 20.0:
            risk_level = "Low Risk"
            risk_color = "🟢"
        elif safety_margin_percent > 10.0:
            risk_level = "Moderate Risk"
            risk_color = "🟡"
        elif safety_margin_percent > 0.0:
            risk_level = "High Risk"
            risk_color = "🟠"
        else:
            risk_level = "Critical"
            risk_color = "🔴"

        # Pass/fail badge
        if passes_warranty:
            status_badge = "✅ PASS"
            status_text = "Meets warranty requirements"
        else:
            status_badge = "❌ FAIL"
            status_text = "Does NOT meet warranty requirements"

        # Build JSON result
        json_data = {
            'type': 'warranty_analysis',
            'preset': preset_name,
            'temperature_C': temperature_C,
            'passes_warranty': passes_warranty,
            'status': status_text,
            'predicted_soh_at_warranty_end_pct': float(predicted_soh_at_warranty * 100.0),
            'warranty_soh_threshold_pct': float(warranty_soh_threshold * 100.0),
            'safety_margin_percent': float(safety_margin_percent),
            'risk_level': risk_level,
            'warranty_years': float(warranty_years),
            'warranty_km': float(warranty_km),
            'warranty_cycles': int(warranty_cycles),
            'warranty_km_actual': float(warranty_km_actual),
            'estimated_years_to_eol': lt_data.get('estimated_years_to_eol'),
            'estimated_cycles_to_eol': lt_data.get('estimated_cycles_to_eol'),
            'usage_profile': {
                'daily_km': usage.daily_km,
                'daily_charge_cycles': usage.daily_charge_cycles,
                'storage_temperature_C': usage.storage_temperature_C,
                'storage_soc': usage.storage_soc,
            },
        }

        # Build Markdown result
        md_lines = [
            f"# Warranty Analysis: {preset_name}",
            "",
            f"## {status_badge}",
            "",
            f"**Status**: {status_text}",
            f"**Operating Temperature**: {temperature_C}°C",
            "",
            "## Warranty Parameters",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Duration | {warranty_years:.1f} years |",
            f"| Distance | {warranty_km:,.0f} km ({warranty_km_actual:,.0f} km at usage) |",
            f"| Cycles | {warranty_cycles:,} cycles |",
            f"| SOH Threshold | {warranty_soh_threshold * 100:.0f}% |",
            "",
            "## Predicted Performance at Warranty End",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Predicted SOH** | {predicted_soh_at_warranty * 100:.1f}% |",
            f"| **Threshold** | {warranty_soh_threshold * 100:.0f}% |",
            f"| **Safety Margin** | {safety_margin_percent:+.1f}% |",
            f"| **Risk Level** | {risk_color} {risk_level} |",
            "",
            "## Lifetime Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Estimated EOL** | {lt_data.get('estimated_years_to_eol', 'N/A')} years ({lt_data.get('estimated_cycles_to_eol', 'N/A')} cycles) |",
            f"| **Warranty Coverage** | {(warranty_years / lt_data.get('estimated_years_to_eol', 1.0) if lt_data.get('estimated_years_to_eol') else 0) * 100:.0f}% of lifetime |",
            "",
            "## Usage Profile",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Daily Cycles | {usage.daily_charge_cycles} |",
            f"| Daily Distance | {usage.daily_km} km |",
            f"| Storage Temperature | {usage.storage_temperature_C}°C |",
            f"| Storage SOC | {usage.storage_soc * 100:.0f}% |",
        ]

        # Add risk assessment text
        md_lines.extend([
            "",
            "## Risk Assessment",
            "",
        ])

        if safety_margin_percent > 20.0:
            md_lines.extend([
                "**LOW RISK**: Cell has comfortable margin above threshold.",
                "- Suitable for conservative designs with minimal concern for degradation",
                "- Temperature/usage variations unlikely to cause failure",
            ])
        elif safety_margin_percent > 10.0:
            md_lines.extend([
                "**MODERATE RISK**: Cell meets requirements but with limited margin.",
                "- Design is safe, but thermal management and usage monitoring recommended",
                "- Temperature swings or aggressive cycling could impact warranty status",
            ])
        elif safety_margin_percent > 0.0:
            md_lines.extend([
                "**HIGH RISK**: Cell meets warranty by narrow margin.",
                "- Requires careful thermal control and usage optimization",
                "- Any degradation acceleration could lead to warranty failure",
                "- Consider next-generation cell or de-rating for critical applications",
            ])
        else:
            md_lines.extend([
                "**CRITICAL**: Cell does NOT meet warranty requirements under this profile.",
                "- Consider different chemistry (higher energy density → less cycling per year)",
                "- Reduce operating temperature (e.g., improved cooling)",
                "- Reduce cycle depth (shallow cycling reduces degradation rate)",
                "- Reconsider warranty targets or usage profile",
            ])

        duration_sec = time.time() - start_time

        self.session.record_investigation(
            investigation_type='warranty_analysis',
            parameters={
                'preset': preset_name,
                'warranty_years': warranty_years,
                'warranty_km': warranty_km,
                'warranty_soh_threshold': warranty_soh_threshold,
                'temperature_C': temperature_C,
                'usage_profile': usage_profile,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration_sec,
            key_findings=[
                f"Warranty Status: {status_text}",
                f"Predicted SOH: {predicted_soh_at_warranty * 100:.1f}% (Threshold: {warranty_soh_threshold * 100:.0f}%)",
                f"Safety Margin: {safety_margin_percent:+.1f}% ({risk_level})",
            ],
        )

        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Warranty analysis depends on consistent usage profile; real-world variations impact results",
                f"Temperature at {temperature_C}°C; higher temps accelerate aging significantly",
                "Review risk level and safety margin for design decisions",
            ],
        )

    @agent_tool(
        description="Find optimal CC-CV charging parameters balancing speed vs aging",
        examples=[
            "Optimize charging for LFP_5AH",
            "Find the best charge current to minimize degradation",
        ]
    )
    def optimize_charging(
        self,
        preset_name: str,
        charge_current_range_A: tuple[float, float] = (1.0, 10.0),
        n_sweep_points: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Find optimal charging parameters by sweeping charge current.
        
        TEACHING: This tool finds the best trade-off between fast charging
        and battery aging. It runs simulations at different charge rates and
        scores them based on: charge_time + capacity_fade.
        
        Args:
            preset_name: Cell chemistry preset (e.g., 'LFP_5AH', 'NMC_5AH')
            charge_current_range_A: (min, max) current range in Amperes
            n_sweep_points: Number of points to test in the range
            temperature_C: Ambient temperature in °C (default 25)
        
        Returns:
            DualFormatResult with optimization results and recommendation
        """
        
        start_time = time.time()
        
        # Get cell
        cell = Cell.preset(preset_name)
        
        # Determine max voltage based on chemistry
        max_voltage_mapping = {
            'LFP': 3.65,
            'NMC': 4.2,
            'NCA': 4.2,
            'LCO': 4.2,
        }
        max_voltage_V = max_voltage_mapping.get(cell.chemistry, 4.2)
        
        # Create optimizer and run
        optimizer = ChargingOptimizer(backend=self._backend)
        results = optimizer.optimize(
            cell=cell,
            charge_current_range_A=charge_current_range_A,
            n_points=n_sweep_points,
            max_voltage_V=max_voltage_V,
            temperature_C=temperature_C,
        )
        
        # Format as DualFormatResult
        json_results = [
            {
                'charge_current_A': res.charge_current_A,
                'charge_time_s': res.charge_time_s,
                'capacity_fade_per_cycle': res.capacity_fade_per_cycle,
                'score': res.score,
                'peak_voltage_V': res.peak_voltage_V,
                'efficiency': res.final_efficiency,
            }
            for res in results
        ]
        
        # Find best result
        best_result = results[0] if results else None
        
        json_data = {
            'type': 'charging_optimization',
            'preset': preset_name,
            'temperature_C': temperature_C,
            'optimal_params': {
                'charge_current_A': best_result.charge_current_A if best_result else None,
                'charge_time_min': (best_result.charge_time_s / 60.0) if best_result and best_result.charge_time_s else None,
                'capacity_fade_per_cycle': best_result.capacity_fade_per_cycle if best_result else None,
                'score': best_result.score if best_result else None,
            } if best_result else {},
            'all_results': json_results,
            'max_voltage_V': max_voltage_V,
        }
        
        # Generate markdown recommendation
        md_lines = [
            f"# Charging Optimization: {preset_name}",
            "",
            f"**Temperature**: {temperature_C}°C",
            f"**Chemistry**: {cell.chemistry}",
            f"**Max Voltage**: {max_voltage_V}V",
            "",
        ]
        
        if best_result:
            md_lines.extend([
                "## Optimal Parameters",
                "",
                f"- **Charge Current**: {best_result.charge_current_A:.2f} A",
                f"- **Estimated Charge Time**: {best_result.charge_time_s / 60:.1f} minutes" if best_result.charge_time_s else "- **Charge Time**: Unknown",
                f"- **Capacity Fade**: {best_result.capacity_fade_per_cycle:.3f}% per cycle" if best_result.capacity_fade_per_cycle else "- **Capacity Fade**: Unknown",
                f"- **Peak Voltage**: {best_result.peak_voltage_V:.2f}V" if best_result.peak_voltage_V else "",
                f"- **Efficiency**: {best_result.final_efficiency:.1f}%" if best_result.final_efficiency else "",
                ""
            ])
        
        md_lines.extend([
            "## Comparison Table",
            "",
            "| Current (A) | Charge Time (min) | Fade (%/cyc) | Score |",
            "|-------------|-------------------|-------------|-------|",
        ])
        
        for res in results:
            time_min = f"{res.charge_time_s / 60:.1f}" if res.charge_time_s else "—"
            fade_str = f"{res.capacity_fade_per_cycle:.3f}" if res.capacity_fade_per_cycle else "—"
            marker = " ⭐" if res == best_result else ""
            md_lines.append(
                f"| {res.charge_current_A:.2f} | {time_min} | {fade_str} | {res.score:.3f} |{marker}"
            )
        
        md_lines.extend([
            "",
            "## Trade-off Analysis",
            "",
            "- **Lower current** → slower charging, less degradation (better for longevity)",
            "- **Higher current** → faster charging, more degradation (better for convenience)",
            f"- **Optimal**: {best_result.charge_current_A:.2f}A balances both factors",
            "",
            "## Lithium Plating Risk",
            "",
            f"- Risk increases with charge current and low temperature",
            f"- Current study at {temperature_C}°C is relatively safe at tested range",
            f"- Monitor for plating at currents > {best_result.charge_current_A * 1.5:.1f}A" if best_result else "",
            "",
        ])
        
        duration = time.time() - start_time
        
        self.session.record_investigation(
            investigation_type='optimize_charging',
            parameters={
                'preset': preset_name,
                'current_range_A': charge_current_range_A,
                'temperature_C': temperature_C,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Optimal charge current: {best_result.charge_current_A:.2f}A" if best_result else None,
                f"Estimated charge time: {best_result.charge_time_s / 60:.1f} min" if best_result and best_result.charge_time_s else None,
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Lower score is better (combines time and aging)",
                "Consider operational requirements when choosing from the table",
                "Higher currents trade longevity for convenience",
                "Temperature affects aging rate significantly",
            ],
        )

    @agent_tool(
        description="Map the safe operating window for a cell across SOC, temperature, and C-rate"
    )
    def operating_window(
        self,
        preset_name: str,
        grid_size: str = "coarse",
    ) -> DualFormatResult:
        """
        Generate an operating window map for a battery cell.
        
        TEACHING: This tool evaluates a grid of operating conditions (SOC, Temperature, C-rate)
        and classifies each as safe/caution/avoid. The result is a map that BMS engineers
        use to configure power and current limits.
        
        Args:
            preset_name: Cell chemistry preset (e.g., 'LFP_5AH')
            grid_size: "coarse" (fast, 27 points) or "fine" (comprehensive, 125 points)
        
        Returns:
            DualFormatResult with operating window grid and summary statistics
        """
        
        start_time = time.time()
        
        # Get cell
        cell = Cell.preset(preset_name)
        
        # Create analyzer
        analyzer = OperatingWindowAnalyzer(backend=self._backend)
        
        # Run analysis
        result = analyzer.analyze(cell=cell, grid_size=grid_size)
        
        # Format as DualFormatResult
        grid_summary = result['summary']
        
        json_data = {
            'type': 'operating_window',
            'preset': preset_name,
            'grid_size': grid_size,
            'total_points': result['total_points'],
            'summary': {
                'safe_count': grid_summary.get('safe', 0),
                'caution_count': grid_summary.get('caution', 0),
                'avoid_count': grid_summary.get('avoid', 0),
                'percent_safe': round(grid_summary.get('percent_safe', 0), 1),
                'percent_caution': round(grid_summary.get('percent_caution', 0), 1),
                'percent_avoid': round(grid_summary.get('percent_avoid', 0), 1),
                'max_safe_crate': round(grid_summary.get('max_safe_crate', 0), 2),
                'safe_temperature_range_C': grid_summary.get('safe_temperature_range_C'),
            },
            'grid_points': [
                {
                    'soc_level': p.soc_level,
                    'temperature_C': p.temperature_C,
                    'c_rate': p.c_rate,
                    'zone': p.zone,
                    'voltage_min_V': round(p.voltage_min_V, 2) if p.voltage_min_V else None,
                    'voltage_max_V': round(p.voltage_max_V, 2) if p.voltage_max_V else None,
                    'temperature_rise_C': round(p.temperature_rise_C, 1) if p.temperature_rise_C else None,
                    'details': p.details,
                }
                for p in result['grid_points']
            ]
        }
        
        # Generate markdown report
        md_lines = [
            f"# Operating Window: {preset_name}",
            "",
            "## Summary",
            "",
            f"- **Safe Zones**: {grid_summary.get('safe', 0)} points ({grid_summary.get('percent_safe', 0):.1f}%)",
            f"- **Caution Zones**: {grid_summary.get('caution', 0)} points ({grid_summary.get('percent_caution', 0):.1f}%)",
            f"- **Avoid Zones**: {grid_summary.get('avoid', 0)} points ({grid_summary.get('percent_avoid', 0):.1f}%)",
            f"- **Maximum Safe C-rate**: {grid_summary.get('max_safe_crate', 0):.2f}C",
            f"- **Safe Temperature Range**: {grid_summary.get('safe_temperature_range_C', (None, None))[0]}–{grid_summary.get('safe_temperature_range_C', (None, None))[1]}°C",
            "",
            "## Zone Classifications",
            "",
            "| Zone | Meaning |",
            "|------|---------|",
            "| **SAFE** | Normal operation, minimal degradation risk |",
            "| **CAUTION** | Acceptable operation but increased aging; monitor |",
            "| **AVOID** | Unsafe; exceeds voltage or thermal limits |",
            "",
            "## Operating Points (sorted by C-rate)",
            "",
            "| SOC | Temp (°C) | C-rate | Zone | V-min | V-max | ΔT | Notes |",
            "|-----|----------|--------|------|-------|-------|-----|-------|",
        ]
        
        # Sort by C-rate for readability
        sorted_points = sorted(result['grid_points'], key=lambda p: (p.c_rate, p.temperature_C, p.soc_level))
        
        for p in sorted_points:
            zone_emoji = "✅" if p.zone == "safe" else "⚠️" if p.zone == "caution" else "❌"
            v_min = f"{p.voltage_min_V:.2f}" if p.voltage_min_V else "—"
            v_max = f"{p.voltage_max_V:.2f}" if p.voltage_max_V else "—"
            dt = f"{p.temperature_rise_C:.1f}" if p.temperature_rise_C else "—"
            md_lines.append(
                f"| {p.soc_level:.1f} | {p.temperature_C} | {p.c_rate:.1f} | {zone_emoji} {p.zone} | {v_min} | {v_max} | {dt} | {p.details[:30]} |"
            )
        
        md_lines.extend([
            "",
            "## Interpretation",
            "",
            "1. **Safe zones**: Safe for continuous operation; use for normal driving",
            "2. **Caution zones**: Temporary operation acceptable; reduced cycle life",
            "3. **Avoid zones**: Should never occur in production; indicates design issue",
            "",
        ])
        
        duration = time.time() - start_time
        
        self.session.record_investigation(
            investigation_type='operating_window',
            parameters={
                'preset': preset_name,
                'grid_size': grid_size,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Safe zones: {grid_summary.get('percent_safe', 0):.1f}%",
                f"Maximum safe C-rate: {grid_summary.get('max_safe_crate', 0):.2f}C",
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Safe zone is the region for normal operation",
                "Caution zones indicate parameter extremes; use sparingly",
                "Avoid zones should never occur in production",
                "Use derating_curves() to extract BMS lookup tables",
            ],
        )

    @agent_tool(
        description="Extract derating curves from operating window for BMS lookup tables"
    )
    def derating_curves(
        self,
        preset_name: str,
        grid_size: str = "coarse",
    ) -> DualFormatResult:
        """
        Generate derating curves suitable for BMS power limiting.
        
        TEACHING: Derating curves show the maximum power/current as a function of
        temperature and SOC. BMS systems use these as lookup tables to protect the battery.
        
        Args:
            preset_name: Cell chemistry preset
            grid_size: "coarse" (fast) or "fine" (comprehensive)
        
        Returns:
            DualFormatResult with two derating curves (vs temperature and vs SOC)
        """
        
        start_time = time.time()
        
        # Get cell
        cell = Cell.preset(preset_name)
        
        # Create analyzer
        analyzer = OperatingWindowAnalyzer(backend=self._backend)
        
        # Generate operating window
        analyzer.analyze(cell=cell, grid_size=grid_size)
        
        # Extract derating curves
        curves = analyzer.get_derating_curves()
        
        # Format JSON
        json_data = {
            'type': 'derating_curves',
            'preset': preset_name,
            'chemistry': cell.chemistry,
            'nominal_voltage_V': cell.nominal_voltage_V,
            'nominal_capacity_Ah': cell.nominal_capacity_Ah,
            'max_crate_vs_temperature': curves['max_crate_vs_temperature'],
            'max_crate_vs_soc': curves['max_crate_vs_soc'],
        }
        
        # Generate markdown
        md_lines = [
            f"# Derating Curves: {preset_name}",
            "",
            "## 1. Maximum C-rate vs Temperature (at SOC=50%)",
            "",
            "Temperature (°C) | Max C-rate | Power @ 5Ah (kW) |",
            "|----------|---------|----------|",
        ]
        
        for point in curves['max_crate_vs_temperature']:
            temp_c = point['temperature_C']
            max_crate = point['max_c_rate']
            # Assume 5Ah nominal capacity and nominal voltage for power calc
            nominal_v = cell.nominal_voltage_V or 3.7
            power_kw = (max_crate * (cell.nominal_capacity_Ah or 5.0) * nominal_v) / 1000
            md_lines.append(
                f"| {temp_c:.0f} | {max_crate:.2f}C | {power_kw:.1f}kW |"
            )
        
        md_lines.extend([
            "",
            "## 2. Maximum C-rate vs SOC (at T=25°C)",
            "",
            "| SOC Level | Max C-rate | Power @ 5Ah (kW) |",
            "|----------|---------|----------|",
        ])
        
        for point in curves['max_crate_vs_soc']:
            soc = point['soc_level']
            max_crate = point['max_c_rate']
            nominal_v = cell.nominal_voltage_V or 3.7
            power_kw = (max_crate * (cell.nominal_capacity_Ah or 5.0) * nominal_v) / 1000
            md_lines.append(
                f"| {soc:.1f} (50%) | {max_crate:.2f}C | {power_kw:.1f}kW |"
            )
        
        md_lines.extend([
            "",
            "## Physical Interpretation",
            "",
            "### Temperature Derating",
            f"- **Cold operation (0°C)**: Battery has highest internal resistance",
            f"- **High current at low T**: Risk of lithium plating and cell damage",
            f"- **Solution**: BMS reduces max current at cold temperatures",
            "",
            "### SOC Derating",
            f"- **Low SOC (near cutoff)**: Voltage collapse risk at high current",
            f"- **High SOC (near full)**: Overvoltage risk at high current",
            f"- **Mid-SOC (50%)**: Voltage stability best; allows highest current",
            "",
            "## BMS Implementation",
            "",
            "These curves become BMS lookup tables:",
            "```",
            "max_current_A = lookup_table(temperature_C, soc_percent)",
            "```",
            "",
            "Real BMS systems interpolate between table points for smooth derating.",
            "",
        ])
        
        duration = time.time() - start_time
        
        self.session.record_investigation(
            investigation_type='derating_curves',
            parameters={
                'preset': preset_name,
                'grid_size': grid_size,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Temperature derating: {len(curves['max_crate_vs_temperature'])} points",
                f"SOC derating: {len(curves['max_crate_vs_soc'])} points",
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Derating curves define safe operating boundaries",
                "Temperature has strong effect on safe current limits",
                "Mid-SOC allows higher power extraction than extremes",
                "These tables are used directly in production BMS firmware",
            ],
        )

    @agent_tool(
        description="Estimate EV range for a cell preset with a given pack configuration and drive cycle",
        examples=[
            "How far can I go with a 96S4P NMC pack on a WLTP cycle?",
            "Estimate range for LFP_5AH with 150 kW peak power",
        ]
    )
    def estimate_range(
        self,
        preset_name: str,
        cycle_name: str = "WLTP",
        n_series: int = 96,
        n_parallel: int = 4,
        vehicle_mass_kg: float = 1800.0,
        peak_power_kW: float = 150.0,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Estimate EV range given a cell preset, pack configuration, and drive cycle.
        
        TEACHING: This tool bridges pack-level configuration with battery performance simulation.
        It answers: "With my chosen cells and pack topology, how far can I drive on one charge?"
        
        The method:
        1. Loads the cell preset and drive cycle profile
        2. Calculates pack voltage and capacity from series/parallel config
        3. Runs a simulation of one drive cycle to measure energy consumption
        4. Estimates how many cycles the pack can complete before cutoff
        5. Multiplies by the cycle distance to get range
        
        Args:
            preset_name: Cell chemistry preset (e.g., 'LFP_5AH', 'NMC_5AH')
            cycle_name: Drive cycle (WLTP, US06, UDDS)
            n_series: Number of cells in series (voltage configuration)
            n_parallel: Number of cell strings in parallel (capacity configuration)
            vehicle_mass_kg: Vehicle mass for cycle scaling (default 1800 kg)
            peak_power_kW: Peak power available for cycle scaling (default 150 kW)
            temperature_C: Operating temperature (default 25°C)
        
        Returns:
            DualFormatResult with estimated range and pack details
        """
        
        start_time = time.time()
        
        # Load cell and drive cycle
        cell = Cell.preset(preset_name)
        drive_profile = get_drive_cycle(cycle_name)
        
        # Calculate pack configuration
        # Note: Using simplified pack model - assumes individual cell voltage/capacity
        # scales linearly with series/parallel count
        pack_voltage_V = n_series * (cell.nominal_voltage_V or 3.2)
        pack_capacity_Ah = n_parallel * (cell.nominal_capacity_Ah or 5.0)
        pack_energy_kWh = (pack_voltage_V * pack_capacity_Ah) / 1000.0
        
        # Create drive cycle protocol at cell level
        # (We'll simulate one full cycle and measure energy consumption)
        protocol = Protocol.drive_cycle(
            cycle_name,
            vehicle_mass_kg=vehicle_mass_kg,
            peak_power_kW=peak_power_kW,
        )
        
        # Run simulation for one cycle
        environment = Environment(temperature_C=temperature_C)
        simulation = Simulation(
            cell=cell,
            model=self.default_model,
            protocol=protocol,
            environment=environment,
            solver_config=self.default_solver_config,
        )
        
        execution_service = SimulationExecutionService(backend=self._backend)
        run = execution_service.execute(simulation)
        
        # Extract energy consumed in the cycle
        # Energy signal is stored in result data
        energy_consumed_Wh = 0.0
        if run.result and hasattr(run.result, '_data'):
            energy_signal = run.result._data.get(Signal.ENERGY)
            if energy_signal is not None:
                # Energy is cumulative, so use the final value
                energy_values = energy_signal.values
                if energy_values:
                    energy_consumed_Wh = energy_values[-1]
        
        # Convert to kWh
        energy_consumed_kWh = energy_consumed_Wh / 1000.0
        
        # Estimate number of complete cycles possible
        if energy_consumed_kWh > 0:
            cycles_possible = pack_energy_kWh / energy_consumed_kWh
        else:
            cycles_possible = 0.0
        
        # Get cycle distance
        cycle_distance_km = DRIVE_CYCLE_DISTANCES_KM.get(cycle_name, 23.3)
        
        # Calculate estimated range
        range_km = cycles_possible * cycle_distance_km
        
        # Prepare JSON response
        json_data = {
            'type': 'range_estimation',
            'preset': preset_name,
            'cycle': cycle_name,
            'pack_configuration': {
                'n_series': n_series,
                'n_parallel': n_parallel,
                'pack_voltage_V': pack_voltage_V,
                'pack_capacity_Ah': pack_capacity_Ah,
            },
            'energy': {
                'pack_energy_kWh': round(pack_energy_kWh, 2),
                'energy_per_cycle_kWh': round(energy_consumed_kWh, 3),
            },
            'range': {
                'cycles_possible': round(cycles_possible, 2),
                'cycle_distance_km': cycle_distance_km,
                'estimated_range_km': round(range_km, 1),
            },
            'temperature_C': temperature_C,
        }
        
        # Prepare Markdown response
        md_lines = [
            f"# EV Range Estimation",
            "",
            f"**Cell Preset**: {preset_name}",
            f"**Drive Cycle**: {cycle_name} ({cycle_distance_km:.1f} km per cycle)",
            f"**Temperature**: {temperature_C}°C",
            "",
            "## Pack Configuration",
            "",
            f"- **Series cells (voltage stacking)**: {n_series}",
            f"- **Parallel strings (capacity)**: {n_parallel}",
            f"- **Pack voltage**: {pack_voltage_V:.1f} V",
            f"- **Pack capacity**: {pack_capacity_Ah:.1f} Ah",
            f"- **Pack energy**: **{pack_energy_kWh:.1f} kWh**",
            "",
            "## Energy Consumption",
            "",
            f"- **Energy per {cycle_name} cycle**: {energy_consumed_kWh:.3f} kWh",
            f"- **Cycles possible**: {cycles_possible:.1f}",
            "",
            "## Estimated Range",
            "",
            f"### **{range_km:.0f} km**",
            "",
            f"({cycles_possible:.1f} × {cycle_distance_km:.1f} km per cycle)",
            "",
            "### Assumptions",
            "",
            "- Pack energy is fully usable (no buffer reserve, no BMS limits)",
            "- Energy consumption scales linearly from single-cell simulation",
            "- No thermal effects on consumption (constant 25°C assumed)",
            "- Cycle repeats at constant power and vehicle mass",
            "",
            "### Notes",
            "",
            "- **Series/Parallel tradeoff**: Higher series → higher voltage (more efficient);",
            "  Higher parallel → higher current (lower losses but heavier)",
            "- **Real-world range**: Typically 15-20% lower due to BMS buffers, thermal losses, driving variation",
            "- **Temperature sensitivity**: Cold weather significantly reduces range (not modeled here)",
        ]
        
        duration = time.time() - start_time
        
        self.session.record_investigation(
            investigation_type='estimate_range',
            parameters={
                'preset': preset_name,
                'cycle': cycle_name,
                'n_series': n_series,
                'n_parallel': n_parallel,
                'vehicle_mass_kg': vehicle_mass_kg,
                'peak_power_kW': peak_power_kW,
                'temperature_C': temperature_C,
            },
            result_summary=json_data,
            result_markdown="\n".join(md_lines),
            duration_seconds=duration,
            key_findings=[
                f"Estimated range: {range_km:.0f} km",
                f"Pack energy: {pack_energy_kWh:.1f} kWh",
                f"Energy per cycle: {energy_consumed_kWh:.3f} kWh",
            ],
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text="\n".join(md_lines),
            interpretation_hints=[
                "Real-world range is typically 15-20% lower than this estimate",
                "Series count affects voltage window (inverter compatibility)",
                "Parallel count affects pack current rating and thermal load",
                "Cold temperature significantly reduces range (not modeled)",
                "Aggressive driving reduces range; eco-mode improves it",
            ],
        )

    # ========================================================================
    # CHARGING STRATEGIES
    # ========================================================================

    @agent_tool(
        description="Compare different charging strategies (CC-CV, multi-step, gentle) on the same cell"
    )
    def compare_charging_strategies(
        self,
        preset_name: str,
        strategies: Optional[List[str]] = None,
        n_cycles: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """
        Compare the performance of different charging strategies on a cell.
        
        TEACHING: Different charging protocols have different tradeoffs:
        - Fast (2C): Quick charge time but more aging
        - Standard (1C): Balanced approach
        - Gentle (0.5C): Slower but less stress
        - Multi-step: Reduces high-voltage stress by stepping down current
        - Pulse: Brief rest periods reduce lithium plating
        
        Args:
            preset_name: Cell chemistry preset (e.g., 'LFP_5AH')
            strategies: Specific strategies to compare, or None for all
            n_cycles: Number of charge-discharge cycles to simulate
            temperature_C: Ambient temperature in Celsius
        
        Returns:
            DualFormatResult with comparison table and recommendations
        """
        
        start_time = time.time()
        
        # Get cell
        cell = Cell.preset(preset_name)
        
        # Create evaluator
        evaluator = ChargingStrategyEvaluator(backend=self._backend)
        
        # Run comparison
        comparison = evaluator.compare(
            cell=cell,
            strategies=strategies,
            n_cycles=n_cycles,
            temperature_C=temperature_C,
        )
        
        # Format as JSON
        json_data = {
            'type': 'charging_strategy_comparison',
            'preset': preset_name,
            'chemistry': comparison.chemistry,
            'nominal_capacity_Ah': round(comparison.nominal_capacity_Ah, 2),
            'temperature_C': temperature_C,
            'n_cycles': n_cycles,
            'strategies': [
                {
                    'strategy_name': s.strategy_name,
                    'charge_time_min': round(s.charge_time_min, 1),
                    'discharge_time_min': round(s.discharge_time_min, 1),
                    'total_cycle_time_min': round(s.total_cycle_time_min, 1),
                    'charge_energy_Wh': round(s.charge_energy_Wh, 2),
                    'discharge_energy_Wh': round(s.discharge_energy_Wh, 2),
                    'energy_efficiency': round(s.energy_efficiency, 3),
                    'capacity_fade_per_cycle': round(s.capacity_fade_per_cycle, 2),
                    'final_soh': round(s.final_soh, 1),
                    'final_temperature_C': round(s.final_temperature_C, 1),
                    'notes': s.notes,
                }
                for s in comparison.strategies
            ],
        }
        
        # Find best strategy (balanced ranking)
        ranked = comparison.rank_balanced()
        if ranked:
            json_data['recommended_strategy'] = ranked[0].strategy_name
            json_data['reason'] = "Balanced score: fastest, efficient, and longest-lived"
        
        # Generate markdown report
        md_lines = [
            f"# Charging Strategy Comparison: {preset_name}",
            "",
            "## Overview",
            "",
            f"- **Chemistry**: {comparison.chemistry}",
            f"- **Nominal Capacity**: {comparison.nominal_capacity_Ah:.1f} Ah",
            f"- **Temperature**: {temperature_C}°C",
            f"- **Cycles Simulated**: {n_cycles}",
            "",
            "## Performance Comparison",
            "",
            "| Strategy | Charge Time (min) | Efficiency | Fade/Cycle (%) | Final SOH (%) | Temp (°C) |",
            "|----------|-------------------|-----------|-----------------|---------------|-----------|",
        ]
        
        for s in comparison.strategies:
            md_lines.append(
                f"| {s.strategy_name} | {s.charge_time_min:.1f} | {s.energy_efficiency:.2%} | "
                f"{s.capacity_fade_per_cycle:.2f} | {s.final_soh:.1f} | {s.final_temperature_C:.1f} |"
            )
        
        md_lines.extend([
            "",
            "## Rankings",
            "",
            "### Fastest Charging",
            "",
        ])
        
        for i, s in enumerate(comparison.rank_by_speed(), 1):
            md_lines.append(f"{i}. **{s.strategy_name}**: {s.charge_time_min:.1f} minutes")
        
        md_lines.extend([
            "",
            "### Best Energy Efficiency",
            "",
        ])
        
        for i, s in enumerate(comparison.rank_by_efficiency(), 1):
            md_lines.append(f"{i}. **{s.strategy_name}**: {s.energy_efficiency:.2%}")
        
        md_lines.extend([
            "",
            "### Best for Longevity (Lowest Fade)",
            "",
        ])
        
        for i, s in enumerate(comparison.rank_by_longevity(), 1):
            md_lines.append(f"{i}. **{s.strategy_name}**: {s.capacity_fade_per_cycle:.2f}% per cycle")
        
        md_lines.extend([
            "",
            "### Balanced Recommendation",
            "",
        ])
        
        ranked = comparison.rank_balanced()
        if ranked:
            md_lines.append(f"**Best Overall**: {ranked[0].strategy_name}")
            md_lines.append(
                f"- Charge time: {ranked[0].charge_time_min:.1f} min"
            )
            md_lines.append(
                f"- Energy efficiency: {ranked[0].energy_efficiency:.2%}"
            )
            md_lines.append(
                f"- Capacity fade: {ranked[0].capacity_fade_per_cycle:.2f}% per cycle"
            )

        strategy_notes = [
            (strategy.strategy_name, strategy.notes)
            for strategy in comparison.strategies
            if strategy.notes
        ]
        if strategy_notes:
            md_lines.extend([
                "",
                "## Notes",
                "",
            ])
            for strategy_name, note in strategy_notes:
                md_lines.append(f"- **{strategy_name}**: {note}")
        
        md_lines.extend([
            "",
            "## Strategy Descriptions",
            "",
            "### Standard 1C",
            "Constant current at 1C (rated capacity per hour) until reaching maximum voltage, then constant voltage until current tapers. This is the most common approach in production vehicles.",
            "",
            "### Fast 2C",
            "Aggressive charging at 2C enables rapid top-up but accelerates battery aging due to increased Joule heating and higher lithium-ion concentration gradients.",
            "",
            "### Gentle 0.5C",
            "Slow charging at 0.5C minimizes thermal stress and concentration gradients, resulting in the least aging but longest charge time.",
            "",
            "### Multi-Step CC",
            "Starts at 2C for quick initial charging, then steps down to 1.5C, 1C, and finally 0.5C. This reduces time at high voltage under high current, which is particularly damaging.",
            "",
            "### Pulse 0.5C",
            "Brief rest periods during charging (5 min charge, 30 sec rest) allow lithium plating to reverse and ion gradients to relax. Effective at reducing plating on cold days.",
            "",
        ])
        
        md_text = "\n".join(md_lines)
        
        # Record in session
        self.session.record_investigation(
            investigation_type="compare_charging_strategies",
            parameters={"preset": preset_name, "strategies": strategies, "n_cycles": n_cycles},
            result_summary={
                "total_strategies": len(comparison.strategies),
                "fastest_strategy": ranked[0].strategy_name if ranked else None,
                "lowest_fade_strategy": comparison.rank_by_longevity()[0].strategy_name,
            },
            result_markdown=md_text,
            duration_seconds=time.time() - start_time,
        )
        
        return DualFormatResult(
            json_data=json_data,
            markdown_text=md_text,
            interpretation_hints=[
                "Lower capacity_fade_per_cycle means longer battery life",
                "Higher energy_efficiency means less energy wasted as heat",
                "Balanced score weighs speed, efficiency, and longevity equally",
            ],
        )

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    def get_session_summary(self) -> str:
        """Get a summary of the current investigation session."""
        return self.session.generate_report()
    
    def save_session(self, filepath: str) -> None:
        """Save the current session to a file."""
        self.session.save_to_file(filepath)
    
    def get_reasoning_chain(self) -> str:
        """Get the reasoning chain from this investigation."""
        return self.session.get_reasoning_chain()
