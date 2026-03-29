# Phase 2c: Degradation Modeling

Add battery degradation modeling using PyBaMM's built-in degradation sub-models (SEI growth, lithium plating).

## Prerequisites
- Phase 2b (Charge-Discharge Cycling) must be complete — multi-cycle experiments work
- Per-cycle metric extraction is functional

## Context

PyBaMM supports degradation sub-models that can be added to SPM/DFN models:
- **SEI (Solid Electrolyte Interphase) growth**: Main cause of capacity fade in lithium-ion batteries
- **Lithium plating**: Occurs during fast charging or low-temperature charging
- **Active material loss**: Electrode degradation over cycling

These are activated by passing options to PyBaMM model constructors:
```python
model = pybamm.lithium_ion.SPM(options={"SEI": "ec_reaction_limited"})
```

Currently battery_sim has no degradation configuration — models are built with default options only.

## Architecture Rules
- Degradation configuration is a **domain concept** — belongs in `core/`
- PyBaMM-specific option strings belong in **backend** only
- `core/` must not reference PyBaMM option names or constants
- New `Signal` members for degradation metrics follow existing patterns

## Steps

### 1. Add `Model.SPMe` to the model enum

In `core/model.py`, add the Single Particle Model with electrolyte (intermediate fidelity, better for degradation studies):

```python
class Model(str, Enum):
    SPM = "single_particle"
    SPMe = "single_particle_electrolyte"  # NEW
    DFN = "doyle_fuller_newman"
```

Update `from_value()` aliases and `label` property. Update backend's `_build_model()` and `supports_model()`.

### 2. Create `DegradationConfig` domain object

In `core/`, create a new file or add to an existing module:

```python
@dataclass(frozen=True)
class DegradationConfig:
    """Domain-level degradation settings (backend-agnostic)."""
    sei_growth: bool = False
    lithium_plating: bool = False
    active_material_loss: bool = False

    def validate(self) -> None:
        """At least one mechanism must be enabled if config is used."""
        pass  # All-false is valid (no degradation)
```

This stays backend-agnostic — no PyBaMM option strings here.

### 3. Add degradation config to `Simulation`

In `core/simulation.py`:
```python
@dataclass(frozen=True)
class Simulation:
    cell: Cell
    model: Model
    protocol: Protocol
    environment: Environment
    solver_config: SolverConfig = field(default_factory=SolverConfig)
    degradation: Optional[DegradationConfig] = None  # NEW
```

### 4. Map degradation config to PyBaMM options in backend

In `backend/pybamm_backend.py`, update `_build_model()`:

```python
def _build_model(self, simulation: Simulation):
    options = {}
    if simulation.degradation:
        if simulation.degradation.sei_growth:
            options["SEI"] = "ec_reaction_limited"
        if simulation.degradation.lithium_plating:
            options["lithium plating"] = "irreversible"
        # etc.

    if simulation.model == Model.SPM:
        return pybamm.lithium_ion.SPM(options=options or None)
    elif simulation.model == Model.SPMe:
        return pybamm.lithium_ion.SPMe(options=options or None)
    elif simulation.model == Model.DFN:
        return pybamm.lithium_ion.DFN(options=options or None)
```

**Important**: Check the current PyBaMM version's API for exact option keys and values. The options syntax may have changed. Read PyBaMM docs or inspect `pybamm.lithium_ion.SPM` options.

### 5. Add degradation signals

In `types/signal.py`:
```python
# Degradation signals
SEI_THICKNESS = "sei_thickness"
LITHIUM_PLATING_CAPACITY = "lithium_plating_capacity"
LOSS_OF_ACTIVE_MATERIAL = "loss_of_active_material"
TOTAL_CAPACITY_LOSS = "total_capacity_loss"
```

In `backend/pybamm_signal.py`, map to PyBaMM variable names:
```python
Signal.SEI_THICKNESS: ("Loss of lithium to SEI [mol]", "mol"),  # or equivalent
Signal.LITHIUM_PLATING_CAPACITY: ("Loss of lithium to lithium plating [mol]", "mol"),
```

**Important**: Check exact PyBaMM variable names — they vary by model and version. Use `solution.data.keys()` to inspect available outputs.

### 6. Extract degradation metrics in backend

In `backend/pybamm_backend.py` `_extract_result()`, add extraction for degradation signals when present in the PyBaMM solution. These are standard PyBaMM outputs when degradation sub-models are active.

### 7. Add degradation smoke test

In `tests/test_smoke.py`:

```python
@pytest.mark.slow
def test_lfp_sei_degradation_5_cycles():
    """Run 5 cycles with SEI degradation and check capacity fade."""
    from battery_sim.core.degradation import DegradationConfig  # or wherever it lives

    cell = Cell.preset("LFP_5AH")
    charge = Protocol.cccv(charge_current_A=2.0, cutoff_voltage_V=3.65, taper_current_A=0.1)
    discharge = Protocol.cc(current_A=5.0, duration_s=1800)
    protocol = Protocol.cycle(charge, discharge, n_cycles=5, rest_s=300)

    sim = Simulation(
        cell=cell, model=Model.SPM, protocol=protocol,
        environment=Environment(temperature_C=25.0),
        solver_config=SolverConfig(initial_soc=0.2),
        degradation=DegradationConfig(sei_growth=True),
    )
    backend = PyBaMMBackend()
    run = sim.run(backend)

    assert isinstance(run, SimulationRun)
    # Capacity should decrease over cycles
    cycle_cap = run.result.get(Signal.CYCLE_DISCHARGE_CAPACITY)
    if cycle_cap:
        assert cycle_cap.values[-1] <= cycle_cap.values[0]  # Fade expected
```

### 8. Update schema and API

- Update `core/api_schema.py` `_SIGNAL_METADATA` with degradation signal descriptions
- Update `tests/test_architecture.py` signal consistency checks
- If MCP server exists, new signals are automatically discoverable (schema-driven)

## Files to Read First
- `core/model.py` — current Model enum
- `core/simulation.py` — current Simulation dataclass
- `backend/pybamm_backend.py` — `_build_model()`, `_extract_result()`
- `types/signal.py` — current Signal enum
- `backend/pybamm_signal.py` — signal mapping patterns
- PyBaMM documentation on degradation options (or inspect `pybamm.lithium_ion.SPM`)

## Files to Create/Modify
- **Create**: `core/degradation.py` (or add `DegradationConfig` to existing module)
- **Modify**: `core/model.py` — add `SPMe`
- **Modify**: `core/simulation.py` — add `degradation` field
- **Modify**: `backend/pybamm_backend.py` — map degradation to PyBaMM options, extract signals
- **Modify**: `types/signal.py` — add degradation signals
- **Modify**: `backend/pybamm_signal.py` — add degradation signal mappings
- **Modify**: `core/api_schema.py` — add degradation signal metadata
- **Modify**: `tests/test_smoke.py` — add degradation smoke test
- **Modify**: `tests/test_architecture.py` — update signal checks

## Definition of Done
- [ ] `Model.SPMe` exists and backend can build it
- [ ] `DegradationConfig` expresses SEI/plating/active material loss as domain booleans
- [ ] `Simulation` accepts optional degradation config
- [ ] Backend maps degradation config to correct PyBaMM model options
- [ ] Degradation signals are extracted when sub-models are active
- [ ] 5-cycle degradation smoke test passes
- [ ] All existing tests still pass
- [ ] New signals appear in API schema
