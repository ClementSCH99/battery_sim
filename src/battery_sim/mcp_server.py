"""MCP server exposing battery_sim tools via Model Context Protocol."""

import json
import math
from dataclasses import fields
from functools import lru_cache, wraps
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP

from battery_sim.interfaces.python.agent_api import AgentAPI
from battery_sim.core.experiment import UsageProfile
from battery_sim.experimental.system.drive_cycles import list_drive_cycles

mcp = FastMCP("battery-sim")
api = AgentAPI()


def _validate_temperature(temperature_C: float) -> None:
    if not math.isfinite(temperature_C) or temperature_C < -40.0 or temperature_C > 100.0:
        raise ValueError("temperature_C must be between -40 and 100")


def _validate_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be > 0")


def _validate_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be >= 0")


def _validate_string_list(name: str, values: list[str]) -> None:
    if not values:
        raise ValueError(f"{name} must contain at least one entry")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} entries must be non-empty strings")


def _validate_trace_lengths(
    time_s: list[float],
    voltage_V: list[float],
    measured_current_A: list[float] | None,
) -> None:
    if len(time_s) < 2:
        raise ValueError("time_s must contain at least two samples")
    if len(time_s) > 2000:
        raise ValueError("test trace is limited to 2000 samples")
    if len(voltage_V) != len(time_s):
        raise ValueError("voltage_V and time_s must have the same length")
    if measured_current_A is not None and len(measured_current_A) != len(time_s):
        raise ValueError("measured_current_A and time_s must have the same length")


def _validate_grid_size(grid_size: str) -> None:
    if grid_size not in {"coarse", "fine"}:
        raise ValueError("grid_size must be one of: coarse, fine")


@lru_cache(maxsize=1)
def _available_preset_names() -> tuple[str, ...]:
    result = api.list_presets()
    presets = result.json_data.get("presets", [])
    names = sorted(
        str(p.get("name"))
        for p in presets
        if isinstance(p, dict) and p.get("name")
    )
    return tuple(names)


