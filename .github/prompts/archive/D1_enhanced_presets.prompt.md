---
mode: agent
description: Enhance cell presets with physical metadata and improve compare_presets
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: enhance cell presets with EV-relevant metadata and improve the comparison tool.

## TASK
Implement **enhanced cell presets** with weight, volume, cost metadata and **improved compare_presets** with EV-specific metrics.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Cell presets live in `core/cell_presets.py` — already has LFP, NMC, NCA presets with metadata dict
- `compare_presets()` in `core/agent_api.py` already works but only compares simulation metrics
- Goal: add physical metadata (weight, volume, cost) to presets and include EV-relevant metrics in comparison (energy density, cost per kWh, C-rate capability)
- Keep code simple and modular

## INSTRUCTIONS

### 1. Enhance `CellPreset` in `core/cell_presets.py`
- Add fields to CellPreset dataclass:
  ```python
  weight_kg: float = 0.0          # Cell weight
  volume_L: float = 0.0           # Cell volume in liters
  cost_usd: float = 0.0           # Estimated cell cost
  max_charge_c_rate: float = 1.0  # Max recommended charge C-rate
  max_discharge_c_rate: float = 2.0  # Max recommended discharge C-rate
  ```
- Fill in realistic values for all existing presets:
  - LFP_5AH: ~0.1kg, ~0.05L, ~$3, 1C/3C
  - NMC_5AH: ~0.07kg, ~0.035L, ~$4, 1C/3C
  - NCA_5AH: ~0.065kg, ~0.032L, ~$4.5, 0.7C/3C
  - (Scale proportionally for 10AH variants)
- Add computed properties to CellPreset:
  - `energy_density_Wh_per_kg`: energy / weight
  - `energy_density_Wh_per_L`: energy / volume
  - `cost_per_kWh`: cost / energy × 1000

### 2. Enhance `compare_presets()` in AgentAPI
- Add EV-specific metrics to comparison output:
  - Gravimetric energy density (Wh/kg)
  - Volumetric energy density (Wh/L)
  - Cost per kWh ($/kWh)
  - Max charge/discharge C-rate
  - Estimated cycle life (from preset metadata)
- Include a `best_for` summary: which preset wins on which metric
- Update both JSON and Markdown output

### 3. Add Ragone data generation
- Add a helper method `_ragone_data(preset_names)` that computes power density vs energy density for each preset
- Include in compare_presets output when 2+ presets are compared

### 4. Add tests
- Test enhanced CellPreset computed properties
- Test compare_presets includes new metrics in output
- Test Ragone data generation

### 5. Write clean, minimal code
- Do not over-engineer

## OUTPUT
- Working code: enhanced presets, improved compare_presets, tests passing
- A report in `/docs/reports/D1_enhanced_presets.md` including:
  - What was done
  - Key decisions (metadata values sourcing, which metrics matter most)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- Gravimetric vs volumetric energy density — why both matter for EV design
- Ragone plots: what they show and how to read them
- Cell cost breakdown: what drives $/kWh for different chemistries
- Why C-rate capability varies by chemistry (ionic conductivity, diffusion coefficients)
