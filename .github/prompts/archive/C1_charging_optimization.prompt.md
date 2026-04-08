---
mode: agent
description: Add charging optimization tool
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add a charging optimization tool that finds the best CC-CV parameters for minimal aging.

## TASK
Implement **optimize_charging** — sweep charge parameters to find the best charge time vs aging tradeoff.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: degradation support (SEI, lithium plating already available in `core/degradation.py`)
- The existing `core/parameter_sweep.py` has sweep infrastructure. The `SensitivityService` in `core/application_services.py` already runs parameter variations
- The `core/investigation_tools.py` has `BatchSimulationConfig` for running multiple sims
- Strategy: run a small grid of charge protocols (varying charge current, CV voltage) with degradation enabled, compare charge time vs capacity fade
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `ChargingOptimizer` class in `core/investigation_tools.py`
```python
class ChargingOptimizer:
    """Finds optimal charging parameters balancing speed and aging."""
    
    def optimize(
        self,
        cell: Cell,
        charge_current_range_A: tuple[float, float] = (1.0, 10.0),
        n_points: int = 5,
        target_soc_range: tuple[float, float] = (0.1, 0.8),
        backend: SimulationBackend = None,
    ) -> dict:
        ...
```
- Generate a grid of charge currents linearly spaced in the range
- For each charge current:
  - Build a CC-CV protocol: CC at test current → CV at max voltage → until taper
  - Run a short cycling simulation (5-10 cycles) with SEI degradation enabled
  - Measure: charge time (seconds), capacity fade per cycle
- Return sorted results: list of {charge_current_A, charge_time_s, capacity_fade_per_cycle, score}
- Score = normalize(charge_time) + normalize(aging), lower is better

### 2. Add `optimize_charging()` to AgentAPI
- Signature:
  ```python
  def optimize_charging(
      self,
      preset_name: str,
      target_soc_range: tuple[float, float] = (0.1, 0.8),
      max_charge_time_min: float = 60.0,
      temperature_C: float = 25.0,
  ) -> DualFormatResult
  ```
- Use ChargingOptimizer internally
- Return DualFormatResult with:
  - JSON: optimal_params, all_results (sorted), charge_time_min, estimated_aging_impact
  - Markdown: recommendation with optimal charge current, expected charge time, aging tradeoff table

### 3. Add MCP tool in `mcp_server.py`

### 4. Add tests
- Test ChargingOptimizer produces sorted results
- Test optimize_charging returns valid DualFormatResult
- Test with different presets

### 5. Write clean, minimal code
- Do not over-engineer
- Add comments explaining the optimization strategy

## OUTPUT
- Working code: ChargingOptimizer, optimize_charging API + MCP, tests passing
- A report in `/docs/reports/C1_charging_optimization.md` including:
  - What was done
  - Key decisions (grid search vs optimization, scoring formula)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- CC-CV charging: how it works, why CV phase matters
- The charge speed vs aging tradeoff (higher C-rate = faster but more degradation)
- Lithium plating risk at high charge rates — the key safety constraint
- Why BMS charge current limits are temperature-dependent
