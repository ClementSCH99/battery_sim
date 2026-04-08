---
mode: agent
description: Add operating window and derating curves tools
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add operating window mapping and derating curve generation tools.

## TASK
Implement **operating_window** and **derating_curves** — map the safe operating region and compute BMS derating tables.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: degradation support in `core/degradation.py`
- Operating window: a grid of SOC × Temperature × C-rate evaluated for aging stress
- Derating curves: max safe C-rate as a function of temperature and SOC — directly usable as BMS lookup tables
- These tools help EV engineers configure BMS limits based on physics rather than guesswork
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `OperatingWindowAnalyzer` class in `core/investigation_tools.py`
- Method `analyze()`:
  - Define grid: SOC=[0.1,0.3,0.5,0.7,0.9], Temp=[0,10,25,40,50]°C, C-rate=[0.5,1.0,2.0,3.0,5.0]
  - For each (SOC, Temp, C-rate) point, run a short simulation (single discharge at that C-rate, from that SOC, at that temperature)
  - Classify each point based on simulation outcome:
    - "safe": simulation completes, voltage stays in bounds, temperature rise < 10°C
    - "caution": simulation completes but temperature rise 10-20°C or voltage close to limits
    - "avoid": simulation fails, voltage violation, or temperature rise > 20°C
  - Return grid data: list of {soc, temperature_C, c_rate, zone, details}
- Keep grid coarse (5×5×5 = 125 points max) for speed

### 2. Add `derating_curves()` method to OperatingWindowAnalyzer
- Extract from operating window data:
  - max_crate_vs_temperature: for each temperature, find highest C-rate still in "safe" zone
  - max_crate_vs_soc: for each SOC, find highest C-rate still in "safe" zone
- Return as lists of {x_value, max_c_rate} suitable for plotting or BMS table generation

### 3. Add `operating_window()` and `derating_curves()` to AgentAPI
- Both return DualFormatResult
- `operating_window()` JSON contains the full grid + summary (% safe, % caution, % avoid)
- `derating_curves()` JSON contains the two curves + recommendations

### 4. Add MCP tools in `mcp_server.py`

### 5. Add tests
- Test OperatingWindowAnalyzer classifies points correctly
- Test derating curves extraction from grid data
- Test API methods return valid DualFormatResult with expected structure
- Test with at least one preset

### 6. Write clean, minimal code
- Grid evaluation can be slow (125 sims). Add a comment noting this. Consider adding a `grid_size` parameter with default "coarse" (3×3×3=27) for testing, "fine" (5×5×5=125) for production
- Do not over-engineer

## OUTPUT
- Working code: OperatingWindowAnalyzer, both API tools + MCP, tests passing
- A report in `/docs/reports/C2_operating_window.md` including:
  - What was done
  - Key decisions (grid resolution, classification thresholds)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- What an operating window is and why BMS engineers need one
- Derating: why BMS limits power at extreme temperatures and SOC levels
- Temperature effects: internal resistance increase at cold, accelerated aging at hot
- How these maps translate directly to BMS lookup tables in production
