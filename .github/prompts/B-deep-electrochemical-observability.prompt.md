## ROLE

You are a senior Python engineer, electrochemist, and mentor.
You understand the Doyle-Fuller-Newman (DFN) model internals: solid-state diffusion, Butler-Volmer kinetics, electrolyte transport, and how each electrode contributes to the terminal voltage.

## GOAL

Execute this task end-to-end: expose PyBaMM's rich internal electrochemical variables so the AI assistant can observe electrode-level physics — concentrations, potentials, exchange current densities, and open-circuit voltages.

## TASK

Implement **Phase B — Deep Electrochemical Observability**

## CONTEXT

- Project: PyBaMM battery assistant API (`battery_sim`)
- Currently only 4 internal state signals exist: `ANODE_POTENTIAL`, `CATHODE_POTENTIAL`, `OVERPOTENTIAL`, `ELECTROLYTE_CONCENTRATION`
- PyBaMM computes dozens of internal variables. The codebase extracts them via `PYBAMM_SIGNAL_MAP` in `backend/pybamm_signal.py`. Missing signals are silently skipped (KeyError catch in `_extract_result()`).
- SPM has no electrolyte spatial dimension; SPMe adds electrolyte transport; DFN has the full picture. Signal extraction must handle model-dependent availability gracefully.
- Phase A (thermal) may or may not be implemented yet. This phase is independent.

## INSTRUCTIONS

### 1. Add new Signal enum entries in `types/signal.py`

Add these electrochemical observability signals:

```python
# Electrode surface concentrations
NEGATIVE_PARTICLE_SURFACE_CONCENTRATION = "negative_particle_surface_concentration"
POSITIVE_PARTICLE_SURFACE_CONCENTRATION = "positive_particle_surface_concentration"

# Electrode open-circuit voltages (OCV vs Li/Li+)
NEGATIVE_OCV = "negative_ocv"
POSITIVE_OCV = "positive_ocv"

# Electrode reaction overpotentials (Butler-Volmer)
NEGATIVE_REACTION_OVERPOTENTIAL = "negative_reaction_overpotential"
POSITIVE_REACTION_OVERPOTENTIAL = "positive_reaction_overpotential"

# Exchange current densities (Butler-Volmer kinetics)
NEGATIVE_EXCHANGE_CURRENT_DENSITY = "negative_exchange_current_density"
POSITIVE_EXCHANGE_CURRENT_DENSITY = "positive_exchange_current_density"

# Electrolyte potentials (SPMe/DFN only)
ELECTROLYTE_POTENTIAL = "electrolyte_potential"

# Electrode stoichiometries (electrode-level SOC)
NEGATIVE_STOICHIOMETRY = "negative_stoichiometry"
POSITIVE_STOICHIOMETRY = "positive_stoichiometry"

# Solid-phase potential
NEGATIVE_SOLID_POTENTIAL = "negative_solid_potential"
POSITIVE_SOLID_POTENTIAL = "positive_solid_potential"
```

### 2. Map signals in `backend/pybamm_signal.py`

Add to `PYBAMM_SIGNAL_MAP`:

```python
Signal.NEGATIVE_PARTICLE_SURFACE_CONCENTRATION: (
    "X-averaged negative particle surface concentration [mol.m-3]", "mol/m³"),
Signal.POSITIVE_PARTICLE_SURFACE_CONCENTRATION: (
    "X-averaged positive particle surface concentration [mol.m-3]", "mol/m³"),
Signal.NEGATIVE_OCV: (
    "X-averaged negative electrode open-circuit potential [V]", "V"),
Signal.POSITIVE_OCV: (
    "X-averaged positive electrode open-circuit potential [V]", "V"),
Signal.NEGATIVE_REACTION_OVERPOTENTIAL: (
    "X-averaged negative electrode reaction overpotential [V]", "V"),
Signal.POSITIVE_REACTION_OVERPOTENTIAL: (
    "X-averaged positive electrode reaction overpotential [V]", "V"),
Signal.NEGATIVE_EXCHANGE_CURRENT_DENSITY: (
    "X-averaged negative electrode exchange current density [A.m-2]", "A/m²"),
Signal.POSITIVE_EXCHANGE_CURRENT_DENSITY: (
    "X-averaged positive electrode exchange current density [A.m-2]", "A/m²"),
Signal.ELECTROLYTE_POTENTIAL: (
    "X-averaged electrolyte potential [V]", "V"),
Signal.NEGATIVE_STOICHIOMETRY: (
    "X-averaged negative electrode stoichiometry", "-"),
Signal.POSITIVE_STOICHIOMETRY: (
    "X-averaged positive electrode stoichiometry", "-"),
Signal.NEGATIVE_SOLID_POTENTIAL: (
    "X-averaged negative electrode potential [V]", "V"),
Signal.POSITIVE_SOLID_POTENTIAL: (
    "X-averaged positive electrode potential [V]", "V"),
```

