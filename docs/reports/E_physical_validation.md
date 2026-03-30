# Phase E — Physical Validation & Cross-Model Benchmarks

**Date:** 2026-03-29  
**Scope:** Pure verification — no new features  
**Author:** automated  

## What Was Done

Created a dedicated `tests/test_physics_validation.py` test suite (13 tests) and extended `tests/test_domain.py` with 5 new fast signal-registration tests.

### New Files

- **`tests/test_physics_validation.py`** — 13 physics-level tests across 7 categories (all `@pytest.mark.slow`)

### Modified Files

- **`tests/test_domain.py`** — Added `TestThermalSignals` (2 tests) and `TestDegradationSignals` (3 tests)

## Test Results Summary

| Suite | Tests | Passed | Failed |
|-------|-------|--------|--------|
| test_physics_validation.py | 13 | 13 | 0 |
| test_domain.py | 82 | 82 | 0 |
| Full suite (all files) | 208 | 208 | 0 |

### Physics Validation Tests (13)

| # | Test | Domain | Result |
|---|------|--------|--------|
| 1 | `test_energy_conservation_thermal` | Energy conservation | PASS |
| 2 | `test_higher_crate_more_heat` | Energy conservation | PASS |
| 3 | `test_thermal_changes_voltage` | Thermal–electrical coupling | PASS |
| 4 | `test_cross_model_voltage_ordering` | Cross-model benchmark | PASS |
| 5 | `test_voltage_decomposition` | Electrode balance | PASS |
| 6 | `test_sei_thickness_monotonic` | Degradation monotonicity | PASS |
| 7 | `test_capacity_retention_decreasing` | Degradation monotonicity | PASS |
| 8 | `test_discharge_current_positive` | Sign conventions | PASS |
| 9 | `test_charge_current_negative` | Sign conventions | PASS |
| 10 | `test_new_preset_simulates[NMC_ECKER_KOKAM]` | Parameter sets | PASS |
| 11 | `test_new_preset_simulates[NMC_OKANE_AGING]` | Parameter sets | PASS |
| 12 | `test_new_preset_simulates[NMC_MOHTAT_POUCH]` | Parameter sets | PASS |
| 13 | `test_new_preset_simulates[NMC_AI_ENERTECH]` | Parameter sets | PASS |

### New Domain Tests (5)

| # | Test | Domain |
|---|------|--------|
| 1 | `TestThermalSignals::test_all_thermal_signals_unique` | Phase A signals |
| 2 | `TestThermalSignals::test_all_thermal_signals_in_pybamm_signal_map` | Phase A signals |
| 3 | `TestDegradationSignals::test_all_degradation_signals_unique` | Phase C signals |
| 4 | `TestDegradationSignals::test_all_degradation_signals_in_pybamm_signal_map` | Phase C signals |
| 5 | `TestDegradationSignals::test_all_cycling_signals_are_derived` | Derived signals |

## Physics Surprises & Observations

### 1. `HEAT_GENERATION` signal not extracted

The PyBaMM signal `"Total heat generation [W]"` (`Signal.HEAT_GENERATION`) is not present in simulation output, even with `thermal_model="lumped"`. However, the component signals (`IRREVERSIBLE_HEAT`, `REVERSIBLE_HEAT`, `OHMIC_HEAT`) in W/m³ are available. The test was adapted to use `IRREVERSIBLE_HEAT` for the C-rate comparison.

### 2. Thermal–voltage coupling is sub-millivolt at 2A / 120s

With NMC_5AH at 2A CC discharge for 120 seconds, the maximum voltage difference between isothermal and lumped thermal simulations is ~0.65 mV. This is physically correct — the temperature rise is small (< 1 K) for this short, moderate-rate protocol. The threshold was set to 0.1 mV to capture the real effect.

### 3. CCCV charge feasibility depends on initial SOC and cutoff voltage

