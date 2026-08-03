"""Compatibility imports for the focused :mod:`battery_sim.core.services` package.

New code should import the service it needs from ``battery_sim.core.services``
or its named submodule. This module remains temporarily to avoid breaking
existing user code while the project architecture is reclaimed.
"""

from battery_sim.core.services import (
    BatchExecutionService,
    ComparisonService,
    CyclingAnalyzer,
    ParameterSweepService,
    SensitivityResult,
    SensitivityService,
    SimulationExecutionService,
)

__all__ = [
    "BatchExecutionService",
    "ComparisonService",
    "CyclingAnalyzer",
    "ParameterSweepService",
    "SensitivityResult",
    "SensitivityService",
    "SimulationExecutionService",
]
