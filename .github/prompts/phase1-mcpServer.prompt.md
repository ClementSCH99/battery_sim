# Phase 1: MCP Server for LLM Access

Expose battery_sim as a set of callable tools for Claude/Copilot via Model Context Protocol (MCP).

## Context

battery_sim has a clean `AgentAPI` class in `core/agent_api.py` with 5 `@agent_tool`-decorated methods:
- `describe_api()` → API documentation
- `list_presets(chemistry?)` → cell chemistry catalog
- `compare_presets(preset_names, environment_temp_C?)` → side-by-side comparison (runs simulations)
- `sensitivity_analysis(preset_name, parameters)` → parameter impact analysis (runs simulations)
- `check_feasibility(preset_name, temperature_C?)` → physical constraint check

Each returns a `DualFormatResult(json_data, markdown_text, interpretation_hints)`.

There is NO tool to run a single simulation and get results — only `compare_presets` triggers execution. This is a gap.

## Architecture Rules
- `core/` must never import from `backend/` (except `simulation_backend.py` port and `agent_api.py` interface layer)
- `SimulationRun` is the canonical simulation output
- The MCP server is infrastructure — it wraps `AgentAPI`, it does not duplicate its logic

## Steps

### 1. Add `run_simulation` tool to `AgentAPI`

In `core/agent_api.py`, add a new `@agent_tool`-decorated method:

```python
@agent_tool(
    description="Run a single battery simulation and return performance metrics",
    examples=["Run a simulation with LFP_5AH", "Simulate NMC_5AH at 40°C"]
)
def run_simulation(
    self,
    preset_name: str,
    current_A: Optional[float] = None,
    duration_s: Optional[float] = None,
    temperature_C: float = 25.0,
) -> DualFormatResult:
```

This method should:
- Create a `Cell` from the preset
- Build a `Protocol` from `current_A`/`duration_s` (fall back to `self.default_protocol`)
- Build an `Environment` and `Simulation`
- Execute via `SimulationExecutionService` (import from `application_services`)
- Extract key metrics from the `SimulationRun` via `ComparisonService.extract_metrics()`
- Return `DualFormatResult` with JSON metrics and a Markdown summary
- Record the investigation in the session

### 2. Add `mcp` dependency

In `pyproject.toml`, add to dependencies:
```toml
dependencies = [
    "pybamm",
    "numpy",
    "mcp[cli]",
]
```

### 3. Create MCP server

Create `mcp_server.py` at project root. Use the `mcp` Python SDK with FastMCP:

```python
from mcp.server.fastmcp import FastMCP
```

The server should:
- Instantiate `AgentAPI` once at module level
- Expose each `@agent_tool` method as an MCP tool via `@mcp.tool()` decorators
- Map tool parameters to typed function arguments
- Return the `json_data` dict from `DualFormatResult` (serialized as JSON string)
- Use stdio transport (default for FastMCP)

MCP tools to expose:
| MCP Tool Name | Wraps | Parameters |
|---|---|---|
| `list_presets` | `api.list_presets()` | `chemistry: str \| None` |
| `run_simulation` | `api.run_simulation()` | `preset_name: str, current_A: float \| None, duration_s: float \| None, temperature_C: float` |
| `compare_presets` | `api.compare_presets()` | `preset_names: list[str], environment_temp_C: float \| None` |
| `sensitivity_analysis` | `api.sensitivity_analysis()` | `preset_name: str, parameters: list[str]` |
| `check_feasibility` | `api.check_feasibility()` | `preset_name: str, temperature_C: float` |
| `get_session_summary` | `api.get_session_summary()` | *(none)* |

### 4. Create VS Code MCP configuration

Create `.vscode/mcp.json`:
```json
{
  "servers": {
    "battery-sim": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

### 5. Verify

Run these checks:
1. `python -c "from mcp.server.fastmcp import FastMCP; print('MCP SDK OK')"` — import works
2. `python -c "from battery_sim.core.agent_api import AgentAPI; a = AgentAPI(); print(a.run_simulation('LFP_5AH'))"` — new tool works
3. `mcp dev mcp_server.py` — MCP Inspector opens, tools are listed
4. In MCP Inspector: call `list_presets` → verify JSON response with preset data
5. In MCP Inspector: call `run_simulation` with `preset_name="LFP_5AH"` → verify JSON with metrics
6. `pytest tests/test_architecture.py -v` — existing architectural tests still pass

## Files to Read First
- `core/agent_api.py` — existing `@agent_tool` methods (wrap these)
- `core/application_services.py` — `SimulationExecutionService`, `ComparisonService.extract_metrics()`
- `core/result_formatter.py` — `DualFormatResult` structure
- `pyproject.toml` — add dependency here

## Files to Create/Modify
- **Modify**: `core/agent_api.py` — add `run_simulation` method
- **Modify**: `pyproject.toml` — add `mcp[cli]` dependency
- **Create**: `mcp_server.py` — MCP server entry point
- **Create**: `.vscode/mcp.json` — VS Code integration config

## Definition of Done
- [ ] `run_simulation` tool exists on `AgentAPI` and returns metrics for a single preset
- [ ] `mcp_server.py` starts without errors and exposes 6 tools via MCP protocol
- [ ] MCP Inspector can discover and call all tools
- [ ] `.vscode/mcp.json` configures the server for Copilot
- [ ] Existing `pytest tests/test_architecture.py` still passes
