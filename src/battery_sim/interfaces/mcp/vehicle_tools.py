"""MCP vehicle tools."""

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
def estimate_range(
    preset_name: str,
    cycle_name: str = "WLTP",
    n_series: int = 96,
    n_parallel: int = 40,
    vehicle_mass_kg: float = 1800.0,
    peak_power_kW: float = 150.0,
    temperature_C: float = 25.0,
) -> str:
    """Screen EV range for a cell preset and pack configuration.

    Integrates a synthetic normalized pack-power trace. This tool does not run
    an electrochemical simulation and is not a regulatory range prediction.
    
    Args:
        preset_name: Cell chemistry preset (e.g., 'LFP_5AH', 'NMC_5AH')
        cycle_name: Drive cycle ('WLTP', 'US06', 'UDDS')
        n_series: Number of cells in series (voltage stacking)
        n_parallel: Number of parallel strings (capacity scaling)
        vehicle_mass_kg: Vehicle mass for power profile scaling (default 1800 kg)
        peak_power_kW: Peak power available (default 150 kW)
        temperature_C: Operating temperature (default 25°C)
    
    Returns:
        JSON string with estimated range, pack config, and energy details
    """
    _validate_preset(preset_name)
    _validate_cycle_name(cycle_name)
    if n_series < 1:
        raise ValueError("n_series must be >= 1")
    if n_parallel < 1:
        raise ValueError("n_parallel must be >= 1")
    _validate_positive("vehicle_mass_kg", vehicle_mass_kg)
    _validate_positive("peak_power_kW", peak_power_kW)
    _validate_temperature(temperature_C)
    result = api.estimate_range(
        preset_name=preset_name,
        cycle_name=cycle_name,
        n_series=n_series,
        n_parallel=n_parallel,
        vehicle_mass_kg=vehicle_mass_kg,
        peak_power_kW=peak_power_kW,
        temperature_C=temperature_C,
    )
    return _result_json(result)

@mcp.tool()
@_tool_error_boundary
def compare_charging_strategies(
    preset_name: str,
    strategies: list[str] | None = None,
    n_cycles: int = 5,
    temperature_C: float = 25.0,
) -> str:
    """Experimentally compare charging protocols on the same cell.

    Failed simulations are excluded and missing aging evidence remains null.
    
    Args:
        preset_name: Cell chemistry preset (e.g., 'LFP_5AH', 'NMC_5AH')
        strategies: List of strategy names to compare, or None for all built-in strategies
        n_cycles: Number of cycles to simulate for each strategy (default 5)
        temperature_C: Ambient temperature (default 25°C)
    
    Returns:
        JSON string with comparison table, rankings, and recommendations
    """
    _validate_preset(preset_name)
    if strategies is not None:
        _validate_string_list("strategies", strategies)
    if n_cycles < 1:
        raise ValueError("n_cycles must be >= 1")
    _validate_temperature(temperature_C)
    result = api.compare_charging_strategies(
        preset_name=preset_name,
        strategies=strategies,
        n_cycles=n_cycles,
        temperature_C=temperature_C,
    )
    return _result_json(result)

