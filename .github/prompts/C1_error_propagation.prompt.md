## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end.

## TASK
Fix error swallowing in the service layer so failures are diagnosable instead of silently converted to None/0.

## CONTEXT
- Project: PyBaMM battery assistant API
- Architecture review found that several service layers collapse exceptions into `None`, `0`, or printed warnings
- `core/charging_strategies.py` `evaluate_strategy()` swallows simulation failures into a string
- `core/application_services.py` `ComparisonService.extract_metrics()` and `BatchExecutionService` replace failures with sentinel values
- This means the LLM (and the user) never learns *why* a simulation failed within a batch

## INSTRUCTIONS
1. **Fix `core/charging_strategies.py` `evaluate_strategy()`** (~lines 247-315):
   - When simulation fails, include failure details in the returned result dict
   - Add an `"error"` key with the exception type and message
   - Do NOT let the function raise — it's called in loops, so it must return a result
   - Example: `{"status": "failed", "error": "SolverError: convergence failed at t=120s", ...}`

2. **Fix `core/application_services.py` `extract_metrics()`**:
   - When a `SimulationRun` has errors or is not successful, include an `"errors"` list in the extracted metrics dict instead of replacing values with 0 or None
   - Example: `{"preset": "NCA_5AH", "status": "failed", "errors": ["SolverError: ..."], ...}`

3. **Fix `core/application_services.py` `BatchExecutionService`**:
   - When a run fails, include it in results with error information rather than silently dropping it
   - The batch result should report `n_succeeded` and `n_failed` counts

4. **Verify `core/agent_api.py`** surfaces these error entries:
   - Check that `DualFormatResult.json_data` includes error entries from failed runs
   - The markdown output should mention failures too
   - If already handled, no changes needed — just verify

5. **Add/update tests**:
   - Test that `evaluate_strategy()` returns structured error on simulation failure
   - Test that `extract_metrics()` includes error info for failed runs
   - Test that batch results report failure counts

## SCOPE BOUNDARIES
- Only modify `core/charging_strategies.py`, `core/application_services.py`, and tests
- Do NOT change `mcp_server.py` (that's Phase F)
- Do NOT change the `AgentAPI` interface unless error entries are being dropped
- Preserve backward compatibility — existing passing tests must still pass

## OUTPUT
- Updated service layer with structured error propagation
- Updated/new tests validating error reporting
- A report in `/docs/reports/C1_error_propagation.md` including:
  - what was done
  - before/after behavior for each fix
  - key decisions
  - issues encountered
  - next improvements

## EDUCATION
- Explain "sentinel values vs structured errors" anti-pattern in the report
- Explain why silent failure is especially dangerous in LLM-facing APIs

## DEFINITION OF DONE
- `evaluate_strategy()` returns `{"status": "failed", "error": "..."}` on simulation failure
- `extract_metrics()` includes `"errors"` list for failed runs instead of None/0
- Batch results include `n_succeeded` / `n_failed` counts
- All existing tests still pass: `pytest tests/ -k "not slow"`
- New tests validate error propagation paths
