"""
LAYER 1: API SCHEMA - Self-Documenting System Discovery

TEACHING FOCUS: Why introspection matters

WHY THIS LAYER EXISTS:
When an LLM (or a human) uses the API, they need to know:
1. What operations are available?
2. What parameters can I vary?
3. What ranges are valid?
4. What signals can I observe?
5. What presets are available?

Without this, the LLM has to guess or rely on external documentation.
WITH this, the API self-documents -  we call this "introspection."

KEY INSIGHT: If the API can't describe itself, the LLM can't reason about it effectively.

DESIGN PRINCIPLE: Every piece of metadata that the LLM might need is exposed
programmatically, not hidden in docstrings or markdown files.

---

EXAMPLE: The difference between good and bad introspection

BAD (forces LLM to guess):
    sim = Simulation(cell, model, protocol, environment, backend)
    result = sim.run()
    # What parameters could I vary? Unknown. What signals are available? Unclear.

GOOD (self-documenting):
    schema = APISchema()
    
    # What parameters CAN I vary?
    param_space = schema.get_parameter_space('cell')
    # Returns: {'nominal_capacity_Ah': {'min': 1.0, 'max': 50.0, ...}, ...}
    
    # What signals are available?
    signals = schema.get_signals()
    # Returns: [Signal(name='voltage_V', description='...', unit='V'), ...]
    
    # What presets exist?
    presets = schema.get_presets()
    # Returns: [Preset(name='LFP_5AH', chemistry='LFP', ...), ...]

The LLM can now reason about what's possible.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from enum import Enum
import json

from battery_sim.core.cell_presets import CellPresets, CellPreset


# ============================================================================
# PARAMETER SPACE: Describe what parameters exist and their valid ranges
# ============================================================================

@dataclass(frozen=True)
class ParameterDefinition:
    """
    Describes a single parameter that can be varied.
    
    TEACHING: This is metadata about a parameter, not the parameter itself.
    It tells you ABOUT the parameter (its range, type, meaning) without
    executing anything.
    
    Attributes:
        name: Parameter identifier (e.g., 'nominal_capacity_Ah')
        type: Python type hint ('float', 'int', 'str', etc.)
        unit: Measurement unit (e.g., 'Ah', 'V', '°C', 'Ω')
        description: What does this parameter control?
        min_value: Minimum valid value
        max_value: Maximum valid value
        default_value: Default if not specified
        is_tunable: Can this be varied in experiments?
        example_value: A typical good value
    """
    name: str
    type: str
    unit: str
    description: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_value: Optional[float] = None
    is_tunable: bool = True
    example_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dictionary."""
        return asdict(self)
    
    def is_valid(self, value: Any) -> bool:
        """
        Check if a value is within valid range.
        
        TEACHING: Validation is part of introspection. The schema doesn't just
        tell you what's valid—it can check for you.
        """
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True
    
    def validation_summary(self) -> str:
        """Human-readable validation info for the engineer."""
        if self.min_value is not None and self.max_value is not None:
            return f"Range: {self.min_value}{self.unit} to {self.max_value}{self.unit}"
        elif self.min_value is not None:
            return f"Minimum: {self.min_value}{self.unit}"
        elif self.max_value is not None:
            return f"Maximum: {self.max_value}{self.unit}"
        else:
            return "No range limits"


