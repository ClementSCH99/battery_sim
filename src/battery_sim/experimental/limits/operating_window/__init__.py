"""Public compatibility surface for OperatingWindowAnalyzer."""

from battery_sim.experimental.limits.operating_window.facade import OperatingWindowAnalyzer
from battery_sim.experimental.limits.operating_window.models import (
    OperatingWindowPoint,
)

__all__ = [
    "OperatingWindowAnalyzer",
    "OperatingWindowPoint",
]
