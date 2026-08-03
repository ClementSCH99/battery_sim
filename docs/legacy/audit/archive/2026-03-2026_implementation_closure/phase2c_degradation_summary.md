# Phase 2c: Degradation Modeling — Implementation Summary

**Date**: 2026-03-29  
**Status**: Complete — all 14 tests pass (6 architecture + 8 smoke)

---

## What was delivered

### 1. `Model.SPMe` enum variant
- **File**: `core/model.py`
- Added `SPMe = "single_particle_electrolyte"` to the `Model` enum
- Updated `label`, `from_value()` aliases (`"spme"`, `"single_particle_electrolyte"`)
- Backend builds `pybamm.lithium_ion.SPMe` and `supports_model()` includes it

### 2. `DegradationConfig` domain object
- **File**: `core/degradation.py` (new)
- Frozen dataclass with three boolean flags: `sei_growth`, `lithium_plating`, `active_material_loss`
- `any_enabled()` helper, `validate()` method
- Backend-agnostic — no PyBaMM strings in core

### 3. `Simulation.degradation` field
- **File**: `core/simulation.py`
- `degradation: Optional[DegradationConfig] = None` — backward-compatible
- `validate()` calls `degradation.validate()` when present

### 4. Backend degradation mapping
- **File**: `backend/pybamm_backend.py`
- `_build_model()` accepts optional `degradation` parameter
- Maps domain booleans to verified PyBaMM 25.12.2 option strings:
  - `sei_growth` → `{"SEI": "ec reaction limited"}`
  - `lithium_plating` → `{"lithium plating": "irreversible"}`
  - `active_material_loss` → `{"loss of active material": "stress-driven"}`
- SPMe model routing added alongside SPM/DFN

### 5. Degradation signals
- **File**: `types/signal.py` — 4 new enum members:
  - `SEI_THICKNESS`, `LITHIUM_PLATING_CAPACITY`, `LOSS_OF_ACTIVE_MATERIAL`, `TOTAL_CAPACITY_LOSS`
- **File**: `backend/pybamm_signal.py` — PyBaMM variable mappings:
  - `X-averaged negative SEI thickness [m]`
  - `Loss of capacity to negative lithium plating [A.h]`
  - `Loss of active material in negative electrode [%]`
  - `Total capacity lost to side reactions [A.h]`
- **File**: `core/api_schema.py` — full `_SIGNAL_METADATA` entries for all 4 signals

### 6. Tests
- **File**: `tests/test_smoke.py` — 2 new tests in `TestDegradation`:
  - `test_lfp_sei_degradation_3_cycles` — 3-cycle SEI run, checks `SEI_THICKNESS` and `TOTAL_CAPACITY_LOSS` signals present
  - `test_spme_model_runs` — SPMe model end-to-end without degradation

---

## Architecture compliance

| Rule | Status |
|------|--------|
| Core does not import backend | ✅ `DegradationConfig` in `core/`, PyBaMM strings in `backend/` only |
| Signal enum is single source of truth | ✅ Schema auto-derives from enum; architecture test confirms consistency |
| `SimulationRun` canonical output | ✅ No change to output contract |
| No core→backend dependency | ✅ Architecture test passes (AST-level check) |

## Files changed

| File | Action |
|------|--------|
| `core/model.py` | Modified — added `SPMe` |
| `core/degradation.py` | **Created** — `DegradationConfig` dataclass |
| `core/simulation.py` | Modified — added `degradation` field |
| `core/api_schema.py` | Modified — added 4 signal metadata entries |
| `types/signal.py` | Modified — added 4 degradation signals |
| `backend/pybamm_backend.py` | Modified — degradation option mapping, SPMe routing |
| `backend/pybamm_signal.py` | Modified — 4 degradation signal mappings |
| `tests/test_smoke.py` | Modified — 2 new degradation tests |

## Test results

```
14 passed in 7.85s
  6 architecture tests — all pass
  8 smoke tests — all pass (including 2 new degradation tests)
```

## PyBaMM version note

Validated against **PyBaMM 25.12.2**. Option strings are space-separated (e.g. `"ec reaction limited"`, not `"ec_reaction_limited"`). If the PyBaMM version changes, the option strings in `backend/pybamm_backend.py` `_build_model()` may need updating.
