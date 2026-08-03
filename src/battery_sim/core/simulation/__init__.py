"""Canonical simulation request, port and execution evidence."""

from battery_sim.core.simulation.diagnostics import (
    ConvergenceDiagnostics,
    ConvergenceRate,
    DiagnosticsAnalyzer,
)
from battery_sim.core.simulation.error_detection import ErrorDetector
from battery_sim.core.simulation.errors import ErrorType, SimulationError
from battery_sim.core.simulation.metadata import SimulationMetadata
from battery_sim.core.simulation.ports import SimulationBackend
from battery_sim.core.simulation.request import Simulation
from battery_sim.core.simulation.run import SimulationRun, ensure_simulation_run

__all__ = [
    "ConvergenceDiagnostics",
    "ConvergenceRate",
    "DiagnosticsAnalyzer",
    "ErrorDetector",
    "ErrorType",
    "Simulation",
    "SimulationBackend",
    "SimulationError",
    "SimulationMetadata",
    "SimulationRun",
    "ensure_simulation_run",
]