@dataclass(frozen=True)
class ParameterSpace:
    """
    Describes all parameters that can be varied in simulations.
    
    TEACHING: A ParameterSpace is like a map of the search space. It tells you
    "these are all the dials you can turn, here's how much each can turn."
    
    Organization:
    - Cell parameters: Properties of the battery cell
    - Environment parameters: External conditions (temperature, etc.)
    - Protocol parameters: Simulation conditions
    """
    cell_parameters: Dict[str, ParameterDefinition] = field(default_factory=dict)
    environment_parameters: Dict[str, ParameterDefinition] = field(default_factory=dict)
    protocol_parameters: Dict[str, ParameterDefinition] = field(default_factory=dict)
    
    def get_parameter(self, category: str, name: str) -> Optional[ParameterDefinition]:
        """Get a specific parameter definition."""
        params = {
            'cell': self.cell_parameters,
            'environment': self.environment_parameters,
            'protocol': self.protocol_parameters,
        }
        return params.get(category, {}).get(name)
    
    def list_parameters(self, category: str) -> List[ParameterDefinition]:
        """Get all parameters in a category."""
        params = {
            'cell': self.cell_parameters,
            'environment': self.environment_parameters,
            'protocol': self.protocol_parameters,
        }
        return list(params.get(category, {}).values())
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization."""
        return {
            'cell_parameters': {k: v.to_dict() for k, v in self.cell_parameters.items()},
            'environment_parameters': {k: v.to_dict() for k, v in self.environment_parameters.items()},
            'protocol_parameters': {k: v.to_dict() for k, v in self.protocol_parameters.items()},
        }
    
    def summary(self) -> str:
        """Human-readable summary of the parameter space."""
        lines = [
            "=" * 70,
            "PARAMETER SPACE",
            "=" * 70,
            "",
            "CELL PARAMETERS (properties of the battery cell):",
        ]
        for param_def in self.cell_parameters.values():
            lines.append(f"  • {param_def.name} ({param_def.unit})")
            lines.append(f"    {param_def.description}")
            lines.append(f"    {param_def.validation_summary()}")
            lines.append("")
        
        lines.append("ENVIRONMENT PARAMETERS (external conditions):")
        for param_def in self.environment_parameters.values():
            lines.append(f"  • {param_def.name} ({param_def.unit})")
            lines.append(f"    {param_def.description}")
            lines.append(f"    {param_def.validation_summary()}")
            lines.append("")
        
        lines.append("PROTOCOL PARAMETERS (simulation conditions):")
        for param_def in self.protocol_parameters.values():
            lines.append(f"  • {param_def.name} ({param_def.unit})")
            lines.append(f"    {param_def.description}")
            lines.append(f"    {param_def.validation_summary()}")
            lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# SIGNAL CATALOG: Describe available metrics
# ============================================================================

@dataclass(frozen=True)
class SignalDefinition:
    """
    Metadata about a signal (metric) available in results.
    
    TEACHING: Just like you wouldn't ask "what's my blood pressure?" without
    knowing what blood pressure IS, an LLM shouldn't ask for signals without
    knowing what they mean.
    
    Attributes:
        signal_name: The signal name (e.g., 'voltage')
        unit: Measurement unit (e.g., 'V')
        interpretation: What does this signal tell us?
        use_cases: Why would someone care about this?
        typical_range: What are typical values?
    """
    signal_name: str
    unit: str
    interpretation: str
    use_cases: List[str]
    typical_range: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization."""
        return {
            'name': self.signal_name,
            'unit': self.unit,
            'interpretation': self.interpretation,
            'use_cases': self.use_cases,
            'typical_range': self.typical_range,
        }


