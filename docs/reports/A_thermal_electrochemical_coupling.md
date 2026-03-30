# Phase A — Thermal-Electrochemical Coupling

**Date:** 2026-03-29

## What was done

Implemented thermal-electrochemical coupling so simulations can model real heat generation and temperature feedback into battery kinetics and transport.

### Changes by file

| File | Change |
|------|--------|
| `core/environment.py` | Added `thermal_model` field (`Optional[str]`, default `None`). Validation rejects unknown values. Backward compatible: convection without explicit thermal_model still works (backend auto-promotes to `"lumped"`). |
| `types/signal.py` | Added 4 new `Signal` enum members: `IRREVERSIBLE_HEAT`, `REVERSIBLE_HEAT`, `OHMIC_HEAT`, `CELL_TEMPERATURE`. |
| `backend/pybamm_signal.py` | Mapped new signals to PyBaMM variable names. Added aliases for `CELL_TEMPERATURE` (covers `X-averaged`, `Cell temperature`, `Volume-averaged` variants). |
| `backend/pybamm_backend.py` | `_build_model()` now always sets `options["thermal"]` explicitly. `_build_parameters()` always sets `"Initial temperature [K]"`. `_extract_result()` applies K→°C conversion for both `TEMPERATURE` and `CELL_TEMPERATURE`. |
| `core/api_schema.py` | Added `_SIGNAL_METADATA` entries for the 4 new signals. |
| `tests/test_domain.py` | 4 new tests: valid lumped, valid x-full, invalid thermal_model rejected, backward compat with convection only. |
| `tests/test_smoke.py` | 2 new PyBaMM-backed tests: lumped thermal produces temperature rise + non-zero irreversible heat; isothermal vs thermal voltage curves differ. |

## Key decisions

- **`thermal_model` defaults to `None`, not `"isothermal"`:** This preserves backward compatibility. `None` means "not explicitly chosen" — the backend resolves it to `"isothermal"` unless convection is set, in which case it auto-promotes to `"lumped"`. Existing code that sets `convection_W_per_m2K` without knowing about `thermal_model` continues to work identically.

- **Always set `options["thermal"]` explicitly:** Even for isothermal, we pass `"isothermal"` to PyBaMM rather than relying on its default. Explicit is better than implicit.

- **Always set `"Initial temperature [K]"`:** This ensures the thermal model starts at the user-specified ambient temperature rather than PyBaMM's built-in default (typically 298.15 K).

- **K→°C conversion for `CELL_TEMPERATURE`:** Same pattern as the existing `TEMPERATURE` signal. Users think in °C; PyBaMM works in K.

- **`CELL_TEMPERATURE` is separate from `TEMPERATURE`:** `TEMPERATURE` maps to `"Cell temperature [K]"` (the existing signal). `CELL_TEMPERATURE` maps to `"X-averaged cell temperature [K]"` — the volume-averaged value that lumped and distributed thermal models produce. Both are exposed because they can differ in spatially-resolved models.

## Issues encountered

None. The implementation was straightforward given PyBaMM's built-in thermal model support.

## Educational notes

### Why thermal feedback matters

At high C-rates, Joule heating and entropic heat raise the cell temperature significantly. Temperature changes affect:
- **Diffusivity** — lithium diffusion in solid and electrolyte phases is Arrhenius-dependent
- **Ionic conductivity** — electrolyte conductivity changes with temperature
- **Reaction kinetics** — Butler-Volmer exchange current density is temperature-dependent

Isothermal simulations ignore these effects and overestimate performance at high rates. Thermal coupling is essential for realistic predictions above ~1C.

### Lumped vs distributed thermal models

- **Isothermal** (`"isothermal"`): No thermal equation solved. Cell temperature is constant. Fastest, valid for low C-rates or well-cooled cells.
- **Lumped** (`"lumped"`): Single temperature for the whole cell. Solves one ODE for energy balance. Good for pouch and prismatic cells where internal temperature gradients are small. The best accuracy/speed trade-off for most applications.
- **X-lumped** (`"x-lumped"`): Temperature varies across the cell thickness (through-plane) but is uniform in-plane. Good for thick electrode stacks.
- **X-full** (`"x-full"`): Full spatial temperature resolution across electrode thickness. Most accurate for thick cells with significant through-plane gradients. Slowest.

### Heat generation decomposition

Total heat = irreversible + reversible + ohmic:
- **Irreversible heat** — Overpotential losses from the Butler-Volmer reaction (activation polarization). Always positive. Dominant at high C-rates.
- **Reversible heat** — Entropic contribution from the temperature dependence of the open-circuit voltage (∂OCV/∂T). Can be positive or negative depending on SOC. Significant in LFP cells.
- **Ohmic heat** — I²R losses in the electrolyte and solid-phase conductors. Proportional to current squared.

## Next improvements

- **Thermal runaway detection:** Monitor for temperature exceeding safe thresholds and flag in `SimulationError`.
- **Pack-level thermal:** Model multi-cell thermal interactions (cell-to-cell conduction, shared cooling).
- **Cooling strategies:** Support active cooling profiles (time-varying convection coefficient).
- **Thermal parameter presets:** Ship realistic thermal properties (density, specific heat, thermal conductivity) per chemistry preset.
