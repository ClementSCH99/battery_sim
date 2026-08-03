"""Result presenters for Python and MCP interfaces."""

from battery_sim.interfaces.presenters.result.comparison import ComparisonFormatter
from battery_sim.interfaces.presenters.result.executive import ExecutiveSummaryFormatter
from battery_sim.interfaces.presenters.result.model import DualFormatResult
from battery_sim.interfaces.presenters.result.sensitivity import (
    InsightExtractor, SensitivityFormatter,
)

__all__ = [
    "ComparisonFormatter", "DualFormatResult",
    "ExecutiveSummaryFormatter", "InsightExtractor",
    "SensitivityFormatter",
]
