# battery_sim

A Python toolkit for battery cell simulation built on [PyBaMM](https://pybamm.org/). Define cells, protocols, and environments as domain objects, then run electrochemical simulations through a clean service layer that keeps your code decoupled from the simulation engine.

## Installation

```bash
pip install -e .

# With dev dependencies (pytest, matplotlib):
pip install -e ".[dev]"
```

## Quick Start

```python
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.backend.pybamm_backend import PyBaMMBackend

# 1. Pick a cell from built-in presets
cell = Cell.preset("LFP_5AH")

# 2. Define a discharge protocol (1C for 60 seconds)
protocol = Protocol.cc(current_A=5.0, duration_s=60)

# 3. Set operating conditions
env = Environment(temperature_C=25.0)

# 4. Build the simulation request
sim = Simulation(
    cell=cell,
    model=Model.SPM,
    protocol=protocol,
    environment=env,
)

# 5. Run it
backend = PyBaMMBackend()
run = sim.run(backend)

# 6. Access results
print(run.is_successful())
print(run.result.voltage())          # Voltage time series
print(run.result.available_signals())  # All extracted signals
print(run.summary())                 # Human-readable summary
```

### Available Presets

```python
from battery_sim.core.cell import Cell
print(Cell.list_presets())
# ['LFP_5AH', 'NMC_5AH', 'NCA_5AH', 'LCO_3AH', 'LFP_10AH',
#  'NMC_10AH', 'LMNO_4AH', 'NMC_HE_50AH', 'LFP_HP_20AH']
```

### CC-CV Charge

```python
from battery_sim.core.protocol import Protocol

protocol = Protocol.cccv(
    charge_current_A=2.5,     # CC phase at 0.5C
    cutoff_voltage_V=4.2,     # Switch to CV at 4.2 V
    taper_current_A=0.25,     # End when current drops to 0.25 A
)
```

### MCP Server (LLM integration)

`battery_sim` ships an MCP server so LLM tools (VS Code Copilot, Claude Desktop)
can run simulations directly. See the [MCP Setup Guide](docs/mcp_setup.md) for
configuration instructions.

## Documentation

- **[Usage Guide](docs/usage_guide.md)** — Full tutorial: protocols, comparisons, sweeps, plotting
- **[MCP Setup Guide](docs/mcp_setup.md)** — Connect battery_sim to VS Code Copilot or Claude Desktop

## Architecture

The codebase follows a clean layered architecture: domain objects (`Cell`, `Protocol`, `Simulation`) contain no infrastructure dependencies, application services orchestrate use cases, and the PyBaMM backend sits behind an abstract port. See [docs/audit/01_target_architecture.md](docs/audit/01_target_architecture.md) for the full architecture reference.

## Running Tests

```bash
# Architectural guard tests (fast, no PyBaMM execution)
pytest tests/test_architecture.py -v

# Smoke tests (run real simulations, requires PyBaMM)
pytest tests/test_smoke.py -v

# All tests
pytest tests/ -v
```

## Dependencies

- **Required:** [PyBaMM](https://pybamm.org/), NumPy
- **Optional:** matplotlib (for plotting)
- **Dev:** pytest

## License

See repository for license details.
