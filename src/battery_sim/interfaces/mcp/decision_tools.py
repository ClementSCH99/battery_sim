"""MCP decision tools."""

import json
from typing import Any, Optional

from battery_sim.interfaces.mcp.contract import (
    api, mcp, _result_json, _tool_error_boundary,
    _validate_cycle_name, _validate_grid_size, _validate_non_negative,
    _validate_positive, _validate_preset, _validate_string_list,
    _validate_temperature, _validate_trace_lengths,
    _validate_usage_profile,
)

@mcp.tool()
@_tool_error_boundary
def optimize_charging(
    preset_name: str,
    charge_current_min_A: float = 1.0,
    charge_current_max_A: float = 10.0,
    n_sweep_points: int = 5,
    temperature_C: float = 25.0,
) -> str:
    """Screen single-charge CC-CV duration over an admissible current grid.

    This experimental tool does not calculate aging, efficiency or plating.
    """
    _validate_preset(preset_name)
    _validate_positive("charge_current_min_A", charge_current_min_A)
    _validate_positive("charge_current_max_A", charge_current_max_A)
    if charge_current_min_A > charge_current_max_A:
        raise ValueError("charge_current_min_A must be <= charge_current_max_A")
    if n_sweep_points < 2:
        raise ValueError("n_sweep_points must be >= 2")
    _validate_temperature(temperature_C)
    result = api.optimize_charging(
        preset_name=preset_name,
        charge_current_range_A=(charge_current_min_A, charge_current_max_A),
        n_sweep_points=n_sweep_points,
        temperature_C=temperature_C,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def pack_sizing(
    preset_name: str,
    target_energy_kWh: float = 60.0,
    voltage_range_min_V: float = 300.0,
    voltage_range_max_V: float = 400.0,
) -> str:
    """Size a battery pack from cell preset and target energy.
    
    Computes series/parallel configuration, weight, volume, cost, and
    energy density for a pack built from a specific cell chemistry.
    """
    _validate_preset(preset_name)
    _validate_positive("target_energy_kWh", target_energy_kWh)
    _validate_positive("voltage_range_min_V", voltage_range_min_V)
    _validate_positive("voltage_range_max_V", voltage_range_max_V)
    if voltage_range_min_V >= voltage_range_max_V:
        raise ValueError("voltage_range_min_V must be < voltage_range_max_V")
    result = api.pack_sizing(
        preset_name=preset_name,
        target_energy_kWh=target_energy_kWh,
        voltage_range=(voltage_range_min_V, voltage_range_max_V),
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def cell_selection_wizard(
    range_km: float = 400.0,
    power_kW: float = 150.0,
    weight_budget_kg: float = 500.0,
    lifetime_years: float = 8.0,
    volume_budget_L: float | None = None,
    cost_budget_usd: float | None = None,
    charge_time_min: float | None = None,
) -> str:
    """Rank cell chemistries against application requirements (interactive wizard).
    
    Scores all available cell presets (LFP, NMC, NCA, etc.) across multiple
    dimensions: energy, power, cost, lifetime, and charging speed.
    Returns ranked recommendations with detailed pack configurations.
    """
    _validate_positive("range_km", range_km)
    _validate_positive("power_kW", power_kW)
    _validate_positive("weight_budget_kg", weight_budget_kg)
    _validate_positive("lifetime_years", lifetime_years)
    if volume_budget_L is not None:
        _validate_positive("volume_budget_L", volume_budget_L)
    if cost_budget_usd is not None:
        _validate_positive("cost_budget_usd", cost_budget_usd)
    if charge_time_min is not None:
        _validate_positive("charge_time_min", charge_time_min)
    result = api.cell_selection_wizard(
        range_km=range_km,
        power_kW=power_kW,
        weight_budget_kg=weight_budget_kg,
        lifetime_years=lifetime_years,
        volume_budget_L=volume_budget_L,
        cost_budget_usd=cost_budget_usd,
        charge_time_min=charge_time_min,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def get_session_summary() -> str:
    """Get a summary of the current investigation session."""
    return json.dumps(
        {
            "type": "session_summary",
            "summary": api.get_session_summary(),
        },
        indent=2,
    )

