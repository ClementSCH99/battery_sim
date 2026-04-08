---
mode: agent
description: Add pack sizing tool
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add a pack sizing tool that computes series/parallel configuration and pack metrics.

## TASK
Implement **pack_sizing** — given a cell preset and target pack energy, compute optimal S/P configuration, weight, volume, and cost.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Task D1 (enhanced cell presets with weight/volume/cost metadata)
- Cell presets in `core/cell_presets.py` now have physical metadata
- This is an engineering calculation tool, no simulation needed
- Common EV pack configurations: 96S (for ~350V nominal), 108S (for ~400V), with parallel count sized for target energy
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `PackSizer` utility in `core/investigation_tools.py`
```python
class PackSizer:
    """Compute pack configuration from cell specs and requirements."""
    
    def size_pack(
        self,
        cell_preset: CellPreset,
        target_energy_kWh: float,
        voltage_range: tuple[float, float] = (300.0, 400.0),
    ) -> dict:
        """
        Returns:
            n_series, n_parallel, total_cells,
            pack_voltage_nominal_V, pack_capacity_Ah,
            pack_energy_kWh (actual),
            pack_weight_kg, pack_volume_L, pack_cost_usd,
            overhead_weight_kg (estimate 15-20% for casing, BMS, cooling),
            total_system_weight_kg
        """
```
- Logic:
  1. n_series = round(target_voltage_midpoint / cell_nominal_voltage), clamped to voltage_range
  2. n_parallel = ceil(target_energy_kWh * 1000 / (n_series × cell_energy_Wh))
  3. Compute all pack-level metrics from cell values × cell count
  4. Add system overhead: +20% weight for housing/BMS/thermal, +30% volume for gaps/cooling

### 2. Add `pack_sizing()` to AgentAPI
- Signature:
  ```python
  def pack_sizing(
      self,
      preset_name: str,
      target_energy_kWh: float = 60.0,
      voltage_range: tuple[float, float] = (300.0, 400.0),
  ) -> DualFormatResult
  ```
- Return DualFormatResult with:
  - JSON: all PackSizer output fields
  - Markdown: formatted table with pack specs, comparison with industry benchmarks (e.g., "60 kWh pack at 180 Wh/kg is typical for mid-range EV")

### 3. Add MCP tool in `mcp_server.py`

### 4. Add tests
- Test PackSizer math: known cell + target → verify n_series, n_parallel
- Test pack_sizing API returns valid DualFormatResult
- Test edge cases: very small target energy, very narrow voltage range
- Test that actual pack energy >= target energy (PackSizer rounds up)

### 5. Write clean, minimal code
- Do not over-engineer
- Add comments explaining series/parallel topology

## OUTPUT
- Working code: PackSizer, pack_sizing API + MCP, tests passing
- A report in `/docs/reports/D2_pack_sizing.md` including:
  - What was done
  - Key decisions (overhead percentages, rounding strategy)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- Series vs parallel: voltage stacking vs capacity scaling
- Why voltage range is constrained (inverter specifications, safety limits)
- Pack-level overhead: what BMS, thermal system, and housing add to weight/volume
- Industry benchmarks: typical pack energy density for 2024 EVs (150-200 Wh/kg at pack level)
