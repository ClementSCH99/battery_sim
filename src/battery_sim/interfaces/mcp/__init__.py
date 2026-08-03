"""MCP adapter for battery_sim engineering tools."""

from battery_sim.interfaces.mcp.contract import api, mcp
from battery_sim.interfaces.mcp.core_tools import (
    describe_api,
    plan_experiment,
    compare_test_data,
    list_presets,
    run_simulation,
    compare_presets,
    sensitivity_analysis,
    check_feasibility,
)
from battery_sim.interfaces.mcp.decision_tools import (
    optimize_charging,
    pack_sizing,
    cell_selection_wizard,
    get_session_summary,
)
from battery_sim.interfaces.mcp.ageing_tools import (
    predict_lifetime,
    warranty_analysis,
    operating_window,
    derating_curves,
)
from battery_sim.interfaces.mcp.vehicle_tools import (
    estimate_range,
    compare_charging_strategies,
)

__all__ = [
    "api", "mcp",
    "describe_api",
    "plan_experiment",
    "compare_test_data",
    "list_presets",
    "run_simulation",
    "compare_presets",
    "sensitivity_analysis",
    "check_feasibility",
    "optimize_charging",
    "pack_sizing",
    "cell_selection_wizard",
    "get_session_summary",
    "predict_lifetime",
    "warranty_analysis",
    "operating_window",
    "derating_curves",
    "estimate_range",
    "compare_charging_strategies",
]
