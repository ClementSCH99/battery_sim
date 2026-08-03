"""Composition of the self-documenting API schema."""

from typing import Any, Dict, Optional

from battery_sim.core.cell import CellPresets
from battery_sim.core.result import Signal
from battery_sim.interfaces.python.schema.catalogs import (
    PresetCatalog, SignalCatalog, SignalDefinition,
)
from battery_sim.interfaces.python.schema.parameter_groups import _DERIVED_METRIC_METADATA
from battery_sim.interfaces.python.schema.parameters import (
    ParameterDefinition, ParameterSpace,
)
from battery_sim.interfaces.python.schema.signal_metadata import _SIGNAL_METADATA

class APISchema:
    """
    The main introspection API.
    
    TEACHING: This is the control panel for the scientific vocabulary used by
    the API. Executable tool discovery belongs to AgentAPI.
    
    This class answers:
    1. APISchema().get_parameter_space() - What can I vary?
    2. APISchema().get_signals() - What can I measure?
    3. APISchema().get_presets() - What starting points are available?
    Tool discovery is owned by AgentAPI.get_available_tools(), which derives
    its catalog from executable @agent_tool methods. This schema describes only
    the scientific vocabulary used by those tools.
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
                description='Ambient temperature around the cell. Canonical environment thermal input.',
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
        """Build catalog of signals by iterating over the canonical Signal enum.

        TEACHING: Instead of hand-maintaining a parallel list of signal
        definitions, we DERIVE the catalog from the Signal enum (Single Source
        of Truth).  The _SIGNAL_METADATA dict enriches each enum member with
        human-readable metadata.  Any enum member missing from the metadata
        dict is still included with sensible defaults — so adding a new signal
        to the enum automatically surfaces it in the schema.
        """
        import warnings

        signals_data: Dict[str, SignalDefinition] = {}

        for member in Signal:
            meta = _SIGNAL_METADATA.get(member)
            if meta is None:
                warnings.warn(
                    f"Signal.{member.name} has no entry in _SIGNAL_METADATA — "
                    f"using placeholder metadata. Please add it.",
                    stacklevel=2,
                )
                meta = {
                    "unit": "?",
                    "interpretation": member.name.replace("_", " ").title(),
                    "use_cases": [],
                }
            signals_data[member.value] = SignalDefinition(
                signal_name=member.value,
                unit=meta["unit"],
                interpretation=meta["interpretation"],
                use_cases=meta.get("use_cases", []),
                typical_range=meta.get("typical_range"),
                aliases=meta.get("aliases", []),
            )

        # Derived summary metrics not backed by a Signal enum member
        for key, meta in _DERIVED_METRIC_METADATA.items():
            signals_data[key] = SignalDefinition(
                signal_name=key,
                unit=meta["unit"],
                interpretation=meta["interpretation"],
                use_cases=meta.get("use_cases", []),
                typical_range=meta.get("typical_range"),
                aliases=meta.get("aliases", []),
            )

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
        """Get the signal catalog for data exposed on SimulationRun.result."""
        return self._signal_catalog
    
    def get_presets(self) -> PresetCatalog:
        """
        Returns: PresetCatalog with available chemistries.
        
        LLM USE: "What starting points are available?"
        """
        return self._preset_catalog
    
    # Tool discovery intentionally belongs to AgentAPI and is derived from
    # @agent_tool methods. APISchema only describes the scientific domain.

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
        }
