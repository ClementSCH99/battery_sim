## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end.

## TASK
Harden MCP boundary validation so all 15 tools reject invalid inputs with clear error messages.

## CONTEXT
- Project: PyBaMM battery assistant API with MCP server (`mcp_server.py`)
- `mcp_server.py` already has validation helpers: `_validate_temperature()`, `_validate_positive()`, `_validate_non_negative()`, `_validate_string_list()`, `_validate_grid_size()`
- Several tools don't use these helpers where they should
- Invalid preset names travel deep into execution before failing
- Raw Python tracebacks reach the LLM instead of structured error messages
- Existing boundary tests in `tests/test_mcp.py` class `TestMCPBoundaryValidation`

## INSTRUCTIONS
1. **Create `_validate_preset(name)` helper** in `mcp_server.py`:
   - Check preset exists in the catalog (`api.list_presets()` or direct preset lookup)
   - Raise `ValueError` with available presets listed in the message
2. **Add missing validation calls** to these tools:
   - `sensitivity_analysis` — missing `_validate_temperature()`, `_validate_preset()`
   - `predict_lifetime` — missing `_validate_temperature()`, `_validate_preset()`, validate `usage_profile` keys if provided
   - `warranty_analysis` — missing `_validate_temperature()`, `_validate_preset()`, validate `usage_profile` keys
   - `operating_window` — missing `_validate_preset()`, missing `_validate_grid_size()`
   - `derating_curves` — missing `_validate_preset()`, missing `_validate_grid_size()`
   - `estimate_range` — missing `_validate_preset()`, `_validate_temperature()`, validate `cycle_name` against known cycles
   - `compare_charging_strategies` — missing `_validate_preset()`, `_validate_temperature()`
3. **Add error wrapper** — Create a decorator or wrapper that catches exceptions in tool functions and returns structured JSON error responses:
   ```python
   {"error": True, "error_type": "ValidationError", "message": "..."}
   ```
   instead of raw tracebacks
4. **Add tests** in `tests/test_mcp.py`:
   - Test invalid preset name → clear error message
   - Test out-of-range temperature → clear error message
   - Test invalid grid_size → clear error message
   - Test invalid cycle_name → clear error message

## SCOPE BOUNDARIES
- Only modify `mcp_server.py` and `tests/test_mcp.py`
- Do NOT change core logic, agent_api, or services
- Do NOT add new tools

## OUTPUT
- Updated `mcp_server.py` with validation on all 15 tools
- Updated `tests/test_mcp.py` with new boundary tests
- A report in `/docs/reports/B1_boundary_validation.md` including:
  - what was done
  - which tools were hardened and how
  - key decisions (error format, validation strategy)
  - issues encountered
  - next improvements

## EDUCATION
- Explain "validate at the boundary" principle in the report
- Explain why LLM-facing APIs need structured error responses (not tracebacks)

## DEFINITION OF DONE
- All 15 tools have input validation before forwarding to `AgentAPI`
- Invalid preset name → JSON error with available presets
- Invalid temperature → JSON error with valid range
- All existing + new tests pass: `pytest tests/test_mcp.py -k "not slow"`
