"""MCP core tools."""

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

