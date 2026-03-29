# Phase 3a — Unit Tests: Delivery Summary

**Date**: 2026-03-29  
**Scope**: Fast unit tests for domain logic — no PyBaMM required.

## What was delivered

| File | Tests | Focus |
|---|---|---|
| `tests/test_domain.py` | 46 | Cell, Protocol, Environment, SolverConfig, Model, Simulation validation |
| `tests/test_result.py` | 24 | Result accessors, metric calculations, missing-signal safety, NaN handling |
| `tests/test_errors.py` | 21 | ErrorDetector (voltage, NaN/Inf, divergence), ConstraintChecker, SimulationError VO |
| **Total** | **91** | All pass in < 0.3 s, zero PyBaMM dependency |

## Verification

```
pytest tests/test_domain.py tests/test_result.py tests/test_errors.py -v
# 91 passed in 0.30s

pytest tests/ -v
# 125 passed, 1 failed (pre-existing: test_agent_api.py::TestSessionTracking — unrelated)
```

## Coverage by domain object

- **Cell** — positive capacity/voltage enforcement, None-allowed, preset factory, all-presets-validate sweep.
- **Protocol** — factory methods (cc, rest, cccv), empty-step rejection, zero-current rejection, `__add__` merge, `total_duration_s()` with undefined-duration steps.
- **Environment** — temperature bounds (including exact boundaries -40/100), `ambient_temperature_C` alias, missing-temperature TypeError.
- **SolverConfig** — SOC range [0,1], negative rtol/atol, default validity, boundary values.
- **Model** — enum values, case-insensitive lookup, typo tolerance (`single_particule`), unknown-value rejection, label property.
- **Simulation** — composite `validate()` propagates typed errors from each child component.
- **Result** — convenience accessors return `Optional[TimeSeries]`, analysis methods return `Optional[float]` when signal is absent, empty Result is safe, NaN does not raise.
- **ErrorDetector** — voltage OOB (above/below), NaN/Inf detection across all signals, divergence detection, `detect_all` aggregation.
- **ConstraintChecker** — cell feasibility (capacity, voltage range, resistance sign), protocol feasibility (temperature warnings), feasibility report format.
- **SimulationError** — `is_critical()`, dict round-trip, `summary()` format.

## Observations for future work

1. **SolverConfig.validate() uses `elif` chains** — only the first failing branch reports an error. If rtol < 0 *and* SOC is out of range, only the rtol error shows. Consider switching to an error-collector pattern if users need full diagnostic output.
2. **`SolverConfig.validate()` checks `rtol < 0` but the error message says "strictly positive"** — `rtol=0` is accepted. The code and the message are inconsistent at the boundary. Minor, but worth a look.
3. **`test_agent_api.py::TestSessionTracking::test_session_grows_after_investigations`** fails independently (pre-existing). Session history length doesn't grow after `check_feasibility`. Not in scope here.
