---
mode: agent
description: Add drive cycle profiles and DriveProfile step type
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add EV drive cycle support to battery_sim.

## TASK
Implement **DriveProfile** step type and a **drive cycle library** with standard EV profiles (WLTP, US06, UDDS).

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Task A1 (PowerStep must exist in `core/protocol.py`)
- A drive cycle is a time-varying power demand. We discretize it into a sequence of short constant-power steps (PowerStep from A1)
- Standard cycles (WLTP, US06, UDDS) are stored as normalized power profiles and scaled at runtime by vehicle/pack parameters
- Keep code simple and modular

## INSTRUCTIONS

### 1. Create `core/drive_cycles.py` (new module)
- Define a `DriveCycleProfile` dataclass: `name: str`, `time_s: list[float]`, `power_normalized: list[float]`, `description: str`
- `power_normalized` is power demand as fraction of peak power (0.0 to 1.0)
- Add built-in profiles as module-level constants:
  - `WLTP_CLASS3`: ~1800s, 4 phases (low/medium/high/extra-high), representative of European mixed driving
  - `US06`: ~600s, aggressive acceleration profile
  - `UDDS`: ~1370s, urban stop-and-go
- Use simplified but realistic shapes (10-20 time points per cycle capturing key power transitions, not full 1Hz data)
- Add `get_drive_cycle(name: str) -> DriveCycleProfile` lookup function
- Add `list_drive_cycles() -> list[str]` function

### 2. Add `scale_drive_cycle()` utility
- Signature: `scale_drive_cycle(profile: DriveCycleProfile, vehicle_mass_kg: float, peak_power_kW: float) -> list[tuple[float, float]]`
- Returns list of `(power_W, duration_s)` segments
- Scaling: `power_W = power_normalized * peak_power_kW * 1000`
- Duration from time differences between consecutive time points

### 3. Add `DriveProfile` step in `core/protocol.py`
- Dataclass with `segments: list[tuple[float, float]]` (power_W, duration_s pairs)
- `duration_s()` returns sum of all segment durations
- Add `Protocol.drive_cycle()` class method:
  ```python
  Protocol.drive_cycle(
      cycle_name: str,
      vehicle_mass_kg: float = 1800.0,
      peak_power_kW: float = 150.0,
  ) -> Protocol
  ```
- Internally: loads cycle, scales it, creates a sequence of PowerStep instances

### 4. Add tests
- Test DriveCycleProfile creation and lookup
- Test scale_drive_cycle produces correct power values
- Test Protocol.drive_cycle("WLTP") creates a valid protocol with PowerStep steps
- Test unknown cycle name raises appropriate error

### 5. Write clean, minimal code
- Do not over-engineer
- Add useful comments

## OUTPUT
- Working code: drive_cycles.py, DriveProfile in protocol.py, tests passing
- A report in `/docs/reports/A2_drive_cycles.md` including:
  - What was done
  - Key decisions (normalized profiles, scaling approach, discretization)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- What drive cycles are and why they matter for EV battery sizing
- WLTP vs US06 vs UDDS — what each represents
- The tradeoff between time resolution and simulation speed
