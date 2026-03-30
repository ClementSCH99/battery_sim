# Phase C — Advanced Degradation Physics

**Date:** 2026-03-29  
**Status:** Complete

## What Was Done

Expanded the degradation configuration from simple boolean flags to full sub-model selectors, exposing PyBaMM's rich degradation physics for aging studies.

### Files Modified

| File | Change |
|------|--------|
| `core/degradation.py` | Replaced simple `DegradationConfig` with richer dataclass supporting sub-model selectors, cross-coupling options, `resolve()` method, and validation |
| `backend/pybamm_backend.py` | Updated `_build_model()` to use `degradation.resolve()` instead of hardcoded boolean-to-string mapping |
| `types/signal.py` | Added 3 new signals: `SEI_FILM_RESISTANCE`, `LITHIUM_PLATING_THICKNESS`, `NEGATIVE_PARTICLE_CRACK_LENGTH` |
| `backend/pybamm_signal.py` | Added PyBaMM variable mappings for new signals |
| `core/api_schema.py` | Added metadata entries for 3 new signals |
| `tests/test_domain.py` | Added `TestDegradationConfig` class with 14 unit tests |
| `tests/test_smoke.py` | Added `TestAdvancedDegradation` class with 3 integration tests |

### New API Surface

```python
DegradationConfig(
    # Legacy booleans (backward compatible)
    sei_growth=True,            # → "ec reaction limited"
    lithium_plating=True,       # → "irreversible"
    active_material_loss=True,  # → "stress-driven"

    # Explicit sub-model selectors (take priority)
    sei_model="solvent-diffusion limited",
    lithium_plating_model="reversible",
    am_loss_model="reaction-driven",

    # Cross-coupling
    sei_on_cracks=True,
    particle_mechanics="swelling and cracking",
)
```

## Key Decisions

### Resolution logic
Explicit sub-model selectors take priority over legacy booleans. If `sei_model` is set, it is used regardless of `sei_growth`. If only `sei_growth=True` is set, it resolves to `"ec reaction limited"` — preserving exact backward compatibility.

### Validation strategy
`validate()` checks all sub-model strings against frozen sets of allowed values, raising `ValueError` with clear messages including the valid options. Validation runs automatically inside `resolve()`.

### Backward compatibility
`DegradationConfig(sei_growth=True)` produces identical PyBaMM options as before. Existing tests pass unchanged.

### `ResolvedDegradation` dataclass
A separate frozen dataclass holds resolved strings, keeping the resolution logic clean and the backend code simple (`resolved.sei` instead of inline if/else chains).

## Issues Encountered

### Parameter set limitations
Some sub-model combinations require parameters not present in the default Chen2020 or Marquis2019 parameter sets:
- **Reversible lithium plating** needs `"Exchange-current density for stripping [A.m-2]"` — absent from Chen2020
- **Particle mechanics (cracking)** needs `"Negative electrode initial crack length [m]"` — absent from Chen2020

These are known PyBaMM limitations. The smoke tests handle this gracefully with `pytest.skip()` when the parameter set is incomplete. Users who need these sub-models should provide custom parameter sets or use parameter sets that include the required values.

### Signal availability
The 3 new signals (`SEI_FILM_RESISTANCE`, `LITHIUM_PLATING_THICKNESS`, `NEGATIVE_PARTICLE_CRACK_LENGTH`) are extracted when PyBaMM makes them available. They are silently skipped when the corresponding sub-model is not active — consistent with how all degradation signals work.

## Education

### SEI growth mechanisms
The Solid Electrolyte Interphase (SEI) forms on the anode surface as electrolyte decomposes during the first few cycles and continues growing throughout the cell's life. Different rate-limiting steps produce different growth kinetics:
- **EC reaction limited:** Growth rate limited by the electrochemical reaction of ethylene carbonate at the SEI surface. Most commonly used default.
- **Solvent-diffusion limited:** Growth limited by diffusion of solvent molecules through the existing SEI layer. Produces √t growth law characteristic of mature SEI.
- **Electron-migration limited:** Growth limited by electron tunneling/migration through the SEI. Relevant for very thin films.
- **Interstitial-diffusion limited:** Growth limited by interstitial diffusion of lithium ions through the SEI lattice.
- **Reaction limited:** Linear growth kinetics — growth rate independent of SEI thickness.

### Reversible vs irreversible lithium plating
At low temperatures or high charge rates, metallic lithium plates on the anode surface instead of intercalating into graphite:
- **Irreversible:** Plated lithium is permanently lost — appears as capacity fade. This is the dominant mode during continuous fast charging.
- **Reversible:** Some plated lithium re-intercalates into graphite during rest periods — partial capacity recovery after rest.
- **Partially reversible:** A fraction of plated lithium is reversible, the rest is permanently lost. Most physically realistic.

### Particle mechanics
During lithiation/delithiation, electrode particles swell and contract. This mechanical cycling causes fatigue:
- **Swelling only:** Particles expand/contract but don't crack. Captures volume change effects on transport.
- **Swelling and cracking:** Stress concentration causes particle fracture, exposing fresh surface area.
- **SEI on cracks:** When enabled together with cracking, new SEI grows on freshly exposed crack surfaces — creating a coupled degradation feedback loop: more cracking → more SEI → more capacity loss → more mechanical stress.

### Why sub-model selection matters for EV
An EV battery ages differently depending on usage and climate:
- **Hot climates:** SEI-dominated aging (accelerated side reactions). Solvent-diffusion limited SEI is most relevant.
- **Cold climates:** Plating-dominated aging (low temperature reduces intercalation kinetics). Reversible plating matters for accurate rest-recovery prediction.
- **High-power cycling:** Mechanical degradation dominates (particle cracking from rapid expansion/contraction).

Having the right sub-model combination is critical for accurate lifetime prediction in specific deployment scenarios.

## Next Improvements

- **Calendar aging:** Add time-dependent degradation models (SEI growth at rest, capacity loss during storage) — important for vehicles that sit idle most of the time.
- **Capacity fade prediction:** Build higher-level tools that run accelerated aging simulations and extrapolate to target lifetime (e.g., "how many cycles to 80% retention?").
- **Custom parameter sets:** Allow users to supply their own degradation parameters, enabling reversible plating and cracking with non-default chemistries.
- **Multi-mechanism coupling:** Expose combined degradation scenarios (SEI + plating + cracking) as investigation presets for common aging profiles (city driving, highway, fast-charge station).
