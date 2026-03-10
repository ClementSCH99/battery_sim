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

from battery_sim.core.application_services import ComparisonService
from battery_sim.core.application_services import SensitivityService
from battery_sim.core.api_schema import APISchema
from battery_sim.core.investigation_tools import (
    BatchSimulationConfig,
    ConstraintChecker,
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
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig


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
    """
    Main API for LLM-driven battery simulation investigation.
    
    TEACHING: This is the control center. An LLM uses AgentAPI to:
    1. Learn what's possible (get_available_tools)
    2. Run investigations (compare_presets, etc.)
    3. Track progress (session)
    4. Save work (save_session)
    
    The API is stateful (maintains a session) so investigations build on each other.
    Investigation methods return DualFormatResult values built from canonical
    SimulationRun execution outputs.
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
        self.comparison_service = ComparisonService()
        self.sensitivity_service = SensitivityService()
    
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
        Compare multiple cell presets.
        
        TEACHING: This is a high-level tool. The LLM says what presets to compare.
        The API handles all the simulation details.
        
        Args:
            preset_names: List of preset names
            environment_temp_C: Ambient temperature around the cell (default 25°C)
        
        Returns:
            DualFormatResult with comparison
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
        )
        
        comparison = self.comparison_service.compare_presets(preset_names, config)
        
        # Format results
        formatted = ComparisonFormatter.format_comparison(
            preset_names,
            comparison['metrics']
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
