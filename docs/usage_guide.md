# battery_sim — Usage Guide

A practical, example-driven guide to battery cell simulation with `battery_sim`.

---

## 1. Installation

```bash
# Clone the repository
git clone <repo-url> && cd battery_sim

# Install in editable mode
pip install -e .

# With dev dependencies (pytest, matplotlib)
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+, PyBaMM, NumPy.

---

## 2. Basic Simulation

Run a single constant-current discharge:

```python
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.backend.pybamm_backend import PyBaMMBackend

# Pick a cell preset
cell = Cell.preset("LFP_5AH")

# 1C discharge for 60 seconds
protocol = Protocol.cc(current_A=5.0, duration_s=60)

# Ambient conditions
env = Environment(temperature_C=25.0)

# Assemble and run
sim = Simulation(cell=cell, model=Model.SPM, protocol=protocol, environment=env)
backend = PyBaMMBackend()
run = sim.run(backend)

# Inspect
print(run.is_successful())           # True
print(run.result.voltage())          # TimeSeries of voltage samples
print(run.result.available_signals())# All extracted signals
print(run.summary())                 # Human-readable diagnostics
```

**What you get back:** A `SimulationRun` containing:
- `result` — signal payload (voltage, current, SOC, temperature, power, energy …)
- `metadata` — timestamp, duration, solver config, convergence status
- `errors` — list of physical / numerical violations (empty if clean)
- `diagnostics` — solver iteration statistics

---

## 3. Cell Presets

Presets are pre-configured cells with realistic parameters for common chemistries.

```python
from battery_sim.core.cell import Cell

# List every preset
print(Cell.list_presets())
# ['LFP_5AH', 'NMC_5AH', 'NCA_5AH', 'LCO_3AH', 'LFP_10AH',
#  'NMC_10AH', 'LMNO_4AH', 'NMC_HE_50AH', 'LFP_HP_20AH']

# Inspect one
cell = Cell.preset("NMC_5AH")
print(cell.chemistry)              # 'NMC'
print(cell.nominal_capacity_Ah)    # 5.0
print(cell.nominal_voltage_V)      # 3.7
print(cell.internal_resistance_Ohm)# 0.07
```

You can also build a custom cell from scratch:

```python
custom = Cell(
    chemistry="Custom_LFP",
    nominal_capacity_Ah=8.0,
    nominal_voltage_V=3.2,
    internal_resistance_Ohm=0.035,
)
```

---

## 4. Protocols

Protocols describe what electrical profile to apply.

### Constant-Current (CC) Discharge

```python
protocol = Protocol.cc(current_A=5.0, duration_s=3600)  # 1C for 1 hour
```

### Rest

```python
rest = Protocol.rest(duration_s=600)  # 10-minute rest
```

### CC-CV Charge

Constant-current phase followed by constant-voltage tapering:

```python
protocol = Protocol.cccv(
    charge_current_A=2.5,     # CC phase at 0.5C
    cutoff_voltage_V=4.2,     # Switch to CV at 4.2 V
    taper_current_A=0.25,     # End CV when current drops to 0.25 A
)
```

### Multi-Step Protocols

Combine protocols with `+`:

```python
charge = Protocol.cccv(charge_current_A=2.5, cutoff_voltage_V=4.2, taper_current_A=0.25)
rest   = Protocol.rest(duration_s=600)
discharge = Protocol.cc(current_A=5.0, duration_s=3600)

full_protocol = charge + rest + discharge
```

### Cycling

Repeat a charge-discharge loop:

```python
protocol = Protocol.cycle(
    charge=Protocol.cccv(charge_current_A=2.5, cutoff_voltage_V=4.2, taper_current_A=0.25),
    discharge=Protocol.cc(current_A=5.0, duration_s=3600),
    n_cycles=10,
    rest_s=600,   # rest between charge/discharge phases
)
```

---

## 5. Comparing Chemistries

### Via the service layer

```python
from battery_sim.core.application_services import ComparisonService
from battery_sim.core.investigation_tools import BatchSimulationConfig
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.backend.pybamm_backend import PyBaMMBackend

backend = PyBaMMBackend()
service = ComparisonService(backend=backend)

config = BatchSimulationConfig(
    protocol=Protocol(steps=[ConstantCurrent(current_A=5.0, _duration_s=3600)]),
    environment=Environment(temperature_C=25.0),
    model=Model.SPM,
    backend=backend,
)

