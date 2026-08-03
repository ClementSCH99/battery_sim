"""MCP runtime, validation and response contract."""

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

