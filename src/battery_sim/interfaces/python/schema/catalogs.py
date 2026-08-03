"""Signal and preset catalogs exposed by the Python interface."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from battery_sim.core.cell import CellPreset
@dataclass
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
        aliases: Legacy or alternate names that resolve to the same canonical signal.
    """
    signal_name: str
    unit: str
    interpretation: str
    use_cases: List[str]
    typical_range: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization."""
        return {
            'name': self.signal_name,
            'unit': self.unit,
            'interpretation': self.interpretation,
            'use_cases': self.use_cases,
            'typical_range': self.typical_range,
            'aliases': self.aliases,
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
        signal = self.signals.get(name)
        if signal is not None:
            return signal

        for candidate in self.signals.values():
            if name in candidate.aliases:
                return candidate
        return None
    
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
            lines.append(f"{sig_def.signal_name} ({sig_def.unit})")
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
                    'nominal_voltage_V': preset.cell.nominal_voltage_V,
                    'internal_resistance_Ohm': preset.cell.internal_resistance_Ohm,
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
            lines.append(f"{name}")
            lines.append(f"   {preset.description}")
            lines.append(f"   Capacity: {preset.cell.nominal_capacity_Ah} Ah")
            lines.append(f"   Nominal voltage: {preset.cell.nominal_voltage_V} V")
            lines.append(f"   Internal resistance: {preset.cell.internal_resistance_Ohm} Ohm")
            lines.append("")
        
        return "\n".join(lines)