def _validate_preset(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("preset_name must be a non-empty string")
    available = _available_preset_names()
    if name not in available:
        available_str = ", ".join(available)
        raise ValueError(
            f"Unknown preset_name '{name}'. Available presets: {available_str}"
        )


def _validate_usage_profile(usage_profile: dict | None) -> None:
    if usage_profile is None:
        return
    if not isinstance(usage_profile, dict):
        raise ValueError("usage_profile must be a dictionary when provided")
    allowed_keys = {field.name for field in fields(UsageProfile)}
    unknown = sorted(str(k) for k in usage_profile.keys() if k not in allowed_keys)
    if unknown:
        allowed = ", ".join(sorted(allowed_keys))
        unknown_str = ", ".join(unknown)
        raise ValueError(
            f"usage_profile contains unsupported keys: {unknown_str}. Allowed keys: {allowed}"
        )


def _validate_cycle_name(cycle_name: str) -> None:
    if not isinstance(cycle_name, str) or not cycle_name.strip():
        raise ValueError("cycle_name must be a non-empty string")
    available = list_drive_cycles()
    normalized = cycle_name.upper()
    if normalized not in {name.upper() for name in available}:
        available_str = ", ".join(available)
        raise ValueError(
            f"cycle_name must be one of: {available_str}"
        )


@lru_cache(maxsize=1)
def _tool_maturity() -> dict[str, str]:
    """Derive MCP maturity from the executable AgentAPI catalog."""
    return {
        tool["name"]: tool["maturity"]
        for tool in api.get_available_tools()
    }


def _response_assumptions(
    tool_name: str,
    payload: Optional[dict[str, Any]] = None,
) -> list[Any]:
    """Return explicit assumptions without duplicating tool implementation logic."""
    assumptions: list[Any] = []
    declared = payload.get("assumptions") if payload else None
    if isinstance(declared, list):
        assumptions.extend(declared)
    elif declared:
        assumptions.append(declared)

    defaults = {
        "describe_api": "Tool availability and core maturity do not imply experimental validation.",
        "list_presets": "Preset catalog values are modelling inputs, not cell datasheet guarantees.",
        "get_session_summary": "The summary contains only operations recorded in the current in-memory session.",
        "check_feasibility": "Constraint screening is not a cell-safety or qualification assessment.",
    }
    default = defaults.get(tool_name)
    if default:
        assumptions.append(default)
    elif _tool_maturity().get(tool_name, "experimental") == "core":
        assumptions.extend(
            [
                "Cell-level results inherit the selected PyBaMM model and parameter-set assumptions.",
                "No pack-level electrical or thermal interactions are represented unless explicitly stated.",
            ]
        )
    else:
        assumptions.append(
            "This capability is exploratory screening and has not been validated as decision evidence."
        )
    return assumptions


def _contract(tool_name: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    maturity = _tool_maturity().get(tool_name, "experimental")
    evidence = payload.get("evidence") if payload else None
    scope = payload.get("scope") if payload else None
    if isinstance(evidence, dict):
        domain = evidence.get("validation_status") or evidence.get("status")
    elif isinstance(evidence, str):
        domain = evidence
    else:
        domain = None
    if not domain:
        domain = scope
    if not domain:
        domain = (
            "cell-level investigation; inspect assumptions and result diagnostics"
            if maturity == "core"
            else "exploratory screening only; not validated decision evidence"
        )
    return {
        "schema_version": "1.0",
        "maturity": maturity,
        "domain_of_validity": domain,
        "assumptions": _response_assumptions(tool_name, payload),
    }


def _tool_error_boundary(func: Callable[..., str]) -> Callable[..., str]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            raw_result = func(*args, **kwargs)
            try:
                payload = json.loads(raw_result)
            except (TypeError, json.JSONDecodeError):
                return raw_result
            if not isinstance(payload, dict):
                return raw_result
            payload.setdefault("tool", func.__name__)
            payload.setdefault("maturity", _tool_maturity().get(func.__name__, "experimental"))
            payload.setdefault("contract", _contract(func.__name__, payload))
            return json.dumps(payload, indent=2, default=str)
        except Exception as exc:  # noqa: BLE001 - convert to MCP-safe error payload
            error_type = "ValidationError" if isinstance(exc, ValueError) else exc.__class__.__name__
            error_code = "validation_error" if isinstance(exc, ValueError) else "execution_error"
            return json.dumps(
                {
                    "error": True,
                    "error_type": error_type,
                    "error_code": error_code,
                    "message": str(exc),
                    "tool": func.__name__,
                    "maturity": _tool_maturity().get(func.__name__, "experimental"),
                    "retryable": False,
                    "contract": _contract(func.__name__),
                },
                indent=2,
                default=str,
            )

    return wrapper


def _result_json(dual_format_result) -> str:
    """Serialize a DualFormatResult's json_data to a JSON string."""
    return json.dumps(dual_format_result.json_data, indent=2, default=str)


@mcp.tool()
@_tool_error_boundary
def describe_api() -> str:
    """Describe available battery_sim tools and the scientific vocabulary."""
    return _result_json(api.describe_api())


@mcp.tool()
@_tool_error_boundary
def plan_experiment(
    question: str,
    preset_name: str | None = None,
    investigation_type: str | None = None,
    model: str | None = None,
    temperature_C: float | None = None,
    requested_signals: list[str] | None = None,
) -> str:
    """Build a reviewable electrochemical experiment plan without running it."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if preset_name is not None:
        _validate_preset(preset_name)
    if temperature_C is not None:
        _validate_temperature(temperature_C)
    if requested_signals is not None:
        _validate_string_list("requested_signals", requested_signals)
    return _result_json(
        api.plan_experiment(
            question=question,
            preset_name=preset_name,
            investigation_type=investigation_type,
            model=model,
            temperature_C=temperature_C,
            requested_signals=requested_signals,
        )
    )


@mcp.tool()
@_tool_error_boundary
def compare_test_data(
    preset_name: str,
    source: str,
    time_s: list[float],
    voltage_V: list[float],
    applied_current_A: float,
    measured_current_A: list[float] | None = None,
    current_sign_convention: str = "discharge_positive",
    temperature_C: float = 25.0,
    test_id: str | None = None,
    voltage_rmse_limit_V: float | None = None,
) -> str:
    """Compare a CC-discharge simulation with a sourced cell-test trace."""
    _validate_preset(preset_name)
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must identify the origin of the test data")
    _validate_positive("applied_current_A", applied_current_A)
    _validate_temperature(temperature_C)
    _validate_trace_lengths(time_s, voltage_V, measured_current_A)
    if voltage_rmse_limit_V is not None:
        _validate_positive("voltage_rmse_limit_V", voltage_rmse_limit_V)
    return _result_json(
        api.compare_test_data(
            preset_name=preset_name,
            source=source,
            time_s=time_s,
            voltage_V=voltage_V,
            applied_current_A=applied_current_A,
            measured_current_A=measured_current_A,
            current_sign_convention=current_sign_convention,
            temperature_C=temperature_C,
            test_id=test_id,
            voltage_rmse_limit_V=voltage_rmse_limit_V,
        )
    )


@mcp.tool()
@_tool_error_boundary
def list_presets(chemistry: str | None = None) -> str:
    """List available cell chemistry presets. Optionally filter by chemistry (e.g. 'LFP', 'NMC')."""
    result = api.list_presets(chemistry=chemistry)
    return _result_json(result)


@mcp.tool()
@_tool_error_boundary
def run_simulation(
    preset_name: str,
    current_A: float | None = None,
    duration_s: float | None = None,
    temperature_C: float = 25.0,
) -> str:
    """Run a single battery simulation and return performance metrics."""
    _validate_preset(preset_name)
    _validate_temperature(temperature_C)
    if current_A is not None:
        _validate_non_negative("current_A magnitude", abs(current_A))
        if current_A == 0:
            raise ValueError("current_A must be non-zero when provided")
    if duration_s is not None:
        _validate_positive("duration_s", duration_s)
    result = api.run_simulation(
        preset_name=preset_name,
        current_A=current_A,
        duration_s=duration_s,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
@_tool_error_boundary
def compare_presets(
    preset_names: list[str],
    environment_temp_C: float | None = None,
) -> str:
    """Compare multiple cell chemistry presets side-by-side."""
    _validate_string_list("preset_names", preset_names)
    for preset_name in preset_names:
        _validate_preset(preset_name)
    if environment_temp_C is not None:
        _validate_temperature(environment_temp_C)
    result = api.compare_presets(
        preset_names=preset_names,
        environment_temp_C=environment_temp_C,
    )
    return _result_json(result)


@mcp.tool()
@_tool_error_boundary
def sensitivity_analysis(
    preset_name: str,
    parameters: list[str],
    temperature_C: float = 25.0,
) -> str:
    """Analyze sensitivity of battery performance to parameter variations."""
    _validate_preset(preset_name)
    _validate_string_list("parameters", parameters)
    _validate_temperature(temperature_C)
    result = api.sensitivity_analysis(
        preset_name=preset_name,
        parameters=parameters,
        temperature_C=temperature_C,
    )
    return _result_json(result)


@mcp.tool()
@_tool_error_boundary
def check_feasibility(
    preset_name: str,
    temperature_C: float = 25.0,
) -> str:
    """Check if a cell/environment combination is physically feasible."""
    _validate_preset(preset_name)
    _validate_temperature(temperature_C)
    result = api.check_feasibility(
        preset_name=preset_name,
        temperature_C=temperature_C,
    )
    return _result_json(result)


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


if __name__ == "__main__":
    mcp.run()
