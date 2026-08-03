"""Parameter definitions and searchable spaces."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
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
