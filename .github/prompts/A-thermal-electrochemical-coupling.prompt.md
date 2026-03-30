## ROLE

You are a senior Python engineer, electrochemist, and mentor.
You have deep knowledge of PyBaMM's thermal sub-models and heat generation mechanisms in lithium-ion batteries.

## GOAL

Execute this task end-to-end: implement thermal-electrochemical coupling so simulations can model real heat generation and temperature feedback into battery kinetics and transport.

## TASK

Implement **Phase A — Thermal-Electrochemical Coupling**

## CONTEXT

- Project: PyBaMM battery assistant API (`battery_sim`)
- Currently, thermal is only activated when `convection_W_per_m2K` is set on `Environment`. There is no explicit thermal model selector, no heat decomposition signals, and no initial temperature setting.
- PyBaMM supports 4 thermal models: `"isothermal"`, `"lumped"`, `"x-lumped"`, `"x-full"` — passed via `options["thermal"]` when building the model.
- Architecture rule: domain objects in `core/` must remain backend-agnostic. PyBaMM-specific translation happens only in `backend/`.
- All existing tests must keep passing (backward compatibility is mandatory).

## INSTRUCTIONS

### 1. Extend `core/environment.py`

Add a `thermal_model` field to `Environment`:
- Type: `Optional[str]`, default `None` (which means `"isothermal"`)
- Accepted values: `"isothermal"`, `"lumped"`, `"x-lumped"`, `"x-full"`
- Validate in `validate()`: reject unknown values
- When `convection_W_per_m2K` is provided but `thermal_model` is `None`, auto-promote to `"lumped"` (preserve current behavior)

### 2. Add new thermal signals in `types/signal.py`

Add these entries to the `Signal` enum:
```
IRREVERSIBLE_HEAT = "irreversible_heat"
REVERSIBLE_HEAT = "reversible_heat"
OHMIC_HEAT = "ohmic_heat"
CELL_TEMPERATURE = "cell_temperature"  # X-averaged, distinct from ambient
```

### 3. Map new signals in `backend/pybamm_signal.py`

Add to `PYBAMM_SIGNAL_MAP`:
```python
Signal.IRREVERSIBLE_HEAT: ("Irreversible electrochemical heating [W.m-3]", "W/m³"),
Signal.REVERSIBLE_HEAT: ("Reversible heating [W.m-3]", "W/m³"),
Signal.OHMIC_HEAT: ("Ohmic heating [W.m-3]", "W/m³"),
Signal.CELL_TEMPERATURE: ("X-averaged cell temperature [K]", "K"),
```

Add aliases for `CELL_TEMPERATURE`:
```python
Signal.CELL_TEMPERATURE: [
    "X-averaged cell temperature [K]",
    "Cell temperature [K]",
    "Volume-averaged cell temperature [K]",
]
```

### 4. Update `backend/pybamm_backend.py`

**`_build_model()`:**
- Read `environment.thermal_model` (or default to `"isothermal"`)
- If convection is set but thermal_model is None, use `"lumped"`
- Always set `options["thermal"]` explicitly (don't skip for isothermal — explicit is better)

**`_build_parameters()`:**
- Always set `"Initial temperature [K]"` from `environment.temperature_C + 273.15`
- This ensures the thermal model starts at the correct ambient temperature

**`_extract_result()`:**
- `CELL_TEMPERATURE` needs K→°C conversion (same as existing `TEMPERATURE` signal)

### 5. Write tests

**In `tests/test_domain.py` (fast, no PyBaMM):**
- `Environment(temperature_C=25, thermal_model="lumped")` — valid
- `Environment(temperature_C=25, thermal_model="invalid")` — raises on validate()
- `Environment(temperature_C=25, convection_W_per_m2K=10)` without explicit thermal_model — should work (backward compat)

**In `tests/test_smoke.py` (slow, with PyBaMM):**
- Run LFP_5AH CC discharge (60s, 1A) with `thermal_model="lumped"` and `convection_W_per_m2K=10`
- Assert `Signal.CELL_TEMPERATURE` is present and shows temperature > initial
- Assert `Signal.IRREVERSIBLE_HEAT` is present and has non-zero values
- Run same scenario isothermal — assert voltage curve differs from thermal case

## OUTPUT

- Working code in the 4 files listed above + test updates
- A report in `/docs/reports/A_thermal_electrochemical_coupling.md` including:
  - What was done
  - Key decisions (why lumped is the default activation, K→°C conversions)
  - Issues encountered
  - Next improvements (e.g., adding thermal runaway detection, pack-level thermal)

## EDUCATION

In the report, briefly explain:
- **Why thermal feedback matters**: at high C-rates, temperature rise changes diffusivity, conductivity, and reaction kinetics — isothermal simulations overestimate performance
- **Lumped vs distributed thermal models**: lumped = single temperature for the whole cell (fast, good for pouch/prismatic); x-full = temperature gradient across electrode thickness (accurate for thick cells)
- **Heat generation decomposition**: irreversible (Butler-Volmer overpotential losses), reversible (entropic heat from OCV slope), ohmic (I²R in electrolyte and solid phase)
