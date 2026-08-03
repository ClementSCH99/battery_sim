"""MCP ageing tools."""

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
def predict_lifetime(
    preset_name: str,
    usage_profile: dict | None = None,
    n_representative_cycles: int = 50,
    temperature_C: float = 25.0,
) -> str:
    """Experimentally extrapolate a short simulated aging trend; not test-validated."""
    _validate_preset(preset_name)
    _validate_usage_profile(usage_profile)
    if n_representative_cycles < 3:
        raise ValueError("n_representative_cycles must be >= 3 for exploratory fitting")
    _validate_temperature(temperature_C)
    result = api.predict_lifetime(
        preset_name=preset_name,
        usage_profile=usage_profile,
        n_representative_cycles=n_representative_cycles,
        temperature_C=temperature_C,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def warranty_analysis(
    preset_name: str,
    warranty_years: float = 8.0,
    warranty_km: float = 160000.0,
    warranty_soh_threshold: float = 0.80,
    usage_profile: dict | None = None,
    temperature_C: float = 25.0,
) -> str:
    """Screen a warranty target using an unvalidated linear aging extrapolation."""
    _validate_preset(preset_name)
    _validate_usage_profile(usage_profile)
    _validate_positive("warranty_years", warranty_years)
    _validate_positive("warranty_km", warranty_km)
    if not 0 < warranty_soh_threshold <= 1:
        raise ValueError("warranty_soh_threshold must be in (0, 1]")
    _validate_temperature(temperature_C)
    result = api.warranty_analysis(
        preset_name=preset_name,
        warranty_years=warranty_years,
        warranty_km=warranty_km,
        warranty_soh_threshold=warranty_soh_threshold,
        usage_profile=usage_profile,
        temperature_C=temperature_C,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def operating_window(
    preset_name: str,
    grid_size: str = "coarse",
) -> str:
    """Screen short cell-voltage pulses across SOC, temperature and C-rate.

    Labels are exploratory and are not a cell-safety qualification.
    """
    _validate_preset(preset_name)
    _validate_grid_size(grid_size)
    result = api.operating_window(
        preset_name=preset_name,
        grid_size=grid_size,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def derating_curves(
    preset_name: str,
    grid_size: str = "coarse",
) -> str:
    """Derive candidate cell-level derating samples from voltage-pulse screens.

    Outputs require test validation and are not production BMS lookup tables.
    """
    _validate_preset(preset_name)
    _validate_grid_size(grid_size)
    result = api.derating_curves(
        preset_name=preset_name,
        grid_size=grid_size,
    )
    return _result_json(result)