@dataclass(frozen=True)
class SignalCatalog:
    """
    Catalog of all signals available in simulation results.
    
    TEACHING: This is like a library catalog. You don't have to read every book
    to know what books exist. The catalog tells you what's available and what
    each contains.
    """
    signals: Dict[str, SignalDefinition] = field(default_factory=dict)
    
    def get_signal(self, name: str) -> Optional[SignalDefinition]:
        """Get metadata for a specific signal."""
        return self.signals.get(name)
    
    def list_signals(self) -> List[SignalDefinition]:
        """Get all available signals."""
        return list(self.signals.values())
    
    def by_use_case(self, use_case: str) -> List[SignalDefinition]:
        """Find signals relevant to a particular use case.
        
        TEACHING: This is a query on metadata. We're asking the API
        "which signals help me understand X?"
        """
        return [sig for sig in self.signals.values() if use_case in sig.use_cases]
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization."""
        return {
            'signals': {k: v.to_dict() for k, v in self.signals.items()}
        }
    
    def summary(self, use_case: Optional[str] = None) -> str:
        """Human-readable summary."""
        if use_case:
            signals = self.by_use_case(use_case)
            header = f"SIGNALS FOR: {use_case.upper()}"
        else:
            signals = self.list_signals()
            header = "ALL AVAILABLE SIGNALS"
        
        lines = [
            "=" * 70,
            header,
            "=" * 70,
            "",
        ]
        
        for sig_def in signals:
            lines.append(f"📊 {sig_def.signal.name} ({sig_def.signal.unit})")
            lines.append(f"   {sig_def.interpretation}")
            if sig_def.typical_range:
                lines.append(f"   Typical range: {sig_def.typical_range}")
            lines.append(f"   Use for: {', '.join(sig_def.use_cases)}")
            lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# PRESET CATALOG: Describe available chemistries
# ============================================================================

@dataclass(frozen=True)
class PresetCatalog:
    """
    Catalog of available cell presets.
    
    TEACHING: We don't want the LLM to start from zero every time. We want to
    say "here are some known-good starting points." The preset catalog makes
    this discoverable.
    """
    presets: Dict[str, CellPreset] = field(default_factory=dict)
    
    def get_preset(self, name: str) -> Optional[CellPreset]:
        """Get a specific preset."""
        return self.presets.get(name)
    
    def list_presets(self) -> List[CellPreset]:
        """Get all presets."""
        return list(self.presets.values())
    
    def by_chemistry(self, chemistry: str) -> Dict[str, CellPreset]:
        """Get all presets for a chemistry (e.g., 'LFP')."""
        return {
            name: preset for name, preset in self.presets.items()
            if preset.chemistry == chemistry
        }
    
    def list_chemistries(self) -> List[str]:
        """What chemistry families are represented?"""
        return sorted(set(p.chemistry for p in self.presets.values()))
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization."""
        return {
            'presets': {
                name: {
                    'name': preset.name,
                    'chemistry': preset.chemistry,
                    'description': preset.description,
                    'capacity_Ah': preset.cell.nominal_capacity_Ah,
                    'voltage_V': preset.cell.nominal_voltage_V,
                    'ir_Ohm': preset.cell.internal_resistance_Ohm,
                }
                for name, preset in self.presets.items()
            }
        }
    
    def summary(self, chemistry: Optional[str] = None) -> str:
        """Human-readable summary."""
        if chemistry:
            presets = self.by_chemistry(chemistry)
            header = f"PRESETS: {chemistry}"
        else:
            presets = {name: p for name, p in self.presets.items()}
            header = "ALL AVAILABLE PRESETS"
        
        lines = [
            "=" * 70,
            header,
            "=" * 70,
            "",
        ]
        
        for name, preset in sorted(presets.items()):
            lines.append(f"🔋 {name}")
            lines.append(f"   {preset.description}")
            lines.append(f"   Capacity: {preset.cell.nominal_capacity_Ah} Ah")
            lines.append(f"   Voltage: {preset.cell.nominal_voltage_V} V")
            lines.append(f"   IR: {preset.cell.internal_resistance_Ohm} Ω")
            lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# MAIN: API SCHEMA
# ============================================================================