When starting at SOC=0.5 with LFP (cutoff 3.65 V), the CCCV charge step is infeasible because the cell voltage is already near 3.2 V nominal and the OCV curve is flat. PyBaMM logs a warning and skips the step. The test was adapted to use NMC at SOC=0.2 where the gap between open-circuit voltage and cutoff is large enough for the charge step to execute.

### 4. Capacity retention metric unreliable with short cycles

With very short discharge durations (120s at 5A from SOC=0.2), some cycles extract zero discharge capacity because the battery is already near empty. The `CYCLE_CAPACITY_RETENTION` metric then shows `[0%, 0%, 50%]` — an artifact of the protocol, not a physics violation. The test was redesigned to verify degradation monotonicity via `SEI_THICKNESS` and `TOTAL_CAPACITY_LOSS` signals directly, which are robust to protocol design.

### 5. Cross-model voltage ordering confirmed

SPM ≥ SPMe ≥ DFN voltage ordering at mid-discharge is confirmed for NMC_5AH at 1A. The voltage spread is small (~5–15 mV) because 1A is a low C-rate for a 5 Ah cell, meaning electrolyte transport losses (which differentiate SPMe/DFN from SPM) are modest.

## Education

### Why physics validation is different from unit testing

Unit tests check code logic: `f(x) == expected_y`. Physics tests check that the mathematical model produces results consistent with electrochemistry. A unit test passes if `validate()` raises on bad input, but a physics test checks that ∫P·dt ≈ E (energy conservation) or dSEI/dt ≥ 0 (thermodynamic irreversibility). Physics tests can pass with code bugs (if the bug doesn't affect the tested relationship) and can fail with correct code (if model parameters are unrealistic).

### Cross-model hierarchy

SPM → SPMe → DFN is an increasing fidelity sequence:

- **SPM** (Single Particle Model): One representative particle per electrode, no electrolyte transport. Fastest, least detailed.
- **SPMe** (SPM with Electrolyte): Adds electrolyte transport but assumes uniform concentration within electrode particles. Intermediate.
- **DFN** (Doyle-Fuller-Newman): Full PDE for solid and electrolyte transport. Most detailed, slowest.

Each model adds physics that creates additional voltage losses (electrolyte IR drop, concentration overpotentials). Therefore, under load: V_SPM ≥ V_SPMe ≥ V_DFN. If DFN shows *higher* voltage than SPM, something is wrong.

### Voltage decomposition

The terminal voltage of a lithium-ion cell is:

V_terminal = φ_positive − φ_negative = (OCV_pos − OCV_neg) − |η_pos| − |η_neg| − IR_electrolyte

Being able to decompose V into electrode OCV contributions and overpotential losses is the most powerful diagnostic tool in battery engineering. It reveals whether voltage drop comes from kinetic limitations (overpotentials), transport limitations (electrolyte IR), or thermodynamic factors (electrode balancing).

### Why monotonicity matters

In an irreversible degradation mechanism, the degradation variable (SEI thickness, capacity loss) is thermodynamically forbidden from decreasing. SEI forms by consuming electrolyte at the anode surface — this reaction is irreversible under normal operating conditions. If a simulation shows non-monotonic SEI thickness, either:
1. The model equations are wrong
2. The solver is producing numerical artifacts (negative time steps, oscillations)
3. The signal extraction is mapping the wrong variable

All three are bugs that should be caught before trusting the simulation for real engineering decisions.

## Next Improvements

1. **CI physics regression**: Add a `physics` marker and run `pytest -m physics` in CI on every PR touching `backend/` or `core/`
2. **Tolerance tuning**: The 0.1 mV thermal coupling threshold and 0.2 V voltage decomposition threshold could be tightened with longer protocols
3. **Parametric sweep**: Run cross-model benchmark at multiple C-rates (0.1C, 0.5C, 1C, 2C) to verify the voltage ordering holds across the operating range
4. **Round-trip efficiency**: Add a test verifying that charge-discharge round-trip energy efficiency is between 85% and 99% — a universal Li-ion constraint
5. **Temperature-dependent degradation**: Verify that SEI growth rate increases with temperature (Arrhenius kinetics)
