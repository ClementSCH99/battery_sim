# C1 Error Propagation Report

Date: 2026-04-06

## What Was Done

1. Updated [core/charging_strategies.py](core/charging_strategies.py)
- Extended `ChargingStrategyMetrics` with:
  - `status` (`"ok"` or `"failed"`)
  - `error` (structured error text, e.g. `RuntimeError: ...`)
- Hardened `ChargingStrategyEvaluator.evaluate_strategy()`:
  - Keeps non-raising behavior for loop safety
  - Captures two failure modes:
    - hard exceptions during simulation execution
    - returned `SimulationRun` objects flagged unsuccessful
  - Populates `status`, `error`, and `notes` on failure

2. Updated [core/application_services.py](core/application_services.py)
- `BatchExecutionService.run_presets()`:
  - No longer swallows exceptions to `(preset, None)`
  - Converts execution exceptions into a failed `SimulationRun` carrying:
    - `metadata.success = False`
    - a critical `SimulationError` with exception type/message
    - placeholder diagnostics and empty `Result`
- `ComparisonService.extract_metrics()`:
  - Adds explicit `status` (`succeeded`/`failed`)
  - Adds `errors` list for failed runs (from `SimulationRun.errors` or convergence reason)
  - Preserves metric extraction best effort without hiding failure state
- `ComparisonService.compare_batch_results()`:
  - Adds aggregate counts:
    - `n_succeeded`
    - `n_failed`

3. Added/updated tests
- [tests/test_charging_strategies.py](tests/test_charging_strategies.py)
  - Failure path now asserts `status == "failed"` and structured `error`
- [tests/test_services.py](tests/test_services.py)
  - Added fast tests for:
    - `extract_metrics()` includes `errors` on failed run
    - `BatchExecutionService.run_presets()` preserves failure details
    - batch comparison includes `n_succeeded` / `n_failed`

4. Verified non-slow suite

```bash
/home/clement/battery_sim/.venv/bin/python -m pytest tests/ -k "not slow"
```

Result: `301 passed, 155 deselected`.

## Before/After Behavior

### 1) Charging strategy evaluation
Before:
- Backend failures were collapsed into a note string only.
- No explicit machine-readable status/error field.

After:
- Returned object includes:
  - `status: "failed"`
  - `error: "<ExceptionType>: <message>"`
  - `notes` retained for human readability
- Function still does not raise, preserving loop-safe behavior.

### 2) Metric extraction
Before:
- Failed/invalid runs could degrade into `None`/default values without a clear explanation.

After:
- `extract_metrics()` includes explicit failure context:
  - `status: "failed"`
  - `errors: ["..."]`
- Failure reason remains visible alongside any partial metrics.

### 3) Batch execution
Before:
- Exceptions were converted to `(preset, None)` and reason was lost.

After:
- Failures are represented as failed `SimulationRun` records with explicit error payload.
- Batch summaries report `n_succeeded` and `n_failed`.

## Key Decisions

1. Preserve external contracts where possible
- Kept `evaluate_strategy()` non-raising.
- Kept `run_presets()` return shape compatible (`(label, run)` tuples), but made failed runs diagnosable.

2. Prefer structured failure signals over sentinels
- Added explicit `status` and `errors` fields to extracted metrics.
- Preserved best-effort numeric extraction while making failure state first-class.

3. Keep backward compatibility for existing consumers
- Existing successful paths and test expectations remain valid.
- Added fields extend behavior rather than breaking shape.

## AgentAPI Surface Verification

Checked [core/agent_api.py](core/agent_api.py) for propagation behavior:
- Charging strategy outputs already surface per-strategy notes in both:
  - JSON (`strategies[].notes`)
  - Markdown (`## Notes` section)
- With this change, those notes now carry structured failure details from `evaluate_strategy()`.
- No `AgentAPI` interface change was required.

## Issues Encountered

- No blocking issues.
- One design choice required care: preserving tuple-based batch APIs while adding diagnosable failure content. This was solved by emitting failed `SimulationRun` objects instead of `None`.

## Education

### Sentinel values vs structured errors
Using sentinels like `None`/`0` to represent failures is an anti-pattern when diagnostics matter.
- Sentinels are ambiguous (`0` might be valid data or failure fallback).
- They erase root cause and location context.
- They force downstream consumers to infer failure heuristically.

Structured errors preserve intent and cause explicitly, enabling robust handling and clear user feedback.

### Why silent failure is dangerous in LLM-facing APIs
LLM clients rely on response structure to reason and explain outcomes.
If failures are silent:
- The model may hallucinate confidence from partial/default values.
- Users get plausible but wrong interpretations.
- Automated tool-chaining makes bad decisions based on hidden failures.

Explicit `status` + `errors` makes failure states observable, debuggable, and safer.

## Next Improvements

1. Standardize a shared error envelope at the result formatter layer so all comparison markdown outputs include failure summaries automatically.
2. Add a dedicated `failed_scenarios` section in comparison JSON for simpler downstream consumption.
3. Add telemetry fields (`failure_stage`, `exception_type`) to improve triage in large parameter sweeps.
