---
mode: agent
description: Add calendar aging and lifetime prediction
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add calendar aging support and a lifetime prediction tool.

## TASK
Implement **calendar aging** in the degradation model and a **predict_lifetime** AgentAPI tool.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Degradation config lives in `core/degradation.py` — already supports SEI, lithium plating, active material loss
- PyBaMM has calendar aging models: SEI growth during rest is inherently modeled when SEI is enabled and the cell sits at rest
- The idea: simulate N representative cycles with degradation enabled, measure capacity fade trend, extrapolate to 80% SOH (end-of-life)
- Cycling analysis in `core/application_services.py` already has `CyclingAnalyzer` with per-cycle metrics
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `UsageProfile` dataclass in `core/degradation.py`
```python
@dataclass(frozen=True)
class UsageProfile:
    daily_km: float = 40.0                # Average daily driving distance
    daily_charge_cycles: float = 1.0      # How many charge cycles per day
    storage_temperature_C: float = 25.0   # Temperature when parked
    storage_soc: float = 0.5              # Typical SOC when parked
    fast_charge_ratio: float = 0.1        # Fraction of charges that are fast (DC)
```

### 2. Extend `DegradationConfig` with calendar aging flag
- Add `calendar_aging: bool = False` field
- When True AND sei_growth is True, calendar aging is modeled (SEI grows during rest periods)
- Add `storage_temperature_C: float = 25.0` and `storage_soc: float = 0.5` to config
- Update `any_enabled()` to include calendar_aging

### 3. Add `predict_lifetime()` to AgentAPI
- Signature:
  ```python
  def predict_lifetime(
      self,
      preset_name: str,
      usage_profile: dict | None = None,
      n_representative_cycles: int = 50,
      temperature_C: float = 25.0,
  ) -> DualFormatResult
  ```
- Logic:
  1. Load cell preset
  2. Build a representative cycling protocol (charge CC-CV + rest + discharge CC + rest) × n_representative_cycles
  3. Enable degradation (SEI + calendar aging)
  4. Run simulation, extract capacity per cycle from cycling analysis
  5. Fit a linear or sqrt(t) trend to capacity fade
  6. Extrapolate to 80% capacity retention → number of cycles to EOL
  7. Convert cycles to years using usage_profile (cycles_per_day → days → years)
- Return DualFormatResult with: estimated_years, estimated_cycles, capacity_fade_rate_per_cycle, capacity_trajectory (list of {cycle, capacity_retention})

### 4. Add MCP tool in `mcp_server.py`
- Expose `predict_lifetime` following existing patterns

### 5. Add tests
- Test UsageProfile creation and defaults
- Test DegradationConfig with calendar_aging enabled
- Test predict_lifetime returns valid result with expected keys
- Test extrapolation math (given known fade rate, verify year estimate)

### 6. Write clean, minimal code
- Do not over-engineer
- Add useful comments

## OUTPUT
- Working code: calendar aging in degradation.py, predict_lifetime in agent_api.py, MCP tool, tests passing
- A report in `/docs/reports/B1_lifetime_prediction.md` including:
  - What was done
  - Key decisions (representative cycling approach, extrapolation method)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- Calendar aging vs cycle aging — what each is and why both matter
- SEI layer growth: the dominant calendar aging mechanism
- Arrhenius relationship: why temperature accelerates aging exponentially
- Why we use representative cycles + extrapolation instead of simulating 3000+ real cycles