class APISchema:
    """
    The main introspection API.
    
    TEACHING: This is the "control panel" for understanding what the API offers.
    Before running an experiment, you ask: "What can I do?"
    
    This class answers:
    1. APISchema().get_parameter_space() - What can I vary?
    2. APISchema().get_signals() - What can I measure?
    3. APISchema().get_presets() - What starting points are available?
    4. APISchema().get_tools() - What operations can I do?
    
    The LLM uses this to decide what's worth exploring.
    """
    
    def __init__(self):
        """Initialize with all metadata."""
        self._parameter_space = self._build_parameter_space()
        self._signal_catalog = self._build_signal_catalog()
        self._preset_catalog = self._build_preset_catalog()
    
    # ========================================================================
    # Parameter Space Construction
    # ========================================================================
    
    def _build_parameter_space(self) -> ParameterSpace:
        """
        TEACHING: This shows what you can vary in simulations.
        These ranges are based on what makes physical sense and what PyBaMM can handle.
        """
        
        # CELL PARAMETERS: Properties of the battery cell
        cell_params = {
            'nominal_capacity_Ah': ParameterDefinition(
                name='nominal_capacity_Ah',
                type='float',
                unit='Ah',
                description='Battery capacity in Ampere-hours. Affects energy and power.',
                min_value=0.5,
                max_value=100.0,
                default_value=5.0,
                example_value=5.0,
            ),
            'nominal_voltage_V': ParameterDefinition(
                name='nominal_voltage_V',
                type='float',
                unit='V',
                description='Nominal cell voltage. Affects power calculations.',
                min_value=2.5,
                max_value=4.5,
                default_value=3.7,
                example_value=3.7,
            ),
            'internal_resistance_Ohm': ParameterDefinition(
                name='internal_resistance_Ohm',
                type='float',
                unit='Ω',
                description='Internal resistance. Higher = more heat loss, lower peak power.',
                min_value=0.001,
                max_value=0.5,
                default_value=0.05,
                example_value=0.05,
            ),
            'chemistry': ParameterDefinition(
                name='chemistry',
                type='str',
                unit='',
                description='Battery chemistry family (LFP, NMC, NCA, LCO, LMNO). Affects characteristics.',
                is_tunable=False,  # Can't continuously vary chemistry; use presets instead
            ),
        }
        
        # ENVIRONMENT PARAMETERS: External conditions
        env_params = {
            'temperature_C': ParameterDefinition(
                name='temperature_C',
                type='float',
                unit='°C',
                description='Ambient temperature. Affects efficiency, voltage, and cycle life.',
                min_value=-20.0,
                max_value=60.0,
                default_value=25.0,
                example_value=25.0,
            ),
        }
        
        # PROTOCOL PARAMETERS: Simulation conditions
        # Note: These are less directly tunable via this API (defined in Protocol class),
        # but we list them for completeness
        protocol_params = {
            'discharge_current_A': ParameterDefinition(
                name='discharge_current_A',
                type='float',
                unit='A',
                description='Discharge current. Affects power output and efficiency.',
                min_value=0.1,
                max_value=100.0,
                default_value=5.0,
                example_value=5.0,
            ),
        }
        
        return ParameterSpace(
            cell_parameters=cell_params,
            environment_parameters=env_params,
            protocol_parameters=protocol_params,
        )
    
    def _build_signal_catalog(self) -> SignalCatalog:
        """Build catalog of available signals from B9 Result enrichment."""
        # TEACHING: These signals come from B9. We're just documenting them here.
        
        signals_data = {
            # Physical measurements
            'voltage_V': SignalDefinition(
                signal_name='voltage_V',
                unit='V',
                interpretation='Cell terminal voltage. Decreases as battery discharges.',
                use_cases=['safety_monitoring', 'efficiency_analysis', 'protocol_feasibility'],
                typical_range='2.5V - 4.2V for lithium cells',
            ),
            'current_A': SignalDefinition(
                signal_name='current_A',
                unit='A',
                interpretation='Discharge current (positive) or charge current (negative).',
                use_cases=['power_analysis', 'safety_monitoring', 'thermal_analysis'],
                typical_range='Positive during discharge, proportional to C-rate',
            ),
            'power_W': SignalDefinition(
                signal_name='power_W',
                unit='W',
                interpretation='Instantaneous power (voltage × current). Key for high-power apps.',
                use_cases=['peak_power_applications', 'efficiency_analysis', 'thermal_analysis'],
                typical_range='Depends on capacity and C-rate',
            ),
            'energy_Wh': SignalDefinition(
                signal_name='energy_Wh',
                unit='Wh',
                interpretation='Cumulative energy delivered. Integrated over time.',
                use_cases=['capacity_validation', 'efficiency_analysis', 'cycle_comparison'],
                typical_range='0 to nominal capacity (Ah) × nominal voltage (V)',
            ),
            
            # Efficiency metrics
            'charge_discharge_efficiency_percent': SignalDefinition(
                signal_name='charge_discharge_efficiency_percent',
                unit='%',
                interpretation='Round-trip efficiency: energy returned / energy stored.',
                use_cases=['battery_selection', 'system_design', 'cost_optimization'],
                typical_range='85% - 99% depending on chemistry',
            ),
            'round_trip_efficiency_percent': SignalDefinition(
                signal_name='round_trip_efficiency_percent',
                unit='%',
                interpretation='Same as charge_discharge_efficiency. For charge+discharge cycles.',
                use_cases=['cycle_analysis', 'long_term_performance'],
                typical_range='70% - 95% due to additional losses',
            ),
            
            # State variables
            'state_of_charge_percent': SignalDefinition(
                signal_name='state_of_charge_percent',
                unit='%',
                interpretation='Battery charge level (0% = empty, 100% = full).',
                use_cases=['bms_calibration', 'remaining_range_estimation', 'safety_limits'],
                typical_range='0% - 100%',
            ),
            'temperature_C': SignalDefinition(
                signal_name='temperature_C',
                unit='°C',
                interpretation='Cell temperature during operation. Increases with high currents.',
                use_cases=['thermal_analysis', 'safety_monitoring', 'cycle_life_prediction'],
                typical_range='20°C - 60°C typical for safe operation',
            ),
            
            # Resistance & losses
            'internal_resistance_Ohm': SignalDefinition(
                signal_name='internal_resistance_Ohm',
                unit='Ω',
                interpretation='Effective internal resistance. Increases with temperature.',
                use_cases=['model_degradation', 'cycle_prediction', 'aging_analysis'],
                typical_range='0.01Ω - 0.5Ω depending on chemistry',
            ),
            'ohmic_loss_W': SignalDefinition(
                signal_name='ohmic_loss_W',
                unit='W',
                interpretation='Power dissipated as heat due to internal resistance.',
                use_cases=['thermal_management', 'efficiency_analysis', 'power_budget'],
                typical_range='Proportional to I²R',
            ),
            'heat_generated_J': SignalDefinition(
                signal_name='heat_generated_J',
                unit='J',
                interpretation='Cumulative heat generated. Important for thermal design.',
                use_cases=['heat_management', 'cooling_requirements', 'safety_limits'],
                typical_range='Depends on discharge profile',
            ),
            
            # Peak metrics
            'peak_voltage_V': SignalDefinition(
                signal_name='peak_voltage_V',
                unit='V',
                interpretation='Maximum voltage reached during operation.',
                use_cases=['charger_design', 'electronics_protection', 'overcharge_detection'],
                typical_range='≤ 4.2V for lithium safety',
            ),
            'peak_current_A': SignalDefinition(
                signal_name='peak_current_A',
                unit='A',
                interpretation='Maximum current drawn. Important for power applications.',
                use_cases=['pack_design', 'connector_sizing', 'thermal_design'],
                typical_range='Depends on capacity and load profile',
            ),
            'peak_power_W': SignalDefinition(
                signal_name='peak_power_W',
                unit='W',
                interpretation='Maximum instantaneous power. Critical for high-power applications.',
                use_cases=['ev_design', 'power_tool_specs', 'fast_charging'],
                typical_range='10W - 10kW depending on chemistry',
            ),
        }
        
        return SignalCatalog(signals=signals_data)
    
    def _build_preset_catalog(self) -> PresetCatalog:
        """Build catalog of cell presets from B10."""
        # TEACHING: Get all presets that were defined in B10
        preset_dict = {}
        for preset_name in CellPresets.list_all():
            # Get the actual preset object from the class
            preset = CellPresets.get(preset_name)
            preset_dict[preset.name] = preset
        
        return PresetCatalog(presets=preset_dict)
    
    # ========================================================================
    # Public Query Methods
    # ========================================================================
    
    def get_parameter_space(self) -> ParameterSpace:
        """
        Returns: ParameterSpace describing what can be varied.
        
        LLM USE: "What parameters can I explore?"
        """
        return self._parameter_space
    
    def get_signals(self) -> SignalCatalog:
        """
        Returns: SignalCatalog with all available metrics.
        
        LLM USE: "What can I measure?"
        """
        return self._signal_catalog
    
    def get_presets(self) -> PresetCatalog:
        """
        Returns: PresetCatalog with available chemistries.
        
        LLM USE: "What starting points are available?"
        """
        return self._preset_catalog
    
    def get_tools(self) -> List[str]:
        """
        Returns: List of available operations/tools.
        
        LLM USE: "What can I DO?"
        
        This will be expanded in Layer 2 (Investigation Tools).
        """
        return [
            'compare_presets',           # Compare chemistries
            'sensitivity_analysis',      # How much does parameter X affect metric Y?
            'constraint_check',          # Is this scenario feasible?
            'parameter_explorer',        # Search parameter space guided
            'batch_simulator',           # Run many scenarios at once
        ]
    
    # ========================================================================
    # Convenience Methods for Common Queries
    # ========================================================================
    
    def describe_parameter(self, category: str, name: str) -> Optional[str]:
        """Get human-readable description of a parameter."""
        param = self._parameter_space.get_parameter(category, name)
        if not param:
            return None
        return f"{param.description} {param.validation_summary()}"
    
    def describe_signal(self, name: str) -> Optional[str]:
        """Get human-readable description of a signal."""
        sig = self._signal_catalog.get_signal(name)
        if not sig:
            return None
        return f"{sig.interpretation} (Typical: {sig.typical_range})"
    
    def describe_preset(self, name: str) -> Optional[str]:
        """Get human-readable description of a preset."""
        preset = self._preset_catalog.get_preset(name)
        if not preset:
            return None
        return preset.description
    
    # ========================================================================
    # Full Introspection Reports
    # ========================================================================
    
    def full_summary(self) -> str:
        """
        Complete self-description of the entire API.
        
        USE CASE: Engineer wants a complete reference document.
        """
        return "\n\n".join([
            self._parameter_space.summary(),
            self._preset_catalog.summary(),
            self._signal_catalog.summary(),
        ])
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Full JSON serialization for programmatic inspection.
        
        USE CASE: LLM wants machine-readable metadata.
        """
        return {
            'parameter_space': self._parameter_space.to_dict(),
            'signals': self._signal_catalog.to_dict(),
            'presets': self._preset_catalog.to_dict(),
            'tools': self.get_tools(),
        }
