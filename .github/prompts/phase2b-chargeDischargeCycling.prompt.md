# Phase 2b: Full Charge-Discharge Cycling

Add support for multi-cycle charge-discharge experiments with per-cycle metric extraction.

## Prerequisites
- Phase 2a (CC-CV Protocol) must be complete — CC-CV charge works end-to-end

## Context

Currently battery_sim can run single-pass protocols (one discharge, or one charge+discharge). Real battery testing involves cycling: repeated charge → rest → discharge → rest sequences over many cycles. PyBaMM natively supports this via `pybamm.Experiment` with cycle notation.

The domain model has `Protocol.__add__()` for combining steps, but no concept of repeating cycles. The backend translates steps linearly — no cycle repetition.

## Architecture Rules
- Cycling is a **domain concept** — `Protocol` should express it
- Cycle repetition translation belongs in **backend** (`translate_protocol_to_pybamm`)
- Per-cycle metric extraction can live in `Result` or a new `CyclingAnalyzer` service
- `core/` must not import from `backend/`

## Steps

### 1. Add `Protocol.cycle()` factory

In `core/protocol.py`, add a factory method and supporting structure:

```python
@dataclass(frozen=True)
class CycleDefinition:
    """One charge-discharge cycle."""
    charge: Protocol
    discharge: Protocol
    rest_after_charge_s: float = 600   # 10 min rest
    rest_after_discharge_s: float = 600

@dataclass(frozen=True)
class Protocol:
    steps: List[Step]
    cycles: Optional[int] = None  # None = single pass, int = repeat
    cycle_definition: Optional[CycleDefinition] = None
```

Add factory:
```python
@classmethod
def cycle(cls, charge: "Protocol", discharge: "Protocol",
          n_cycles: int = 1, rest_s: float = 600) -> "Protocol":
    """Create a cycling protocol: (charge + rest + discharge + rest) × n_cycles."""
```

Design choice: Either (a) expand into flat steps at Protocol level, or (b) keep `cycles` as metadata and let the backend handle repetition. Option (b) is better — PyBaMM has native cycle support via `pybamm.Experiment(...) * n_cycles`.

### 2. Update PyBaMM translation for cycles

In `backend/pybamm_backend.py`, update `translate_protocol_to_pybamm()` and `_build_experiment()`:

PyBaMM supports cycles like:
```python
experiment = pybamm.Experiment(
    [
        "Charge at 1A until 3.65V",
        "Hold at 3.65V until 0.05A",
        "Rest for 600 seconds",
        "Discharge at 2A for 3600 seconds",
        "Rest for 600 seconds",
    ] * n_cycles
)
```

Or using PyBaMM's native cycle grouping (check current PyBaMM API version).

### 3. Add per-cycle metric extraction

In `backend/pybamm_backend.py` `_extract_result()`, or in a new helper:
- PyBaMM solutions have a `.cycles` attribute when run with experiments
- Extract per-cycle: discharge capacity (Ah), charge capacity (Ah), Coulombic efficiency, voltage range
- Store these as new signals or as structured data on `Result`

Options:
- **Option A**: Add `CYCLE_CAPACITY`, `CYCLE_EFFICIENCY` to `Signal` enum, store as `TimeSeries` where time = cycle number
- **Option B**: Add a `cycle_metrics: List[Dict]` field to `Result` — simpler but breaks the pure signal model

Recommend **Option A** for consistency with the signal-based architecture.

### 4. Add cycling signals to Signal enum

In `types/signal.py`:
```python
# Cycling signals (time axis = cycle number)
CYCLE_DISCHARGE_CAPACITY = "cycle_discharge_capacity"
CYCLE_CHARGE_CAPACITY = "cycle_charge_capacity"
CYCLE_COULOMBIC_EFFICIENCY = "cycle_coulombic_efficiency"
CYCLE_CAPACITY_RETENTION = "cycle_capacity_retention"
```

Update `backend/pybamm_signal.py` `DERIVED_SIGNALS` to include these.
Update `core/api_schema.py` `_SIGNAL_METADATA` to include descriptions.

### 5. Add `CyclingAnalyzer` to application services

In `core/application_services.py`, add:

```python
class CyclingAnalyzer:
    """Extract cycling performance trends from multi-cycle SimulationRuns."""

    @staticmethod
    def capacity_fade_rate(run: SimulationRun) -> float:
        """Capacity fade per cycle (Ah/cycle) from linear fit."""

    @staticmethod
    def end_of_life_prediction(run: SimulationRun, eol_threshold: float = 0.8) -> Optional[int]:
        """Predict cycle number where capacity drops below threshold."""

    @staticmethod
    def cycling_summary(run: SimulationRun) -> Dict[str, Any]:
        """Per-cycle summary: capacity, efficiency, retention."""
```

### 6. Add cycling smoke test

In `tests/test_smoke.py`:

```python
@pytest.mark.slow
def test_lfp_cycling_3_cycles():
    """Run 3 charge-discharge cycles and extract per-cycle metrics."""
    cell = Cell.preset("LFP_5AH")
    charge = Protocol.cccv(charge_current_A=2.0, cutoff_voltage_V=3.65, taper_current_A=0.1)
    discharge = Protocol.cc(current_A=5.0, duration_s=1800)
    protocol = Protocol.cycle(charge, discharge, n_cycles=3, rest_s=300)

    sim = Simulation(
        cell=cell, model=Model.SPM, protocol=protocol,
        environment=Environment(temperature_C=25.0),
        solver_config=SolverConfig(initial_soc=0.2),
    )
    backend = PyBaMMBackend()
    run = sim.run(backend)

    assert isinstance(run, SimulationRun)
    # Per-cycle signals should be available
    cycle_cap = run.result.get(Signal.CYCLE_DISCHARGE_CAPACITY)
    assert cycle_cap is not None
    assert len(cycle_cap.values) == 3
```

### 7. Expose cycling in AgentAPI (if Phase 1 complete)

Add or extend `run_simulation` tool to accept `n_cycles` parameter. Add a `cycling_analysis` tool that runs cycles and returns degradation trends.

## Files to Read First
- `core/protocol.py` — current step/protocol model
- `backend/pybamm_backend.py` — `translate_protocol_to_pybamm()`, `_extract_result()`
- `types/signal.py` — current Signal enum
- `backend/pybamm_signal.py` — signal mappings
- `core/application_services.py` — service patterns to follow

## Files to Create/Modify
- **Modify**: `core/protocol.py` — add `CycleDefinition`, `Protocol.cycle()`, cycle metadata
- **Modify**: `backend/pybamm_backend.py` — translate cycles, extract per-cycle metrics
- **Modify**: `types/signal.py` — add cycling signals
- **Modify**: `backend/pybamm_signal.py` — add cycling signal mappings
- **Modify**: `core/api_schema.py` — add cycling signal metadata
- **Modify**: `core/application_services.py` — add `CyclingAnalyzer`
- **Modify**: `tests/test_smoke.py` — add cycling smoke test
- **Modify**: `tests/test_architecture.py` — verify new signals appear in schema

## Definition of Done
- [ ] `Protocol.cycle(charge, discharge, n_cycles=3)` creates a cycling protocol
- [ ] PyBaMM backend executes multi-cycle experiments successfully
- [ ] Per-cycle capacity and efficiency are extracted as signals
- [ ] `CyclingAnalyzer` computes capacity fade rate and EOL prediction
- [ ] Cycling smoke test passes with 3 cycles
- [ ] All existing tests still pass
- [ ] New cycling signals appear in the API schema
