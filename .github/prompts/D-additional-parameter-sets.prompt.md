## ROLE

You are a senior Python engineer, battery characterization specialist, and mentor.
You know the major PyBaMM parameter sets by heart and understand which cell parameterizations are validated for which use cases (general simulation, aging studies, thermal analysis).

## GOAL

Execute this task end-to-end: add real, peer-reviewed cell parameterizations from PyBaMM's parameter library to expand the chemistry coverage beyond the current Marquis2019/Chen2020 baseline.

## TASK

Implement **Phase D — Additional Validated Parameter Sets**

## CONTEXT

- Project: PyBaMM battery assistant API (`battery_sim`)
- Currently 2 parameter sets used: `Marquis2019` (LFP) and `Chen2020` (NMC, NCA, LCO, LMNO)
- Parameter sets are resolved in `backend/parameter_mapper.py` via chemistry string → PyBaMM parameter set name
- Cell presets are defined in `core/cell_presets.py` with electrical, thermal, and geometry specs + metadata
- PyBaMM ships many more validated parameter sets. The goal is to expose the most EV-relevant ones.
- Existing presets must remain unchanged.

## INSTRUCTIONS

### 1. Research available PyBaMM parameter sets

Before implementing, verify which parameter sets are actually available in the installed PyBaMM version. Run:

```python
import pybamm
# Try loading each parameter set to confirm availability
for name in ["Ecker2015", "OKane2022", "Mohtat2020", "Ai2020", "Chen2020"]:
    try:
        p = pybamm.ParameterValues(name)
        print(f"✓ {name} — {p['Nominal cell capacity [A.h]']} Ah")
    except Exception as e:
        print(f"✗ {name} — {e}")
```

Only implement presets for parameter sets that actually load. Adapt the plan if some are unavailable.

### 2. Add mappings in `backend/parameter_mapper.py`

Add new chemistry keys that map to the validated parameter sets. Use a naming convention that identifies the source:

```python
_CHEMISTRY_PARAMETER_SETS = {
    # Existing
    "LFP": "Marquis2019",
    "NMC": "Chen2020",
    "NCA": "Chen2020",
    "LCO": "Chen2020",
    "LMNO": "Chen2020",
    # New validated sets
    "NMC-ECKER": "Ecker2015",        # Ecker et al. 2015, NMC/graphite 18650
    "NMC-OKANE": "OKane2022",        # O'Kane et al. 2022, designed for degradation
    "NMC-MOHTAT": "Mohtat2020",      # Mohtat et al. 2020, pouch cell
    "NMC811-AI": "Ai2020",           # Ai et al. 2020, LGM50 cylindrical
}
```

Add variant mappings as needed (e.g., `"NMC811"` → `"NMC811-AI"`).

### 3. Create new Cell presets in `core/cell_presets.py`

For each new parameter set, create a preset with realistic cell specifications. Extract the actual values from the PyBaMM parameter set where possible (capacity, voltage range, thermal properties). Include rich metadata:

```python
"NMC_ECKER_18650": Cell(
    chemistry="NMC-ECKER",
    nominal_capacity_Ah=...,      # from Ecker2015 params
    nominal_voltage_V=...,
    metadata={
        "source": "Ecker et al., J. Electrochem. Soc., 2015",
        "cell_format": "18650 cylindrical",
        "designed_for": "general characterization",
        "anode": "graphite",
        "cathode": "NMC",
    }
),
```

Create these presets (adjust based on what's actually available):
- `NMC_ECKER_18650` — Ecker2015
- `NMC_OKANE_AGING` — OKane2022 (metadata: "designed_for": "degradation studies")
- `NMC_MOHTAT_POUCH` — Mohtat2020
- `NMC811_AI_LGM50` — Ai2020 (NMC811/graphite, LG M50 5Ah cylindrical — very popular EV cell)

### 4. Write tests

**In `tests/test_domain.py` (fast, no PyBaMM):**
- All new presets load via `Cell.preset("NMC_ECKER_18650")` without error
- Each preset has valid chemistry, positive capacity and voltage
- Each preset has `"source"` in metadata

**In `tests/test_smoke.py` (slow, with PyBaMM):**
- For each new preset: run SPM CC discharge at 1A for 60s
- Assert simulation completes and `Signal.VOLTAGE` has data
- Assert voltage is in physically reasonable range (2.0-5.0V)

### 5. Important research notes

- **Always verify the exact parameter set string** that PyBaMM expects. Some versions use different naming (e.g., `"Ecker2015"` vs `"Ecker2015_graphite_halfcell"`).
- **Extract real cell specs** from the parameter set: `pv["Nominal cell capacity [A.h]"]`, `pv["Lower voltage cut-off [V]"]`, `pv["Upper voltage cut-off [V]"]`
- If a parameter set doesn't have thermal parameters, note it in metadata: `"thermal_data": "limited"`
- If a parameter set is specifically designed for degradation (OKane2022), note it — it includes SEI, plating, and AM loss parameters that others don't

## OUTPUT

- Working code in `backend/parameter_mapper.py`, `core/cell_presets.py`, and test files
- A report in `/docs/reports/D_additional_parameter_sets.md` including:
  - What was done
  - Which parameter sets were available and which weren't
  - Key cell specifications extracted from each parameter set
  - Issues encountered
  - Next improvements (custom parameter fitting, user-supplied parameter sets)

## EDUCATION

In the report, briefly explain:
- **What a PyBaMM parameter set contains**: A complete set of physical parameters for a specific real cell — electrode thermodynamics (OCV curves via functions), kinetics (exchange current density functions), transport (diffusivity, conductivity), geometry (particle radius, electrode thickness, porosity), and thermal properties. Typically 50-100+ parameters.
- **Why validated parameter sets matter**: Parameters are interdependent. Mixing an NMC cathode OCV curve with an LFP anode diffusivity produces nonphysical results. Validated sets come from careful experimental characterization of a specific cell.
- **Ecker2015 vs Chen2020 vs OKane2022**: Ecker2015 was one of the first complete open-source parameterizations (18650 NMC). Chen2020 parameterized the LGM50 cell with improved methodology. OKane2022 extended Chen2020 with full degradation sub-model parameters for long-term aging prediction.
- **The LGM50 cell**: LG's M50 (INR21700-M50T) is a 5Ah NMC811/SiC cylindrical cell widely used in EV packs (Tesla, BMW). It's the most-studied cell in PyBaMM literature.