comparison = service.compare_presets(["LFP_5AH", "NMC_5AH", "NCA_5AH"], config)
# comparison['metrics'] is a dict mapping preset → metric dict
```

### Via AgentAPI (higher-level, LLM-friendly)

```python
from battery_sim.core.agent_api import AgentAPI

api = AgentAPI()
result = api.compare_presets(["LFP_5AH", "NMC_5AH", "NCA_5AH"])

print(result.json_data)       # Structured data for programmatic use
print(result.markdown_text)   # Human-readable table + findings
```

> **Learning point:** `DualFormatResult` is the standard return type for all
> AgentAPI methods. It carries both machine-readable JSON and human-readable
> Markdown, so the same call serves an LLM or an engineer.

---

## 6. Sensitivity Analysis

Which parameters affect performance most?

```python
api = AgentAPI()
result = api.sensitivity_analysis(
    preset_name="NMC_5AH",
    parameters=["temperature_C", "nominal_capacity_Ah", "internal_resistance_Ohm"],
)

print(result.json_data)      # Sensitivity coefficients per parameter
print(result.markdown_text)  # Ranked table with interpretation
```

The service varies each parameter across a default range and measures the effect
on peak power, returning a sensitivity coefficient for each parameter.

---

## 7. Feasibility Checking

Before running a long simulation, check physical constraints:

```python
api = AgentAPI()
result = api.check_feasibility("LFP_5AH", temperature_C=25.0)

print(result.json_data["feasible"])            # True / False
print(result.json_data["critical_violations"]) # List of blocking issues
print(result.json_data["warnings"])            # Non-blocking advisories
```

---

## 8. Session Tracking

AgentAPI maintains a session so investigations build on each other:

```python
api = AgentAPI(session_name="BMS Calibration Study")

# Investigation 1
api.compare_presets(["LFP_5AH", "NMC_5AH"])

# Investigation 2
api.sensitivity_analysis(preset_name="NMC_5AH", parameters=["temperature_C"])

# Review what was done
print(api.get_session_summary())     # Chronological report
print(api.get_reasoning_chain())     # Ordered reasoning trace
```

This is especially valuable when an LLM orchestrates multiple steps: the session
provides a human-auditable trail of what was tried and what was learned.

> **Learning point — immutable vs. mutable:**
> Domain objects (`Cell`, `Protocol`, `Simulation`) are immutable (`frozen=True`).
> `AgentAPI` is intentionally stateful: an investigation is a process that
> accumulates findings, where each step builds on prior results.

---

## 9. Plotting

Visualise result signals (requires `matplotlib`):

```python
from battery_sim.core.result_plotting import plot_result
from battery_sim.types.signal import Signal

# After running a simulation
run = sim.run(backend)

# Plot all signals
plot_result(run.result, save_path="all_signals.png")

# Plot specific signals
plot_result(
    run.result,
    signals=[Signal.VOLTAGE, Signal.CURRENT, Signal.SOC],
    save_path="selected_signals.png",
)
```

---

## 10. Advanced: Parameter Sweeps

Systematically explore how a parameter affects results:

```python
from battery_sim.core.parameter_sweep import ParameterSweep
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.core.simulation import Simulation
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment

backend = PyBaMMBackend()
sweep = ParameterSweep(backend)

baseline = Simulation(
    cell=Cell.preset("NMC_5AH"),
    model=Model.SPM,
    protocol=Protocol.cc(current_A=5.0, duration_s=3600),
    environment=Environment(temperature_C=25.0),
)

# Sweep a cell parameter
results = sweep.sweep_cell_parameter(
    baseline_simulation=baseline,
    parameter_name="nominal_capacity_Ah",
    values=[3.0, 5.0, 7.0],
)

for sr in results:
    print(f"Capacity={sr.parameter_value} Ah → "
          f"Peak power = {sr.simulation_result.result.peak_power():.2f} W")
```

```python
# Sweep an environment parameter
results = sweep.sweep_environment_parameter(
    baseline_simulation=baseline,
    parameter_name="temperature_C",
    values=[0, 15, 25, 40],
)

for sr in results:
    print(f"T={sr.parameter_value}°C → "
          f"Min voltage = {sr.simulation_result.result.min_voltage():.3f} V")
