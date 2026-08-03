# B1 Boundary Validation Report

Date: 2026-04-06

## What Was Done
1. Hardened MCP boundary validation in [mcp_server.py](mcp_server.py) with new reusable validators:
- `_validate_preset(name)`
- `_validate_usage_profile(usage_profile)`
- `_validate_cycle_name(cycle_name)`

2. Added a uniform error wrapper decorator:
- `_tool_error_boundary`
- Converts exceptions to structured JSON payloads returned by MCP tools:

```json
{
  "error": true,
  "error_type": "ValidationError",
  "message": "..."
}
```

3. Applied boundary checks before `AgentAPI` calls across all tools where relevant.

4. Updated and expanded boundary tests in [tests/test_mcp.py](tests/test_mcp.py):
- Existing boundary tests now assert structured JSON errors (instead of raw exceptions)
- Added coverage for invalid preset name, invalid temperature, invalid grid size, and invalid cycle name

5. Verified test results:

```bash
/home/clement/battery_sim/.venv/bin/python -m pytest tests/test_mcp.py -k "not slow"
```

Result: `28 passed, 8 deselected`.

## Tools Hardened and How
- `run_simulation`: preset + temperature + numeric checks
- `compare_presets`: non-empty list + per-preset validation + optional temperature
- `sensitivity_analysis`: preset + parameters + boundary temperature validation
- `check_feasibility`: preset + temperature
- `optimize_charging`: preset + current range + sweep points + temperature
- `pack_sizing`: preset + positive energy/voltage + valid voltage range ordering
- `cell_selection_wizard`: positive requirement/budget checks (already present, now wrapped)
- `predict_lifetime`: preset + usage_profile key validation + cycle count + temperature
- `warranty_analysis`: preset + usage_profile key validation + warranty bounds + temperature
- `operating_window`: preset + valid `grid_size`
- `derating_curves`: preset + valid `grid_size`
- `estimate_range`: preset + cycle name + series/parallel + vehicle/power + temperature
- `compare_charging_strategies`: preset + strategy list + cycle count + temperature
- `list_presets`: wrapped for structured errors
- `get_session_summary`: wrapped for structured errors

## Key Decisions
- Error format decision:
  - Used a single stable payload shape (`error`, `error_type`, `message`) so LLM/tooling clients can branch on `error_type` and display user-safe messages.
- Validation strategy:
  - Enforce checks at MCP boundary before calling `AgentAPI`.
  - Centralize checks in helper functions to keep behavior consistent and avoid drift.
- Preset validation strategy:
  - Resolve available presets from `api.list_presets()` and include available names directly in invalid-preset messages.

## Issues Encountered
- No blocking issues.
- One compatibility adjustment was needed during implementation to keep tool forwarding aligned with current `AgentAPI` method signatures.

## Education
### Validate at the boundary
"Validate at the boundary" means inputs are checked immediately when they enter the system (here, MCP tool functions), not deep inside execution.
This prevents invalid requests from propagating into simulation internals, reduces wasted compute, and provides faster, clearer feedback to clients.

### Why LLM-facing APIs need structured errors
LLM clients handle structured JSON much more reliably than Python tracebacks.
- Structured errors are machine-parseable and predictable.
- They separate user-facing validation failures from internal crashes.
- They reduce prompt noise and make agent behavior easier to control and test.

## Next Improvements
1. Add explicit tests for invalid `usage_profile` keys on both `predict_lifetime` and `warranty_analysis`.
2. Consider publishing a shared error schema contract in docs so downstream clients can rely on it.
3. Optionally distinguish `ValidationError` from unexpected internal failures with a stable `InternalError` type while still preserving safe messages.
