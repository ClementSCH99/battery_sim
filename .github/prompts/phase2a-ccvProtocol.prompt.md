# Phase 2a: CC-CV Protocol Support

Verify and complete CC-CV (constant-current / constant-voltage) charge protocol support end-to-end.

## Context

The domain model already defines a `CC_CV` step class in `core/protocol.py`:
```python
@dataclass(frozen=True)
class CC_CV(Step):
    charge_current_A: float
    cutoff_voltage_V: float
    taper_current_A: float
```

And `backend/pybamm_backend.py` already translates it in `translate_protocol_to_pybamm()`:
```python
elif isinstance(step, CC_CV):
    strings.append(f"Charge at {step.charge_current_A} A until {step.cutoff_voltage_V} V")
    strings.append(f"Hold at {step.cutoff_voltage_V} V until {step.taper_current_A} A")
```

There is also a `Protocol.cccv()` factory method. However, this has never been validated end-to-end with a real PyBaMM execution.

## Architecture Rules
- `core/` must never import from `backend/`
- Protocol domain objects must not contain PyBaMM-specific logic
- All translations happen in `backend/pybamm_backend.py`

## Steps

### 1. Verify `Protocol.cccv()` factory

Read `core/protocol.py` and confirm:
- `Protocol.cccv()` creates a `CC_CV` step with correct parameters
- The factory accepts `charge_current_A`, `cutoff_voltage_V`, `taper_current_A`
- If missing or incomplete, add/fix it

### 2. Verify PyBaMM translation

Read `backend/pybamm_backend.py` `translate_protocol_to_pybamm()` and confirm:
- `CC_CV` step is handled (it is — see Context above)
- The PyBaMM experiment strings are valid PyBaMM syntax
- PyBaMM expects: `"Charge at X A until Y V"` then `"Hold at Y V until Z A"` — confirm this matches PyBaMM's experiment string format

### 3. Run end-to-end CC-CV test

Create a manual test or add to `tests/test_smoke.py`:

```python
def test_cccv_charge_discharge():
    """CC-CV charge followed by CC discharge."""
    cell = Cell.preset("LFP_5AH")
    # CC-CV charge: 2A until 3.65V, taper to 0.1A
    # Then CC discharge: 5A for 120s
    charge = Protocol.cccv(charge_current_A=2.0, cutoff_voltage_V=3.65, taper_current_A=0.1)
    discharge = Protocol.cc(current_A=5.0, duration_s=120)
    protocol = charge + discharge  # Protocol.__add__ combines steps

    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=Environment(temperature_C=25.0),
    )
    backend = PyBaMMBackend()
    run = sim.run(backend)

    assert isinstance(run, SimulationRun)
    assert run.metadata.success
    assert len(run.result.available_signals()) >= 1
```

### 4. Fix any issues

Common problems to check:
- PyBaMM may require specific string formatting for CC-CV experiments
- The `initial_soc` default is 1.0 (fully charged) — for a charge test, set `initial_soc=0.5` or lower in `SolverConfig`
- CC_CV `_duration_s` property may return `None` — verify `Protocol.total_duration_s()` handles this
- PyBaMM experiment may need explicit operating voltage bounds for the cell chemistry

### 5. Add `run_simulation` support for CC-CV

If Phase 1 (MCP Server) is complete, verify the `run_simulation` tool on `AgentAPI` can accept protocol type parameters to trigger CC-CV simulations. If not yet, note this as a follow-up.

## Files to Read First
- `core/protocol.py` — `CC_CV` class, `Protocol.cccv()` factory, `Protocol.__add__()`
- `backend/pybamm_backend.py` — `translate_protocol_to_pybamm()`, `_build_experiment()`
- `core/solver.py` — `SolverConfig.initial_soc` (needs to be <1.0 for charge tests)
- `tests/test_smoke.py` — existing smoke tests to extend

## Files to Create/Modify
- **Modify**: `tests/test_smoke.py` — add CC-CV smoke test
- **Possibly modify**: `core/protocol.py` — fix `Protocol.cccv()` if incomplete
- **Possibly modify**: `backend/pybamm_backend.py` — fix translation if PyBaMM rejects the strings

## Definition of Done
- [ ] `Protocol.cccv()` factory creates a valid CC-CV protocol
- [ ] `Protocol.__add__` combines CC-CV charge + CC discharge into a multi-step protocol
- [ ] End-to-end test passes: CC-CV charge → CC discharge → `SimulationRun` with signals
- [ ] `pytest tests/test_smoke.py -v` passes including the new test
- [ ] `pytest tests/test_architecture.py -v` still passes
