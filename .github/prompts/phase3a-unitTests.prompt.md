# Phase 3a: Unit Tests

Add unit tests for domain objects and core logic — no PyBaMM execution required.

## Context

Current test coverage is minimal:
- `tests/test_architecture.py` — architectural fitness tests (import rules, contract types, signal consistency)
- `tests/test_smoke.py` — end-to-end tests that require PyBaMM execution (slow)

Missing: fast unit tests that validate domain logic, validation rules, metric calculations, and error detection without running simulations.

## Architecture Rules
- Unit tests must not depend on PyBaMM or any backend
- Use mock/synthetic data for `Result` and `TimeSeries` testing
- Tests should be fast (no `@pytest.mark.slow`)

## Steps

### 1. Create `tests/test_domain.py` — Domain object validation

Test each domain object's validation and factory methods:

**Cell:**
- `Cell(chemistry="LFP", nominal_capacity_Ah=5.0).validate()` — should pass
- `Cell(chemistry="LFP", nominal_capacity_Ah=-1.0).validate()` — should raise `CellValidationError`
- `Cell(chemistry="LFP", nominal_voltage_V=0).validate()` — should raise `CellValidationError`
- `Cell(chemistry="LFP", nominal_capacity_Ah=None).validate()` — should pass (None is allowed)
- `Cell.preset("LFP_5AH")` — should return a Cell with chemistry="LFP"
- `Cell.preset("NONEXISTENT")` — should raise an error
- `Cell.list_presets()` — should return a non-empty list of strings

**Protocol:**
- `Protocol.cc(current_A=5.0, duration_s=60)` — should create single ConstantCurrent step
- `Protocol.rest(duration_s=300)` — should create single Rest step
- `Protocol.cccv(...)` — should create CC_CV step(s)
- `Protocol.cc(current_A=0, duration_s=60)` — should fail validation (zero current)
- `Protocol(steps=[])` — should fail validation (no steps)
- `Protocol.__add__` — combining two protocols should merge steps
- `Protocol.total_duration_s()` — should sum step durations

**Environment:**
- `Environment(temperature_C=25.0)` — should pass validation
- `Environment(temperature_C=-50)` — should raise `EnvironmentValidationError` (below -40°C)
- `Environment(temperature_C=110)` — should raise `EnvironmentValidationError` (above 100°C)
- `Environment(ambient_temperature_C=25.0)` — legacy alias should work
- `env.temperature_C` and `env.ambient_temperature_C` should return same value

**SolverConfig:**
- `SolverConfig()` — defaults should be valid
- `SolverConfig(initial_soc=-0.1)` — should raise `SolverValidationError`
- `SolverConfig(initial_soc=1.5)` — should raise `SolverValidationError`
- `SolverConfig(rtol=0)` — should raise `SolverValidationError`

**Model:**
- `Model.SPM` — should equal `"single_particle"`
- `Model.from_value("spm")` — case-insensitive lookup
- `Model.from_value("single_particule")` — typo tolerance
- `Model.from_value("unknown")` — should raise `ValueError`

**Simulation:**
- Simulation with valid components should pass `validate()`
- Simulation with invalid cell should propagate `CellValidationError`

### 2. Create `tests/test_result.py` — Result metric calculations

Create synthetic `TimeSeries` data and test `Result` methods:

```python
def make_result(voltage_values, current_values, time_s):
    """Helper to build a Result from synthetic data."""
    from battery_sim.types.signal import Signal
    from battery_sim.types.timeseries import TimeSeries
    from battery_sim.core.result import Result

    data = {
        Signal.TIME: TimeSeries(time_s=time_s, values=time_s, unit="s"),
        Signal.VOLTAGE: TimeSeries(time_s=time_s, values=voltage_values, unit="V"),
        Signal.CURRENT: TimeSeries(time_s=time_s, values=current_values, unit="A"),
    }
    return Result(data)
```

Test cases:
- `result.voltage()` — returns TimeSeries for voltage signal
- `result.available_signals()` — returns list of available Signal enums
- `result.min_voltage()` / `result.max_voltage()` — correct min/max
- `result.peak_current()` — correct peak
- `result.total_energy_Wh()` — verify numerical integration (trap rule)
- Empty result (no signals) — graceful handling, not crashes
- Result with NaN values — methods should handle without exceptions

### 3. Create `tests/test_errors.py` — Error detection

Test `ErrorDetector` with synthetic anomalous data:

```python
def test_detect_voltage_out_of_bounds():
    """Voltage exceeding safe bounds triggers a violation."""
    # Create TimeSeries with voltage spike to 6V
    result = make_result(voltage_values=[3.2, 3.3, 6.0, 3.1], ...)
    errors = ErrorDetector.detect_voltage_violations(result, min_v=2.5, max_v=4.2)
    assert len(errors) >= 1
    assert errors[0].error_type == ErrorType.VOLTAGE_OUT_OF_BOUNDS

def test_detect_nan():
    """NaN in signals triggers numerical issue detection."""
    result = make_result(voltage_values=[3.2, float('nan'), 3.1], ...)
    errors = ErrorDetector.detect_numerical_issues(result)
    assert any(e.error_type == ErrorType.NAN_DETECTED for e in errors)

def test_no_errors_on_clean_data():
    """Clean data should produce no errors."""
    result = make_result(voltage_values=[3.2, 3.3, 3.1], ...)
    errors = ErrorDetector.detect_all(result)
    assert len(errors) == 0
```

### 4. Create constraint checker tests

Test `ConstraintChecker` from `core/investigation_tools.py`:

```python
def test_cell_feasibility_valid_cell():
    cell = Cell.preset("LFP_5AH")
    violations = ConstraintChecker.check_cell_feasibility(cell)
    critical = [v for v in violations if v.severity == "critical" and v.violated]
    assert len(critical) == 0

def test_protocol_feasibility():
    cell = Cell.preset("LFP_5AH")
    env = Environment(temperature_C=25.0)
    violations = ConstraintChecker.check_protocol_feasibility(cell, env)
    # Standard conditions should be feasible
    ...
```

## Files to Read First
- `core/cell.py` — validation logic, preset factory
- `core/protocol.py` — step types, factories, validation
- `core/environment.py` — temperature validation, alias support
- `core/solver.py` — SolverConfig validation
- `core/model.py` — enum parsing, aliases
- `core/result.py` — metric methods to test
- `core/simulation_error.py` — `ErrorDetector` methods
- `core/investigation_tools.py` — `ConstraintChecker`
- `core/exceptions.py` — exception hierarchy

## Files to Create
- **Create**: `tests/test_domain.py`
- **Create**: `tests/test_result.py`
- **Create**: `tests/test_errors.py`

## Definition of Done
- [ ] `tests/test_domain.py` covers all domain object validation paths
- [ ] `tests/test_result.py` covers Result metric calculations with synthetic data
- [ ] `tests/test_errors.py` covers ErrorDetector with anomalous data
- [ ] All new tests pass: `pytest tests/test_domain.py tests/test_result.py tests/test_errors.py -v`
- [ ] No new test requires PyBaMM execution (all run fast)
- [ ] Existing tests still pass: `pytest tests/ -v`
