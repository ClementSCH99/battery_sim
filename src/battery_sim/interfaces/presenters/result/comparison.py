"""Comparison presenter assembled from focused behaviors."""

from battery_sim.interfaces.presenters.result.comparison_basic import ComparisonBasicMixin
from battery_sim.interfaces.presenters.result.comparison_ev import ComparisonEVMixin
from battery_sim.interfaces.presenters.result.comparison_helpers import ComparisonHelpersMixin

class ComparisonFormatter(
    ComparisonBasicMixin,
    ComparisonEVMixin,
    ComparisonHelpersMixin,
):
    """Format generic and EV-oriented comparison results."""
