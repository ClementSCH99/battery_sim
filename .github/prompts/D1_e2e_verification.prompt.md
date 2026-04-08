## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end.

## TASK
End-to-end verification of the MCP server — confirm the full loop works from VS Code Copilot through simulation to response.

## CONTEXT
- Project: PyBaMM battery assistant API with MCP server
- Phases A1 (config fix), B1 (boundary validation), C1 (error propagation) should be complete
- Server uses stdio transport via `.vscode/mcp.json`
- 15 tools registered in `mcp_server.py`
- First PyBaMM call takes ~20s (JIT compilation)

## INSTRUCTIONS
1. **Run full test suite**:
   - `pytest tests/test_mcp.py` (including slow round-trip tests marked `@pytest.mark.slow`)
   - `pytest tests/ -k "not slow"` (all fast tests across the project)
   - Fix any failures found

2. **Verify tool discovery**:
   - Reload VS Code (`Ctrl+Shift+P` → Developer: Reload Window)
   - Check that 15 battery-sim tools appear in Copilot tool list (prefixed `mcp_battery-sim_`)

3. **Test simple flow** (via Copilot chat or direct MCP calls):
   - `list_presets` → verify returns preset list with chemistry info
   - `run_simulation` with `preset_name="LFP_5AH"` → verify returns voltage/current/energy metrics
   - `check_feasibility` with `preset_name="LFP_5AH"` → verify returns feasibility verdict

4. **Test complex flow**:
   - `compare_presets` with `preset_names=["LFP_5AH", "NMC_5AH"]` → verify comparison table
   - `optimize_charging` with `preset_name="LFP_5AH"` → verify charging optimization results

5. **Test error handling**:
   - Send invalid preset name → verify structured JSON error (not traceback)
   - Send out-of-range temperature (e.g. 999) → verify clear error message

6. **Document findings**:
   - Record response times for each tool
   - Note any unexpected behaviors or edge cases
   - List any remaining issues for follow-up

## SCOPE BOUNDARIES
- Do NOT add new features
- Fix only bugs discovered during testing
- Keep fixes minimal and targeted

## OUTPUT
- All tests passing (fast + slow)
- Verified end-to-end flows documented
- A report in `/docs/reports/D1_e2e_verification.md` including:
  - test results summary (pass/fail counts)
  - response times per tool
  - issues found and fixed
  - remaining issues for follow-up
  - screenshots or output samples if useful

## EDUCATION
- Explain MCP tool execution lifecycle in the report (VS Code → stdio → FastMCP → tool function → response)
- Explain cold start vs warm call performance difference (PyBaMM JIT)

## DEFINITION OF DONE
- `pytest tests/test_mcp.py` — ALL tests pass (fast + slow)
- `pytest tests/ -k "not slow"` — ALL fast tests pass
- 15 tools visible in VS Code Copilot after reload
- Simple flow (list → run → check) completes successfully
- Complex flow (compare → optimize) completes successfully
- Invalid inputs return structured error JSON
- Report documents response times and any remaining issues
