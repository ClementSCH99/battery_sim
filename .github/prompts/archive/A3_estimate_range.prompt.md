---
mode: agent
description: Add estimate_range API tool and MCP endpoint
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add an EV range estimation tool to the AgentAPI and expose it via MCP.

## TASK
Implement **estimate_range** — given a cell preset, pack configuration, and drive cycle, estimate range in km.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Tasks A1 (PowerStep) and A2 (drive cycles)
- AgentAPI lives in `core/agent_api.py`, returns `DualFormatResult` (JSON + Markdown)
- MCP server lives in `mcp_server.py`, wraps AgentAPI methods
- Range estimation: run a simulation with the drive cycle protocol, measure how many cycles complete before voltage cutoff, multiply by cycle distance
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add pack configuration helper
- In `core/agent_api.py` (or a small helper), add a `PackConfig` dataclass:
  - `n_series: int`, `n_parallel: int`
  - Computed properties: `pack_voltage_V` (= n_series × cell_nominal_voltage), `pack_capacity_Ah` (= n_parallel × cell_capacity)
  - `pack_energy_kWh` property

### 2. Add `estimate_range()` to AgentAPI
- Signature:
  ```python
  def estimate_range(
      self,
      preset_name: str,
      cycle_name: str = "WLTP",
      n_series: int = 96,
      n_parallel: int = 4,
      vehicle_mass_kg: float = 1800.0,
      peak_power_kW: float = 150.0,
      temperature_C: float = 25.0,
  ) -> DualFormatResult
  ```
- Logic:
  1. Load cell preset
  2. Build drive cycle protocol via `Protocol.drive_cycle()`
  3. Calculate pack energy (kWh)
  4. Run simulation of one drive cycle
  5. Measure energy consumed per cycle from simulation result
  6. Estimate cycles possible = pack_energy / energy_per_cycle
  7. Calculate range = cycles × cycle_distance_km (derive from cycle metadata or use standard values: WLTP=23.3km, US06=12.9km, UDDS=12.0km)
- Return DualFormatResult with JSON data (range_km, pack_energy_kWh, energy_per_cycle_kWh, cycles_possible) and Markdown summary

### 3. Add MCP tool in `mcp_server.py`
- Expose `estimate_range` with all parameters
- Follow existing pattern (call api method, return `_result_json()`)

### 4. Add tests
- Test estimate_range returns valid DualFormatResult with expected keys
- Test with different presets and drive cycles
- Test edge case: very small pack → very short range

### 5. Write clean, minimal code
- Do not over-engineer
- Add useful comments

## OUTPUT
- Working code: estimate_range in agent_api.py, MCP tool in mcp_server.py, tests passing
- A report in `/docs/reports/A3_estimate_range.md` including:
  - What was done
  - Key decisions (range calculation method, pack-level simplification)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- How EV range is estimated in practice (pack energy ÷ energy consumption per km)
- Why series/parallel configuration matters (voltage window for inverter, capacity for range)
- Limitations of single-cell simulation extrapolated to pack level
