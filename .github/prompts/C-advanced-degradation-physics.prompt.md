## ROLE

You are a senior Python engineer, battery degradation specialist, and mentor.
You understand SEI growth mechanisms, lithium plating thermodynamics, and mechanical degradation in lithium-ion cells at a fundamental level.

## GOAL

Execute this task end-to-end: expand the degradation configuration from simple boolean flags to full sub-model selectors, exposing PyBaMM's rich degradation physics for aging studies.

## TASK

Implement **Phase C — Advanced Degradation Physics**

## CONTEXT

- Project: PyBaMM battery assistant API (`battery_sim`)
- Currently `DegradationConfig` has 3 booleans: `sei_growth`, `lithium_plating`, `active_material_loss`
- The backend hardcodes one variant per mechanism: `"ec reaction limited"` for SEI, `"irreversible"` for plating, `"stress-driven"` for AM loss
- PyBaMM supports multiple sub-model variants for each mechanism, plus cross-coupling (SEI on cracks, particle mechanics)
- Backward compatibility is mandatory: `DegradationConfig(sei_growth=True)` must keep working exactly as before

## INSTRUCTIONS

### 1. Expand `core/degradation.py`

Replace the simple dataclass with a richer one that supports both legacy booleans and new sub-model selectors:

```python
@dataclass(frozen=True)
class DegradationConfig:
    # --- Legacy boolean API (backward compatible) ---
    sei_growth: bool = False
    lithium_plating: bool = False
    active_material_loss: bool = False

    # --- Sub-model selectors (new, take priority when set) ---
    sei_model: Optional[str] = None
    # Valid: "ec reaction limited", "solvent-diffusion limited",
    #        "electron-migration limited", "interstitial-diffusion limited",
    #        "reaction limited"

    lithium_plating_model: Optional[str] = None
    # Valid: "irreversible", "reversible", "partially reversible"

    am_loss_model: Optional[str] = None
    # Valid: "stress-driven", "reaction-driven", "stress and reaction-driven"

    # --- Cross-coupling options ---
    sei_on_cracks: bool = False
    # When True + particle cracking active: SEI grows on freshly exposed surfaces

    particle_mechanics: Optional[str] = None
    # Valid: None, "swelling only", "swelling and cracking"
```

**Resolution logic** (add a method `resolve()`):
- If `sei_model` is set explicitly → use it
- Else if `sei_growth=True` → use `"ec reaction limited"` (backward compat)
- Same pattern for plating and AM loss
- `validate()` should check that sub-model strings are in the allowed set

### 2. Update `backend/pybamm_backend.py` — `_build_model()`

Replace the current boolean-to-option translation with a call to `degradation.resolve()` or equivalent logic:

```python
if degradation is not None:
    resolved = degradation.resolve()  # or inline the logic
    if resolved.sei:
        options["SEI"] = resolved.sei
    if resolved.lithium_plating:
        options["lithium plating"] = resolved.lithium_plating
    if resolved.am_loss:
        options["loss of active material"] = resolved.am_loss
    if degradation.sei_on_cracks:
        options["SEI on cracks"] = "true"
    if degradation.particle_mechanics:
        options["particle mechanics"] = degradation.particle_mechanics
```

### 3. Add new degradation signals in `types/signal.py`

```python
SEI_FILM_RESISTANCE = "sei_film_resistance"
LITHIUM_PLATING_THICKNESS = "lithium_plating_thickness"
NEGATIVE_PARTICLE_CRACK_LENGTH = "negative_particle_crack_length"
```

### 4. Map new signals in `backend/pybamm_signal.py`

```python
Signal.SEI_FILM_RESISTANCE: (
    "X-averaged SEI film resistance [ohm.m2]", "Ω·m²"),
Signal.LITHIUM_PLATING_THICKNESS: (
    "X-averaged lithium plating thickness [m]", "m"),
Signal.NEGATIVE_PARTICLE_CRACK_LENGTH: (
    "X-averaged negative particle crack length [m]", "m"),
```

### 5. Write tests

**In `tests/test_domain.py` (fast, no PyBaMM):**
- `DegradationConfig(sei_growth=True)` resolves to `"ec reaction limited"` — backward compat
- `DegradationConfig(sei_model="solvent-diffusion limited")` resolves correctly
- `DegradationConfig(sei_model="invalid")` raises validation error
- `DegradationConfig(sei_model="ec reaction limited", sei_growth=True)` — explicit wins, no conflict
- `DegradationConfig(particle_mechanics="swelling and cracking", sei_on_cracks=True)` — valid
- `any_enabled()` returns True when any sub-model is set

**In `tests/test_smoke.py` (slow, with PyBaMM):**
- Run NMC_5AH cycling (3 cycles) with `sei_model="solvent-diffusion limited"` on SPMe
- Assert `Signal.SEI_THICKNESS` is present and monotonically increasing
- Run with `lithium_plating_model="reversible"` — confirm simulation completes
- Run with `particle_mechanics="swelling and cracking"` — confirm no crash

## OUTPUT

- Working code in `core/degradation.py`, `backend/pybamm_backend.py`, `types/signal.py`, `backend/pybamm_signal.py`, and test files
- A report in `/docs/reports/C_advanced_degradation_physics.md` including:
  - What was done
  - Key decisions (resolution logic, backward compat strategy)
  - Issues encountered (some sub-model combinations may not work with all models)
  - Next improvements (calendar aging, capacity fade prediction)

## EDUCATION

In the report, briefly explain:
- **SEI growth mechanisms**: The Solid Electrolyte Interphase forms on the anode surface as electrolyte decomposes. Different rate-limiting steps (EC reaction, solvent diffusion, electron migration) produce different growth kinetics (√t law for diffusion-limited, linear for reaction-limited)
- **Reversible vs irreversible lithium plating**: At low temperatures or high charge rates, lithium plates on the anode instead of intercalating. Irreversible plating is permanent capacity loss; reversible plating means some lithium re-intercalates during rest (partial recovery)
- **Particle mechanics**: During lithiation/delithiation, electrode particles swell and contract. This mechanical stress can cause cracks, exposing fresh surface to electrolyte. `"SEI on cracks"` models SEI growth on these new surfaces — a coupled degradation feedback loop
- **Why sub-model selection matters for EV**: An EV battery ages differently in cold climates (plating-dominated) vs hot climates (SEI-dominated). Having the right sub-model is critical for accurate lifetime prediction
