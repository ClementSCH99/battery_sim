"""MCP server exposing battery_sim tools via Model Context Protocol."""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from battery_sim.core.agent_api import AgentAPI

mcp = FastMCP("battery-sim")
api = AgentAPI()


def _result_json(dual_format_result) -> str:
    """Serialize a DualFormatResult's json_data to a JSON string."""
    return json.dumps(dual_format_result.json_data, indent=2, default=str)


@mcp.tool()
def list_presets(chemistry: str | None = None) -> str:
    """List available cell chemistry presets. Optionally filter by chemistry (e.g. 'LFP', 'NMC')."""
    result = api.list_presets(chemistry=chemistry)
    return _result_json(result)


@mcp.tool()
def run_simulation(
    preset_name: str,
    current_A: float | None = None,
    duration_s: float | None = None,
    temperature_C: float = 25.0,
) -> str:
    """Run a single battery simulation and return performance metrics."""
    result = api.run_simulation(
        preset_name=preset_name,
        current_A=current_A,
        duration_s=duration_s,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
def compare_presets(
    preset_names: list[str],
    environment_temp_C: float | None = None,
) -> str:
    """Compare multiple cell chemistry presets side-by-side."""
    result = api.compare_presets(
        preset_names=preset_names,
        environment_temp_C=environment_temp_C,
    )
    return _result_json(result)


@mcp.tool()
def sensitivity_analysis(
    preset_name: str,
    parameters: list[str],
) -> str:
    """Analyze sensitivity of battery performance to parameter variations."""
    result = api.sensitivity_analysis(
        preset_name=preset_name,
        parameters=parameters,
    )
    return _result_json(result)


@mcp.tool()
def check_feasibility(
    preset_name: str,
    temperature_C: float = 25.0,
) -> str:
    """Check if a cell/environment combination is physically feasible."""
    result = api.check_feasibility(
        preset_name=preset_name,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
def get_session_summary() -> str:
    """Get a summary of the current investigation session."""
    return api.get_session_summary()


if __name__ == "__main__":
    mcp.run()
