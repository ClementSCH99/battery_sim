"""Self-documenting Python API schema."""

from battery_sim.interfaces.python.schema.api import APISchema
from battery_sim.interfaces.python.schema.catalogs import (
    PresetCatalog, SignalCatalog, SignalDefinition,
)
from battery_sim.interfaces.python.schema.parameters import (
    ParameterDefinition, ParameterSpace,
)

__all__ = [
    "APISchema", "ParameterDefinition", "ParameterSpace",
    "PresetCatalog", "SignalCatalog", "SignalDefinition",
]
