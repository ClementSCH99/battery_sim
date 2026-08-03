"""Public compatibility surface for ResultAnalyzer."""

from battery_sim.application.analysis.result.facade import ResultAnalyzer
from battery_sim.application.analysis.result.models import (
    CycleInfo,
)

__all__ = [
    "CycleInfo",
    "ResultAnalyzer",
]
