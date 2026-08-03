"""Public compatibility surface for SimulationSession."""

from battery_sim.application.session.facade import SimulationSession
from battery_sim.application.session.analyzer import SessionAnalyzer
from battery_sim.application.session.models import (
    InvestigationRun,
)

__all__ = [
    "InvestigationRun",
    "SessionAnalyzer",
    "SimulationSession",
]
