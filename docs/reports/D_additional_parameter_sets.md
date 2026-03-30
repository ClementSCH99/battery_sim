# Phase D — Additional Validated Parameter Sets

## Summary

Added four peer-reviewed, validated PyBaMM parameter sets to expand chemistry coverage beyond the Marquis2019/Chen2020 baseline. All four parameter sets were confirmed available in the installed PyBaMM version and pass end-to-end simulation smoke tests.

## What Was Done

### 1. New chemistry mappings (`backend/parameter_mapper.py`)

| Chemistry Key | PyBaMM Parameter Set | Variant Aliases |
|--------------|---------------------|-----------------|
| `NMC-ECKER` | `Ecker2015` | — |
| `NMC-OKANE` | `OKane2022` | — |
| `NMC-MOHTAT` | `Mohtat2020` | — |
| `NMC-AI` | `Ai2020` | — |

### 2. New cell presets (`core/cell_presets.py`)

| Preset Name | Parameter Set | Capacity | Voltage Range | Cell Format |
|------------|--------------|----------|---------------|-------------|
| `NMC_ECKER_KOKAM` | Ecker2015 | 0.156 Ah | 2.5–4.2 V | Kokam pouch (single pair) |
| `NMC_OKANE_AGING` | OKane2022 | 5.0 Ah | 2.5–4.2 V | Cylindrical (LG M50) |
| `NMC_MOHTAT_POUCH` | Mohtat2020 | 5.0 Ah | 2.8–4.2 V | Pouch (NMC532) |
| `NMC_AI_ENERTECH` | Ai2020 | 2.28 Ah | 3.0–4.2 V | Pouch (Enertech) |

### 3. Tests added

- **Domain tests** (`tests/test_domain.py`): Parametrized test verifying all 4 presets load, have positive capacity/voltage, and include `"source"` in metadata.
- **Smoke tests** (`tests/test_smoke.py`): Parametrized test running SPM CC discharge (60 s) for each preset, asserting solver success, voltage data presence, and physical voltage range (2.0–5.0 V).

## Parameter Set Availability

All four target parameter sets loaded successfully:

| Parameter Set | Status | Nominal Capacity | Voltage Range |
|--------------|--------|-----------------|---------------|
| `Ecker2015` | ✓ Available | 0.15625 Ah | 2.5–4.2 V |
| `OKane2022` | ✓ Available | 5.0 Ah | 2.5–4.2 V |
| `Mohtat2020` | ✓ Available | 5.0 Ah | 2.8–4.2 V |
| `Ai2020` | ✓ Available | 2.28 Ah | 3.0–4.2 V |

## Key Cell Specifications

### Ecker2015
- **Cell**: Kokam SLPB 75106100 NMC/graphite pouch cell
- **Capacity**: 0.156 Ah (single electrode pair; full cell has ~48 pairs ≈ 7.5 Ah)
- **Thermal**: Full thermal parameters available (h = 10 W/m²K), thermal data from Zhao et al. 2018
- **Notable**: First complete open-source Li-ion parameterization; reference baseline for validation studies. The low capacity reflects PyBaMM modelling a single electrode sandwich, not the full cell.

### OKane2022
- **Cell**: NMC/graphite cylindrical (extends Chen2020 LGM50)
- **Capacity**: 5.0 Ah
- **Degradation models**: SEI growth, SEI on cracks, lithium plating, active material loss
- **Notable**: Specifically designed for long-term aging simulations; includes all degradation sub-model parameters

### Mohtat2020
- **Cell**: NMC532/graphite pouch cell
- **Capacity**: 5.0 Ah
- **Lower voltage cutoff**: 2.8 V (higher than others)
- **Notable**: Pouch cell geometry; useful for electrode-level design studies

### Ai2020
- **Cell**: Enertech NMC/graphite pouch cell (NOT the LG M50)
- **Capacity**: 2.28 Ah (full cell with 34 electrode pairs)
- **Lower voltage cutoff**: 3.0 V
- **Notable**: Focused on electrochemical thermal-mechanical stress modelling. The 34 parallel electrode pairs are explicitly included in the parameterization. Not to be confused with Chen2020/OKane2022 which parameterize the LG M50.

## Issues Encountered

None. All four parameter sets loaded and simulated successfully on the first attempt.

## Educational Notes

### What a PyBaMM parameter set contains
A complete set of physical parameters for a specific real cell — electrode thermodynamics (OCV curves via interpolation functions), kinetics (exchange current density functions), transport (diffusivity, conductivity as functions of concentration and temperature), geometry (particle radius, electrode thickness, porosity), and thermal properties. Typically 50–100+ parameters that together define the electrochemical behavior of one specific cell.

### Why validated parameter sets matter
Parameters are interdependent. Mixing an NMC cathode OCV curve with an LFP anode diffusivity produces nonphysical results. Validated sets come from careful experimental characterization of a specific cell — EIS, GITT, half-cell testing, calorimetry — ensuring internal consistency. Using a validated set means simulation results can be compared against published experimental data.

### Ecker2015 vs Chen2020 vs OKane2022
- **Ecker2015** was one of the first complete open-source parameterizations (NMC/graphite 18650). It established the methodology for full-cell parameterization in PyBaMM.
- **Chen2020** parameterized the LG M50 cylindrical cell with improved methodology and more comprehensive electrode characterization. It became the de facto standard parameter set.
- **OKane2022** extended Chen2020 with full degradation sub-model parameters (SEI growth kinetics, lithium plating rates, active material loss) for long-term aging prediction. It's the go-to set for calendar and cycle aging studies.

### The LGM50 cell
LG's M50 (INR21700-M50T) is a 5 Ah NMC811/SiC cylindrical cell widely used in EV packs (Tesla Model 3/Y, BMW i-series). It's the most-studied cell in PyBaMM literature, with multiple independent parameterizations (Chen2020, OKane2022, Ai2020). The silicon-graphite composite anode gives higher energy density but introduces mechanical degradation mechanisms not present in pure graphite cells.

## Next Improvements

1. **Custom parameter fitting**: Allow users to supply their own parameter sets from experimental data (e.g., from BioLogic or Arbin cycler output).
2. **User-supplied parameter sets**: Support loading parameter YAML/JSON files at runtime rather than requiring code changes.
3. **Parameter set validation**: Add automated checks that user-supplied parameters are physically consistent (e.g., OCV monotonicity, positive diffusivities).
4. **Additional chemistries**: Add LFP-specific validated sets (e.g., Safari2009) and solid-state electrolyte parameter sets as they become available in PyBaMM.