Add aliases in `PYBAMM_SIGNAL_ALIASES` for key signals that have multiple PyBaMM names:

```python
Signal.NEGATIVE_OCV: [
    "X-averaged negative electrode open-circuit potential [V]",
    "Negative electrode open-circuit potential [V]",
],
Signal.POSITIVE_OCV: [
    "X-averaged positive electrode open-circuit potential [V]",
    "Positive electrode open-circuit potential [V]",
],
Signal.ELECTROLYTE_POTENTIAL: [
    "X-averaged electrolyte potential [V]",
    "Electrolyte potential [V]",
],
Signal.NEGATIVE_REACTION_OVERPOTENTIAL: [
    "X-averaged negative electrode reaction overpotential [V]",
    "Negative electrode reaction overpotential [V]",
],
Signal.POSITIVE_REACTION_OVERPOTENTIAL: [
    "X-averaged positive electrode reaction overpotential [V]",
    "Positive electrode reaction overpotential [V]",
],
```

### 3. No changes needed in `backend/pybamm_backend.py`

The existing `_extract_result()` loop already iterates over `PYBAMM_SIGNAL_MAP` and gracefully handles `KeyError` when a signal is not available for a given model. Adding entries to the map is sufficient.

Verify this by checking that SPM simulations don't crash when electrolyte-only signals are in the map.

### 4. Write tests

**In `tests/test_domain.py` (fast, no PyBaMM):**
- Verify all new Signal enum values exist and are unique strings
- Verify new signals appear in `PYBAMM_SIGNAL_MAP`

**In `tests/test_smoke.py` (slow, with PyBaMM):**
- Run NMC_5AH with **DFN** model, CC discharge 1A for 60s
- Assert at least 5 of the new signals are present in the result (electrode potentials, concentrations, exchange current densities)
- Assert `NEGATIVE_OCV` values are in a physically reasonable range (0-1V for graphite vs Li/Li+)
- Assert `POSITIVE_OCV` values are in reasonable range (3-5V for NMC vs Li/Li+)
- Run same scenario with **SPM** — confirm no crash, and that electrolyte-only signals are simply absent

## OUTPUT

- Working code in `types/signal.py`, `backend/pybamm_signal.py`, and test files
- A report in `/docs/reports/B_deep_electrochemical_observability.md` including:
  - What was done
  - Key decisions (why x-averaged, why graceful skip)
  - Issues encountered
  - Next improvements (spatial profiles for DFN, phase-space plots)

## EDUCATION

In the report, briefly explain:
- **Terminal voltage decomposition**: V_cell = U_pos(θ_pos) - U_neg(θ_neg) - η_pos - η_neg - ΔΦ_e where U is OCV, η is reaction overpotential, ΔΦ_e is electrolyte potential drop
- **Butler-Volmer kinetics**: exchange current density j₀ controls reaction rate; depends on concentration and temperature. Overpotential η drives the reaction via sinh(Fη/2RT)
- **Stoichiometry vs SOC**: electrode stoichiometry θ = c_s/c_s,max is the local "filling fraction" of lithium in the particle. Cell SOC is a weighted combination of both electrodes.
- **Why x-averaged**: SPM and SPMe have no spatial electrode resolution — only x-averaged values make sense. DFN could give position-resolved profiles, but x-averaged is the universal comparable quantity.
