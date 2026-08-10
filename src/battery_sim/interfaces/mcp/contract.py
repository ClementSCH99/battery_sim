"""MCP runtime, validation and response contract."""

import json
import math
import time
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
        "schema_version": "2.0",
        "maturity": maturity,
        "domain_of_validity": domain,
        "assumptions": _response_assumptions(tool_name, payload),
    }

def _failure_from_payload(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Normalize legacy domain failures without hiding their original fields."""
    error_value = payload.get("error")
    if error_value:
        return {
            "code": payload.get("error_code", "domain_error"),
            "type": payload.get("error_type", "DomainError"),
            "message": payload.get("message", str(error_value)),
            "retryable": bool(payload.get("retryable", False)),
        }
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and (
        metrics.get("status") == "failed"
        or int(metrics.get("critical_errors", 0) or 0) > 0
    ):
        messages = metrics.get("errors") or ["Simulation result failed validation"]
        return {
            "code": "result_validation_failed",
            "type": "ResultValidationError",
            "message": "; ".join(str(item) for item in messages),
            "retryable": False,
        }
    if str(payload.get("type", "")).endswith("_error"):
        return {
            "code": "domain_error",
            "type": "DomainError",
            "message": str(payload.get("message") or "Tool returned an error result"),
            "retryable": False,
        }
    return None

def _attach_response_envelope(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("tool", tool_name)
    payload.setdefault("maturity", _tool_maturity().get(tool_name, "experimental"))
    payload.setdefault("contract", _contract(tool_name, payload))
    failure = _failure_from_payload(payload)
    payload["ok"] = failure is None
    payload["response"] = {
        "schema_version": "2.0",
        "status": "success" if failure is None else "error",
        "error": failure,
        "warnings": payload.get("warnings", []),
        "diagnostics": payload.get("diagnostics", {}),
    }
    return payload

_SELF_RECORDING_TOOLS = {
    "run_simulation", "compare_test_data", "compare_presets",
    "sensitivity_analysis", "predict_lifetime", "pack_sizing",
    "cell_selection_wizard", "warranty_analysis", "optimize_charging",
    "operating_window", "derating_curves", "estimate_range",
    "compare_charging_strategies",
}

def _record_boundary_call(
    tool_name: str,
    parameters: dict[str, Any],
    payload: dict[str, Any],
    duration_s: float,
    history_start: int,
) -> None:
    if tool_name == "get_session_summary":
        return
    new_events = api.session.investigation_history[history_start:]
    if tool_name in _SELF_RECORDING_TOOLS:
        roots = [event for event in new_events if event.investigation_type == tool_name]
        if roots:
            root = roots[-1]
            root.status = payload.get("response", {}).get("status", "unknown")
            root.result_summary = payload
            for event in new_events:
                if event is not root and event.parent_event_id is None:
                    event.parent_event_id = root.event_id
            return
    api.session.record_investigation(
        investigation_type=tool_name,
        parameters=parameters,
        result_summary=payload,
        result_markdown=f"MCP call {tool_name}: {payload.get('response', {}).get('status', 'unknown')}",
        duration_seconds=duration_s,
        key_findings=[],
        status=payload.get("response", {}).get("status", "unknown"),
    )

def _tool_error_boundary(func: Callable[..., str]) -> Callable[..., str]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        started_at = time.perf_counter()
        history_start = api.session.num_investigations()
        parameter_names = func.__code__.co_varnames[:func.__code__.co_argcount]
        parameters = dict(zip(parameter_names, args))
        parameters.update(kwargs)
        try:
            raw_result = func(*args, **kwargs)
            try:
                payload = json.loads(raw_result)
            except (TypeError, json.JSONDecodeError):
                return raw_result
            if not isinstance(payload, dict):
                return raw_result
            payload = _attach_response_envelope(func.__name__, payload)
            _record_boundary_call(
                func.__name__, parameters, payload,
                time.perf_counter() - started_at, history_start,
            )
            return json.dumps(payload, indent=2, default=str)
        except Exception as exc:  # noqa: BLE001 - convert to MCP-safe error payload
            error_type = "ValidationError" if isinstance(exc, ValueError) else exc.__class__.__name__
            error_code = "validation_error" if isinstance(exc, ValueError) else "execution_error"
            payload = _attach_response_envelope(func.__name__, {
                "error": True,
                "error_type": error_type,
                "error_code": error_code,
                "message": str(exc),
                "tool": func.__name__,
                "maturity": _tool_maturity().get(func.__name__, "experimental"),
                "retryable": False,
                "contract": _contract(func.__name__),
            })
            _record_boundary_call(
                func.__name__, parameters, payload,
                time.perf_counter() - started_at, history_start,
            )
            return json.dumps(payload, indent=2, default=str)

    return wrapper

def _result_json(dual_format_result) -> str:
    """Serialize a DualFormatResult's json_data to a JSON string."""
    return json.dumps(dual_format_result.json_data, indent=2, default=str)

