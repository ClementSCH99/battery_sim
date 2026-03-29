# Phase 2b: Full Charge-Discharge Cycling — Implementation Summary

**Date**: 2026-03-29  
**Status**: Complete — all 14 tests pass (6 architecture + 8 smoke)

---

## What was delivered

Multi-cycle charge-discharge experiments with per-cycle metric extraction, end-to-end from domain model through PyBaMM execution to analysis services.

## Changes by file

### Domain layer (`core/`)

| File | Change |
|---|---|
| `core/protocol.py` | Added `CycleDefinition` frozen dataclass. Added `n_cycles` and `cycle_definition` optional fields to `Protocol`. Added `Protocol.cycle()` factory that builds a cycling protocol preserving cycle metadata for the backend. Flat steps stored for duration estimation; `n_cycles` kept as metadata for native backend repetition. |
| `core/application_services.py` | Added `CyclingAnalyzer` static service class with `capacity_fade_rate()` (linear fit), `end_of_life_prediction()` (extrapolation to threshold), and `cycling_summary()` (per-cycle dict). Also added `Signal` import. Fixed pre-existing truncation (missing closing paren on `SensitivityResult`). |
| `core/api_schema.py` | Added `_SIGNAL_METADATA` entries for all 4 cycling signals with units, interpretation, use_cases, and typical_range. |

### Signal vocabulary (`types/`)

| File | Change |
|---|---|
| `types/signal.py` | Added 4 enum members: `CYCLE_DISCHARGE_CAPACITY`, `CYCLE_CHARGE_CAPACITY`, `CYCLE_COULOMBIC_EFFICIENCY`, `CYCLE_CAPACITY_RETENTION`. |

### Backend infrastructure (`backend/`)

| File | Change |
|---|---|
| `backend/pybamm_backend.py` | Refactored `translate_protocol_to_pybamm()` → extracted `_translate_steps_to_pybamm()` helper. Top-level function now detects `cycle_definition` + `n_cycles` and builds `one_cycle_steps * n_cycles` for PyBaMM. Added `_extract_cycling_signals()` method that splits the time series into per-cycle segments and computes discharge/charge capacity, coulombic efficiency, and capacity retention. `_extract_result()` now accepts optional `protocol` to trigger cycling extraction. |
| `backend/pybamm_signal.py` | Added 4 cycling signals to `DERIVED_SIGNALS` map. |

### Tests (`tests/`)

| File | Change |
|---|---|
| `tests/test_smoke.py` | Added `TestCycling` class with 2 tests: `test_lfp_cycling_3_cycles` (3-cycle CC-CV charge + CC discharge, asserts per-cycle signals exist with correct length and first-cycle retention = 100%), `test_cycling_analyzer` (validates `CyclingAnalyzer.cycling_summary()` and `capacity_fade_rate()`). |

## Architecture compliance

- **No core → backend imports**: `core/` never imports from `backend/`. Verified by `test_no_core_imports_backend`. `CyclingAnalyzer` only reads `Signal` enum and `Result._data`, both in `core/` / `types/`.
- **Signal vocabulary consistency**: All 4 new signals appear in both `Signal` enum and `_SIGNAL_METADATA`. Verified by `test_all_signal_enum_values_in_schema`.
- **Canonical output type**: `SimulationRun` remains the sole return type. No changes to the execution contract.
- **Cycle metadata pattern**: `Protocol` carries cycle intent as metadata (`n_cycles`, `cycle_definition`). The backend decides how to translate it (flat step repetition for PyBaMM). The domain does not contain PyBaMM-specific logic.

## Design decisions

1. **Cycle repetition via flat step multiplication** (`steps * n_cycles`): Chosen over PyBaMM's tuple-based cycle grouping because the current `pybamm.Experiment` API accepts a flat list of strings. This is backend-internal and can be swapped later.
2. **Per-cycle splitting by equal array partitioning**: The time series is split into `n_cycles` segments of approximately equal length. This works for uniform cycles. If non-uniform cycles are needed later, step event markers from PyBaMM `.cycles` should be used instead.
3. **CyclingAnalyzer as static methods**: Follows the existing service pattern in `application_services.py`. No instance state needed — just pure functions over `SimulationRun`.

## Test results

```
tests/test_architecture.py  6/6 passed
tests/test_smoke.py          8/8 passed (including 2 new cycling tests)
Total: 14/14 passed in ~8s
```

## Definition of Done checklist

- [x] `Protocol.cycle(charge, discharge, n_cycles=3)` creates a cycling protocol
- [x] PyBaMM backend executes multi-cycle experiments successfully
- [x] Per-cycle capacity and efficiency are extracted as signals
- [x] `CyclingAnalyzer` computes capacity fade rate and EOL prediction
- [x] Cycling smoke test passes with 3 cycles
- [x] All existing tests still pass
- [x] New cycling signals appear in the API schema

## Follow-up candidates

- Expose `n_cycles` in `AgentAPI.run_simulation()` (deferred to Phase 2b AgentAPI step)
- Switch to PyBaMM `.cycles` attribute for per-cycle splitting when available
- Add degradation-aware cycling (SEI + cycling combined)
