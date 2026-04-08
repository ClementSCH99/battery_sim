---
mode: agent
description: Add PowerStep to protocol and PyBaMM backend translation
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add power-based discharge/charge steps to the battery simulation protocol system.

## TASK
Implement **PowerStep** — a new step type that drives a cell at constant power (watts) for a given duration.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- The protocol system lives in `core/protocol.py` with existing step types: `ConstantCurrent`, `Rest`, `CC_CV`
- Backend translation happens in `backend/pybamm_backend.py` — the method `_translate_steps_to_pybamm()` converts domain steps into PyBaMM experiment strings
- PyBaMM supports power-based experiment strings like `"Discharge at 10 W for 3600 seconds"` and `"Charge at 5 W for 1800 seconds"`
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `PowerStep` dataclass in `core/protocol.py`
- Fields: `power_W: float`, `_duration_s: float`
- Positive power = discharge, negative power = charge (document this convention)
- Implement `duration_s()` method like other steps
- Add validation in `Protocol.validate()`: power_W must not be zero

### 2. Add `Protocol.power()` static factory
- Signature: `Protocol.power(power_W: float, duration_s: float) -> Protocol`
- Follows the pattern of `Protocol.cc()` and `Protocol.rest()`

### 3. Extend PyBaMM backend translation
- In `backend/pybamm_backend.py`, update `_translate_steps_to_pybamm()` to handle `PowerStep`
- Generate strings like `"Discharge at 10 W for 3600 seconds"` (positive power) or `"Charge at 5 W for 1800 seconds"` (negative power → use abs value)

### 4. Add tests
- In `tests/test_domain.py`, add tests for:
  - PowerStep creation and duration
  - Protocol.power() factory
  - Protocol validation rejects power_W=0
  - Protocol composition: `Protocol.power(10, 3600) + Protocol.rest(600)`
- In `tests/test_smoke.py` or a new test, verify PyBaMM translation produces correct experiment string

### 5. Write clean, minimal code
- Do not over-engineer
- Add useful comments explaining the PyBaMM string format convention

## OUTPUT
- Working code: `PowerStep` in protocol.py, translation in pybamm_backend.py, tests passing
- A report in `/docs/reports/A1_power_step.md` including:
  - What was done
  - Key decisions (sign convention for power)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- What constant-power discharge means physically (voltage drops → current increases to maintain power)
- Why power-based steps matter for EV applications (motors demand power, not current)
- How PyBaMM internally handles power experiments
