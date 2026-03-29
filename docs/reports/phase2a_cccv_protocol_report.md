# Phase 2a: CC-CV Protocol Support — Completion Report

**Date**: 2026-03-29  
**Status**: Complete  

---

## Scope

Verify and validate CC-CV (constant-current / constant-voltage) charge protocol support end-to-end through the domain model, PyBaMM backend, and test suite.

## Findings — Pre-existing Code (no changes needed)

| Component | File | Status |
|---|---|---|
| `CC_CV` step dataclass | `core/protocol.py` | Correct — `charge_current_A`, `cutoff_voltage_V`, `taper_current_A` |
| `Protocol.cccv()` factory | `core/protocol.py` | Correct — returns `Protocol([CC_CV(...)])` |
| `Protocol.__add__()` | `core/protocol.py` | Correct — concatenates step lists |
| `Protocol.validate()` CC_CV branch | `core/protocol.py` | Correct — validates positive charge current, nonzero cutoff voltage, positive taper current |
| `translate_protocol_to_pybamm()` | `backend/pybamm_backend.py` | Correct — emits `"Charge at X A until Y V"` + `"Hold at Y V until Z A"` (valid PyBaMM syntax) |
| `CC_CV.duration_s()` returns `None` | `core/protocol.py` | Correct — `total_duration_s()` skips `None`, and `build_t_eval()` returns `None` when `time_step_s` is unset, letting PyBaMM manage timing via the experiment |

No code fixes were required in `core/protocol.py` or `backend/pybamm_backend.py`.

## Changes Made

### `tests/test_smoke.py`

Added `TestCCCVProtocol` class with two tests:

- **`test_cccv_charge_then_cc_discharge`** — CC-CV charge (2 A → 3.65 V, taper 0.1 A) followed by CC discharge (5 A, 120 s) on LFP_5AH at SOC 0.5. Verifies the combined protocol produces a successful `SimulationRun` with signals.
- **`test_cccv_only`** — Standalone CC-CV charge (1 A → 3.65 V, taper 0.05 A) on LFP_5AH at SOC 0.5. Verifies a pure CC-CV protocol works without a discharge phase.

## Test Results

```
tests/test_smoke.py       — 4 passed (4.67 s)
tests/test_architecture.py — 6 passed (0.18 s)
```

All 10 tests pass. No regressions.

## Architecture Compliance

- `core/` does not import from `backend/` (verified by `test_architecture.py`).
- Protocol domain objects contain no PyBaMM-specific logic.
- All translations happen in `backend/pybamm_backend.py`.

## Definition of Done

- [x] `Protocol.cccv()` factory creates a valid CC-CV protocol
- [x] `Protocol.__add__` combines CC-CV charge + CC discharge into a multi-step protocol
- [x] End-to-end test passes: CC-CV charge → CC discharge → `SimulationRun` with signals
- [x] `pytest tests/test_smoke.py -v` passes including the new tests
- [x] `pytest tests/test_architecture.py -v` still passes

## Follow-up: AgentAPI / MCP `run_simulation`

`AgentAPI.run_simulation()` and the MCP `run_simulation` tool currently only accept `current_A` / `duration_s` (CC-only). They do **not** expose CC-CV protocol parameters. Extending the agent interface to support CC-CV simulation requests is a separate task (Phase 2b or later).
