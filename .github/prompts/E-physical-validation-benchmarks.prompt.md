## ROLE

You are a senior Python engineer, battery simulation validation expert, and mentor.
You understand how to verify physical correctness of electrochemical simulations: energy conservation, sign conventions, model hierarchy consistency, and degradation monotonicity.

## GOAL

Execute this task end-to-end: build a comprehensive physical validation and cross-model benchmark test suite that proves the enriched physics from phases A-D are physically correct and consistent.

## TASK

Implement **Phase E — Physical Validation & Cross-Model Benchmarks**

## CONTEXT

- Project: PyBaMM battery assistant API (`battery_sim`)
- Phases A-D added: thermal coupling, deep electrochemical signals, advanced degradation, and new parameter sets
- Existing test suites: `test_domain.py` (fast unit), `test_smoke.py` (slow integration), `test_architecture.py` (guards)
- This phase creates a dedicated `tests/test_physics_validation.py` for physics-level correctness
- All tests that need PyBaMM should be marked `@pytest.mark.slow`
- No new features — pure validation and verification

## INSTRUCTIONS

### 1. Create `tests/test_physics_validation.py`

This file contains physics-level tests organized by domain. All PyBaMM tests use `@pytest.mark.slow`.

#### A. Energy Conservation Tests

```python
def test_energy_conservation_thermal():
    """In a thermal simulation, ∫P·dt must match the cumulative energy signal."""
    # Run LFP_5AH CC discharge 1A for 120s with thermal_model="lumped"
    # Extract POWER and ENERGY signals
    # Compute ∫P·dt via trapezoidal integration
    # Assert relative error < 1% between computed and reported ENERGY
```

```python
def test_higher_crate_more_heat():
    """Higher C-rate must produce more heat generation."""
    # Run same cell at 0.5A and 2A CC discharge, thermal_model="lumped"
    # Assert mean(HEAT_GENERATION @ 2A) > mean(HEAT_GENERATION @ 0.5A)
    # Assert final CELL_TEMPERATURE @ 2A > final CELL_TEMPERATURE @ 0.5A
```

#### B. Thermal-Electrical Coupling Test

```python
def test_thermal_changes_voltage():
    """Thermal model must produce a different voltage curve than isothermal."""
    # Run NMC_5AH CC discharge 2A for 120s — isothermal vs lumped thermal
    # Assert voltage arrays are NOT identical (thermal feedback changes kinetics)
    # The difference should be small but measurable (> 1mV at some point)
```

#### C. Cross-Model Benchmark

```python
def test_cross_model_voltage_ordering():
    """DFN must show greater voltage drop than SPMe, which is greater than SPM.
    
    Physical reasoning: SPM ignores electrolyte transport entirely.
    SPMe adds electrolyte but assumes uniform concentration in electrodes.
    DFN models full transport → more losses → lower voltage under load.
    """
    # Run NMC_5AH, CC discharge 1A for 120s on SPM, SPMe, DFN
    # Compare voltage at t=60s (mid-discharge)
    # Assert: V_SPM >= V_SPMe >= V_DFN (within 0.5V of each other, but ordered)
    # All three should start at similar OCV (within 10mV at t=0)
```

#### D. Electrode Balance Test

```python
def test_voltage_decomposition():
    """Terminal voltage ≈ OCV_pos - OCV_neg - η_pos - η_neg (approximately).
    
    This is not exact because of electrolyte potential drop, but should be
    close for low-rate discharge.
    """
    # Run DFN model, NMC_5AH, CC discharge 0.5A for 60s
    # At each timestep: V_reconstructed = POSITIVE_OCV - NEGATIVE_OCV - |POSITIVE_REACTION_OVERPOTENTIAL| - |NEGATIVE_REACTION_OVERPOTENTIAL|
    # Assert: |V_terminal - V_reconstructed| < 0.2V on average
    # (gap is from electrolyte IR drop, not modeled in the simple decomposition)
```

#### E. Degradation Monotonicity Tests

```python
def test_sei_thickness_monotonic():
    """SEI thickness must never decrease (irreversible growth)."""
    # Run NMC_5AH cycling (3 cycles) with sei_model="ec reaction limited" on SPMe
    # Extract SEI_THICKNESS signal
    # Assert all differences >= 0 (monotonically non-decreasing)
```

```python
def test_capacity_retention_decreasing():
    """Capacity retention must not increase cycle-over-cycle with irreversible degradation."""
    # Run cycling with SEI degradation
    # Extract CYCLE_CAPACITY_RETENTION
    # Assert each value <= previous (monotonically non-increasing)
```

#### F. Sign Convention Tests

```python
def test_discharge_current_positive():
    """By convention, discharge current must be positive."""
    # Run CC discharge — assert all current values > 0
```

```python
def test_charge_current_negative():
    """By convention, charge current must be negative."""
    # Run CC charge (or CCCV) — assert current values < 0 during charge phase
```

#### G. New Parameter Sets Smoke Tests

```python
@pytest.mark.parametrize("preset_name", [
    "NMC_ECKER_18650", "NMC_OKANE_AGING", "NMC_MOHTAT_POUCH", "NMC811_AI_LGM50"
])
def test_new_preset_simulates(preset_name):
    """Each new preset must produce a valid simulation result."""
    # Load preset, run SPM CC discharge 0.5A for 60s
    # Assert result has VOLTAGE with values in [2.0, 5.0] V range
    # Assert result has TIME with monotonically increasing values
```

### 2. Add domain tests in `tests/test_domain.py`

Add fast tests for new domain objects (if not already added in phases A-D):
- All new Signal enum values are unique
- New Signal entries exist in PYBAMM_SIGNAL_MAP or DERIVED_SIGNALS
- `DegradationConfig` resolve() backward compat
- `Environment` thermal_model validation

### 3. Run full test suite

After writing all tests:
```bash
# Fast tests first (no PyBaMM)
pytest tests/test_domain.py tests/test_architecture.py -v

# Then full suite including physics validation
pytest -v

# Physics validation only
pytest tests/test_physics_validation.py -v
```

Ensure no regressions in any existing test.

## OUTPUT

- New `tests/test_physics_validation.py` with ≥8 physics tests
- Updated `tests/test_domain.py` if needed for new domain objects
- A report in `/docs/reports/E_physical_validation.md` including:
  - What was done
  - Test results summary (pass/fail counts)
  - Any physics surprises (unexpected voltage ordering, conservation violations)
  - Issues encountered
  - Next improvements (automated CI physics regression, tolerance tuning)

## EDUCATION

In the report, briefly explain:
- **Why physics validation is different from unit testing**: Unit tests check code logic. Physics tests check that the mathematical model produces results consistent with electrochemistry. A unit test passes if `f(x) == expected_y`, but a physics test checks that `∫P·dt ≈ E` (energy conservation) or `dSEI/dt ≥ 0` (thermodynamic irreversibility).
- **Cross-model hierarchy**: SPM → SPMe → DFN is an increasing fidelity sequence. Each model adds physics (electrolyte transport, concentration gradients) that creates additional voltage losses. If DFN shows *higher* voltage than SPM, something is wrong.
- **Voltage decomposition**: The terminal voltage of a lithium-ion cell is the difference between positive and negative electrode potentials, minus all overpotential losses (kinetic, ohmic, concentration). Being able to decompose V into components is the most powerful diagnostic tool in battery engineering.
- **Why monotonicity matters**: In an irreversible degradation mechanism, the degradation variable (SEI thickness, capacity loss) is thermodynamically forbidden from decreasing. If a simulation shows non-monotonic SEI thickness, either the model is wrong or the solver is producing numerical artifacts.