```

---

## Models

Three electrochemical model fidelities are available:

| Model | Enum | Fidelity | Speed |
|-------|------|----------|-------|
| Single Particle Model | `Model.SPM` | Low | Fast |
| SPM + Electrolyte | `Model.SPMe` | Medium | Moderate |
| Doyle-Fuller-Newman | `Model.DFN` | High | Slow |

Use `Model.SPM` for quick screening; switch to `Model.DFN` for high-fidelity
validation.

> **Learning point — model choice matters:**
> SPM is fast but ignores electrolyte transport. For degradation or cycling
> studies, use `Model.SPMe` which captures concentration gradients without
> the full cost of DFN.

---

## Degradation Modeling

For cycling simulations, enable degradation mechanisms to study capacity fade:

```python
from battery_sim.core.degradation import DegradationConfig
from battery_sim.core.model import Model
from battery_sim.core.cell import Cell
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.backend.pybamm_backend import PyBaMMBackend

degradation = DegradationConfig(
    sei_growth=True,            # SEI layer thickening (main calendar aging)
    lithium_plating=False,      # Lithium plating at low temp / high rate
    active_material_loss=False, # Electrode material dissolution
)

charge = Protocol.cccv(charge_current_A=2.0, cutoff_voltage_V=3.65, taper_current_A=0.1)
discharge = Protocol.cc(current_A=5.0, duration_s=120)
protocol = Protocol.cycle(charge, discharge, n_cycles=5, rest_s=60)

sim = Simulation(
    cell=Cell.preset("NMC_5AH"),
    model=Model.SPMe,              # SPMe required for degradation sub-models
    protocol=protocol,
    environment=Environment(temperature_C=25.0),
    degradation=degradation,
)

run = sim.run(PyBaMMBackend())
```

After execution, degradation signals are available:

```python
from battery_sim.types.signal import Signal

sei = run.result._data.get(Signal.SEI_THICKNESS)         # SEI layer thickness
cap_loss = run.result._data.get(Signal.TOTAL_CAPACITY_LOSS)  # Total capacity loss
```

You can also use `CyclingAnalyzer` for trend analysis:

```python
from battery_sim.core.application_services import CyclingAnalyzer

fade = CyclingAnalyzer.capacity_fade_rate(run)      # Ah/cycle
eol = CyclingAnalyzer.end_of_life_prediction(run)   # Cycle number at 80% capacity
summary = CyclingAnalyzer.cycling_summary(run)       # Per-cycle metrics dict
```

> **Learning point — degradation flags are domain-level:**
> `DegradationConfig` doesn't know about PyBaMM. It expresses intent
> ("I want SEI growth"). The backend translates that to the correct PyBaMM
> sub-model options. This keeps the domain layer engine-agnostic.

---

## Signals Reference

All time-series data is accessed through `Signal` enum values:

| Signal | Description |
|--------|-------------|
| `VOLTAGE` | Terminal voltage (V) |
| `CURRENT` | Current (A) |
| `POWER` | Power (W) |
| `ENERGY` | Cumulative energy (Wh) |
| `SOC` | State of charge (%) |
| `TEMPERATURE` | Cell temperature |
| `CAPACITY` | Cumulative charge (Ah) |
| `INTERNAL_RESISTANCE` | Approximate R_internal (Ω) |
| `CYCLE_DISCHARGE_CAPACITY` | Per-cycle discharge capacity (Ah) |
| `CYCLE_COULOMBIC_EFFICIENCY` | Per-cycle coulombic efficiency (%) |
| `CYCLE_CAPACITY_RETENTION` | Capacity retention vs cycle 1 (%) |
| `SEI_THICKNESS` | SEI layer thickness (degradation) |
| `TOTAL_CAPACITY_LOSS` | Total capacity loss (degradation) |

Access via `run.result.voltage()`, `run.result.soc()`, etc., or generically
via `run.result.get(Signal.VOLTAGE)`.

---

## Quick Reference

```
Cell.preset("LFP_5AH")                        → Cell
Cell.list_presets()                            → ["LFP_5AH", ...]
Protocol.cc(current_A, duration_s)             → Protocol
Protocol.cccv(charge_A, cutoff_V, taper_A)     → Protocol
Protocol.cycle(charge, discharge, n_cycles)    → Protocol
charge + discharge                             → Protocol (combined)
Simulation(cell, model, protocol, env).run(be) → SimulationRun
run.result.voltage()                           → TimeSeries
run.result.peak_power()                        → float
run.summary()                                  → str
AgentAPI().compare_presets(["A", "B"])          → DualFormatResult
AgentAPI().sensitivity_analysis(...)            → DualFormatResult
AgentAPI().check_feasibility(...)              → DualFormatResult
```
