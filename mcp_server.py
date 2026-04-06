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
def optimize_charging(
    preset_name: str,
    charge_current_min_A: float = 1.0,
    charge_current_max_A: float = 10.0,
    n_sweep_points: int = 5,
    temperature_C: float = 25.0,
) -> str:
    """Find optimal CC-CV charging parameters balancing speed vs aging.
    
    Sweeps through a range of charge currents to find the best trade-off
    between charging speed and battery degradation (capacity fade).
    """
    result = api.optimize_charging(
        preset_name=preset_name,
        charge_current_range_A=(charge_current_min_A, charge_current_max_A),
        n_sweep_points=n_sweep_points,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
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
    result = api.pack_sizing(
        preset_name=preset_name,
        target_energy_kWh=target_energy_kWh,
        voltage_range=(voltage_range_min_V, voltage_range_max_V),
    )
    return _result_json(result)


@mcp.tool()
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
def get_session_summary() -> str:
    """Get a summary of the current investigation session."""
    return api.get_session_summary()


@mcp.tool()
def predict_lifetime(
    preset_name: str,
    usage_profile: dict | None = None,
    n_representative_cycles: int = 50,
    temperature_C: float = 25.0,
) -> str:
    """Predict battery lifetime using degradation modeling and usage patterns."""
    result = api.predict_lifetime(
        preset_name=preset_name,
        usage_profile=usage_profile,
        n_representative_cycles=n_representative_cycles,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
def warranty_analysis(
    preset_name: str,
    warranty_years: float = 8.0,
    warranty_km: float = 160000.0,
    warranty_soh_threshold: float = 0.80,
    usage_profile: dict | None = None,
    temperature_C: float = 25.0,
) -> str:
    """Evaluate if a battery cell meets warranty requirements."""
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
def operating_window(
    preset_name: str,
    grid_size: str = "coarse",
) -> str:
    """Map the safe operating window across SOC, temperature, and C-rate.
    
    Evaluates a grid of operating conditions and classifies each as
    safe/caution/avoid, providing data for BMS power limiting strategies.
    """
    result = api.operating_window(
        preset_name=preset_name,
        grid_size=grid_size,
    )
    return _result_json(result)


@mcp.tool()
def derating_curves(
    preset_name: str,
    grid_size: str = "coarse",
) -> str:
    """Extract derating curves for BMS lookup tables.
    
    Generates maximum C-rate curves as functions of temperature and SOC,
    directly usable in production BMS firmware for power limiting.
    """
    result = api.derating_curves(
        preset_name=preset_name,
        grid_size=grid_size,
    )
    return _result_json(result)


@mcp.tool()
def estimate_range(
    preset_name: str,
    cycle_name: str = "WLTP",
    n_series: int = 96,
    n_parallel: int = 4,
    vehicle_mass_kg: float = 1800.0,
    peak_power_kW: float = 150.0,
    temperature_C: float = 25.0,
) -> str:
    """Estimate EV range for a given cell preset and pack configuration.
    
    Simulates one drive cycle with the specified pack configuration,
    measures energy consumption, and extrapolates to total range.
    
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
def compare_charging_strategies(
    preset_name: str,
    strategies: list[str] | None = None,
    n_cycles: int = 5,
    temperature_C: float = 25.0,
) -> str:
    """Compare different charging strategies on the same cell.
    
    Evaluates multiple charging approaches (standard CC-CV, fast, gentle, multi-step, pulse)
    through multiple charge-discharge cycles with degradation modeling.
    
    Args:
        preset_name: Cell chemistry preset (e.g., 'LFP_5AH', 'NMC_5AH')
        strategies: List of strategy names to compare, or None for all built-in strategies
        n_cycles: Number of cycles to simulate for each strategy (default 5)
        temperature_C: Ambient temperature (default 25°C)
    
    Returns:
        JSON string with comparison table, rankings, and recommendations
    """
    result = api.compare_charging_strategies(
        preset_name=preset_name,
        strategies=strategies,
        n_cycles=n_cycles,
        temperature_C=temperature_C,
    )
    return _result_json(result)


if __name__ == "__main__":
    mcp.run()
