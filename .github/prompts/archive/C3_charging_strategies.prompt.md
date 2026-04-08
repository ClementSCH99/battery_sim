---
mode: agent
description: Add charging strategy comparison tool
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add a tool to compare different charging strategies on the same cell.

## TASK
Implement **compare_charging_strategies** — compare standard CC-CV, multi-step CC, and gentle charging on the same cell.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Tasks A1 (PowerStep), C1 (charging optimization concepts)
- Protocol system in `core/protocol.py` supports CC, CC-CV, Rest steps
- Degradation models available in `core/degradation.py`
- Strategy: define several charging protocols, run each with degradation, compare charge time vs aging
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add predefined charging strategies in `core/investigation_tools.py`
- Add a `ChargingStrategyBuilder` class or module-level functions:
  ```python
  def build_charging_strategies(cell: Cell) -> dict[str, Protocol]:
      """Return a dict of named charging protocols."""
      capacity = cell.nominal_capacity_Ah
      return {
          "standard_1C": Protocol.cccv(capacity * 1.0, max_voltage, taper),
          "fast_2C": Protocol.cccv(capacity * 2.0, max_voltage, taper),
          "gentle_0.5C": Protocol.cccv(capacity * 0.5, max_voltage, taper),
          "multi_step": build_multi_step_protocol(cell),  # 2C→1.5C→1C→0.5C stepped CC
      }
  ```
- For multi-step CC: start at high current, reduce in steps as SOC increases (approximated with time-based segments)
- Get max_voltage from cell metadata (or use chemistry defaults: LFP=3.65, NMC=4.2, NCA=4.2)

### 2. Add `compare_charging_strategies()` to AgentAPI
- Signature:
  ```python
  def compare_charging_strategies(
      self,
      preset_name: str,
      strategies: list[str] | None = None,  # None = all built-in
      n_cycles: int = 10,
      temperature_C: float = 25.0,
  ) -> DualFormatResult
  ```
- Logic:
  1. Build charging protocols for the given cell
  2. For each strategy, run n_cycles (charge + discharge) with SEI degradation
  3. Extract per strategy: charge_time_min, energy_efficiency, capacity_fade_per_cycle, final_soh
  4. Rank by configurable criteria (default: balance of speed and aging)
- Return DualFormatResult with comparison table and recommendation

### 3. Add MCP tool in `mcp_server.py`

### 4. Add tests
- Test build_charging_strategies produces valid protocols for each chemistry
- Test compare_charging_strategies returns valid DualFormatResult
- Test strategy names are recognized

### 5. Write clean, minimal code
- Do not over-engineer
- Add comments explaining each charging strategy

## OUTPUT
- Working code: charging strategy builder, compare API + MCP, tests passing
- A report in `/docs/reports/C3_charging_strategies.md` including:
  - What was done
  - Key decisions (which strategies, cycle count for comparison)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- CC-CV vs multi-step CC vs pulse charging — how each works
- Why multi-step CC can reduce aging (less time at high voltage under high current)
- Energy efficiency during charging: where do losses come from (ohmic, thermodynamic)
- How BMS implements different charging strategies in production vehicles
