# Phase B — Deep Electrochemical Observability

**Date:** 2026-03-29
**Status:** Complete

## Summary

Exposed 13 new electrode-level physics signals from PyBaMM's internal solver variables, enabling the AI assistant to observe concentrations, potentials, exchange current densities, open-circuit voltages, and stoichiometries at each electrode.

## What was done

### 1. New Signal enum entries (`types/signal.py`)

Added 13 signals organized into 6 categories:

| Category | Signals |
|---|---|
| Surface concentrations | `NEGATIVE_PARTICLE_SURFACE_CONCENTRATION`, `POSITIVE_PARTICLE_SURFACE_CONCENTRATION` |
| Open-circuit voltages | `NEGATIVE_OCV`, `POSITIVE_OCV` |
| Reaction overpotentials | `NEGATIVE_REACTION_OVERPOTENTIAL`, `POSITIVE_REACTION_OVERPOTENTIAL` |
| Exchange current densities | `NEGATIVE_EXCHANGE_CURRENT_DENSITY`, `POSITIVE_EXCHANGE_CURRENT_DENSITY` |
| Electrolyte & stoichiometry | `ELECTROLYTE_POTENTIAL`, `NEGATIVE_STOICHIOMETRY`, `POSITIVE_STOICHIOMETRY` |
| Solid-phase potentials | `NEGATIVE_SOLID_POTENTIAL`, `POSITIVE_SOLID_POTENTIAL` |

### 2. PyBaMM signal mappings (`backend/pybamm_signal.py`)

- Added all 13 signals to `PYBAMM_SIGNAL_MAP` with their PyBaMM variable names (X-averaged variants)
- Added aliases in `PYBAMM_SIGNAL_ALIASES` for OCV, electrolyte potential, and reaction overpotential signals that have multiple PyBaMM names

### 3. Signal catalog metadata (`core/api_schema.py`)

Added `_SIGNAL_METADATA` entries for all 13 signals with unit, interpretation, use cases, and typical ranges.

### 4. Tests

- **Domain tests** (`test_domain.py::TestElectrochemicalSignals`): Verify all 13 enum values exist, are unique, and are present in `PYBAMM_SIGNAL_MAP`
- **Smoke tests** (`test_smoke.py::TestDeepElectrochemicalObservability`):
  - DFN + NMC_5AH produces ≥5 Phase B signals
  - Negative OCV in [0, 1.5] V range (graphite vs Li/Li⁺)
  - Positive OCV in [2.5, 5.0] V range (NMC vs Li/Li⁺)
  - SPM runs without crash (electrolyte-only signals gracefully absent)

All 165 tests pass.

## Key decisions

### Why X-averaged?

SPM and SPMe have no spatial electrode resolution — only x-averaged values exist. DFN could provide position-resolved profiles, but x-averaged quantities are the universal comparable form across all model fidelities. This makes Phase B signals usable regardless of chosen model.

### Why graceful skip?

The existing `_extract_result()` loop catches `KeyError` when a signal's PyBaMM variable doesn't exist for the selected model. Adding new entries to `PYBAMM_SIGNAL_MAP` is sufficient — no backend changes were needed. SPM simulations simply produce fewer signals (no electrolyte potential), while DFN produces the full set.

### Why aliases?

PyBaMM uses different variable names depending on model and version. For example, `"X-averaged negative electrode open-circuit potential [V]"` vs `"Negative electrode open-circuit potential [V]"`. Aliases ensure signals are found regardless of which name PyBaMM uses internally.

## Issues encountered

None. The architecture was well-prepared for this extension — adding signals required only declarative additions to the enum, map, aliases, and metadata.

## Educational notes

### Terminal voltage decomposition

```
V_cell = U_pos(θ_pos) − U_neg(θ_neg) − η_pos − η_neg − ΔΦ_e
```

Where:
- **U_pos**, **U_neg** — open-circuit potentials (from `POSITIVE_OCV`, `NEGATIVE_OCV`)
- **η_pos**, **η_neg** — reaction overpotentials (from `POSITIVE_REACTION_OVERPOTENTIAL`, `NEGATIVE_REACTION_OVERPOTENTIAL`)
- **ΔΦ_e** — electrolyte potential drop (from `ELECTROLYTE_POTENTIAL`)

### Butler-Volmer kinetics

Exchange current density **j₀** controls the reaction rate and depends on surface concentration and temperature. The overpotential **η** drives the reaction via:

```
j = j₀ [ exp(αₐ·F·η / R·T) − exp(−αc·F·η / R·T) ]  ≈  2·j₀·sinh(F·η / 2·R·T)
```

The signals `NEGATIVE_EXCHANGE_CURRENT_DENSITY` and `POSITIVE_EXCHANGE_CURRENT_DENSITY` expose **j₀** at each electrode.

### Stoichiometry vs SOC

Electrode stoichiometry **θ = cₛ / cₛ,max** is the local "filling fraction" of lithium in the particle. Cell SOC is a weighted combination of both electrodes' stoichiometries. The signals `NEGATIVE_STOICHIOMETRY` and `POSITIVE_STOICHIOMETRY` give electrode-level insight that cell SOC alone cannot provide — essential for diagnosing asymmetric degradation.

### Why X-averaged (expanded)

SPM assumes uniform composition across the electrode thickness — only a single representative particle exists per electrode. SPMe adds electrolyte transport but still averages electrode variables. DFN resolves the full spatial dimension but x-averaged quantities remain the standard for inter-model comparison and trend analysis.

## Next improvements

- **Spatial profiles for DFN**: Expose position-resolved variables (concentration gradients through electrode thickness) for transport-limited regimes
- **Phase-space plots**: θ_neg vs θ_pos trajectories to visualize electrode balance and capacity fade mechanisms
- **Differential voltage analysis**: dV/dQ curves derived from the new OCV signals for non-invasive degradation diagnostics
- **Real-time voltage decomposition**: Auto-compute the contribution of each loss term to terminal voltage drop
