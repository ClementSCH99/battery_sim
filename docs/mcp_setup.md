# MCP Server Setup Guide

Connect `battery_sim` to LLM tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

---

## What is MCP?

MCP is an open protocol that lets LLM-based tools (VS Code Copilot, Claude Desktop, etc.)
discover and call external functions at runtime. `battery_sim` ships an MCP server
that exposes its simulation capabilities as callable tools — so an LLM can run
battery simulations, compare chemistries, and analyze sensitivity without any
custom glue code.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | ≥ 3.10 |
| `battery_sim` | installed (`pip install -e .`) |
| `mcp[cli]` | installed (pulled automatically by battery_sim) |
| PyBaMM | installed (pulled automatically by battery_sim) |

Verify:

```bash
python -c "from battery_sim.mcp_server import mcp; print('OK')"
```

---

## VS Code Copilot Setup

1. Create (or update) `.vscode/mcp.json` in your workspace root:

```json
{
  "servers": {
    "battery-sim": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/absolute/path/to/battery_sim"
    }
  }
}
```

> Replace `/absolute/path/to/battery_sim` with the actual path to the project.

2. Reload VS Code (`Ctrl+Shift+P` → **Developer: Reload Window**).
3. Open Copilot Chat. Tools prefixed `mcp_battery-sim_` should appear.

**Quick check:** Ask Copilot *"List battery presets"* — it should invoke `list_presets` and return a table of chemistries.

---

## Claude Desktop Setup

Add the server to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "battery-sim": {
      "command": "python",
      "args": ["/absolute/path/to/battery_sim/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. The tools will appear in the tool picker.

---

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `list_presets` | List available cell chemistry presets | `chemistry` (optional, e.g. `"LFP"`) |
| `run_simulation` | Run a single simulation and return metrics | `preset_name` (required), `current_A`, `duration_s`, `temperature_C` |
| `compare_presets` | Side-by-side comparison of multiple presets | `preset_names` (required, list), `environment_temp_C` |
| `sensitivity_analysis` | Measure parameter sensitivity | `preset_name` (required), `parameters` (required, list of `"temperature_C"`, `"nominal_capacity_Ah"`, `"internal_resistance_Ohm"`) |
| `check_feasibility` | Check physical feasibility of a configuration | `preset_name` (required), `temperature_C` |
| `get_session_summary` | Summarise the current investigation session | *(none)* |

All tools return JSON strings.

---

## Example Conversations

### 1. Discover presets

> **User:** What battery chemistries can you simulate?
>
> **LLM** *(calls `list_presets`)*: There are 9 presets across 6 chemistries:
> LFP (5 Ah, 10 Ah, 20 Ah HP), NMC (5 Ah, 10 Ah, 50 Ah HE), NCA (5 Ah),
> LCO (3 Ah), LMNO (4 Ah).

### 2. Compare two chemistries

> **User:** Compare LFP_5AH and NMC_5AH.
>
> **LLM** *(calls `compare_presets` with `["LFP_5AH", "NMC_5AH"]`)*:
> NMC delivers 50 % more peak power but LFP is 2 % more efficient …

### 3. Sensitivity analysis

> **User:** How sensitive is NMC_5AH to temperature?
>
> **LLM** *(calls `sensitivity_analysis` with `preset_name="NMC_5AH"`,
> `parameters=["temperature_C"]`)*:
> Temperature sensitivity is HIGH — a 30 °C swing changes peak power by 45 %.

### 4. Multi-step investigation

> **User:** Find the best chemistry for a cold-weather application at −10 °C.
>
> **LLM:**
> 1. Calls `check_feasibility` for each preset at −10 °C.
> 2. Calls `compare_presets` with feasible presets at −10 °C.
> 3. Calls `sensitivity_analysis` on the winner to confirm robustness.
> 4. Summarises with `get_session_summary`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: battery_sim` | Package not installed | `pip install -e .` from the project root |
| `ModuleNotFoundError: mcp` | MCP SDK missing | `pip install "mcp[cli]"` |
| Tools not visible in Copilot | `.vscode/mcp.json` missing or wrong path | Verify `cwd` and `args` paths, reload VS Code |
| First call is slow (~20 s) | PyBaMM JIT-compiles on first invocation | This is normal; subsequent calls are fast |
| `ImportError: pybamm` | PyBaMM not installed | `pip install pybamm` |
| JSON parse error in tool output | Tool returned an error string | Check server logs (`python mcp_server.py` in a terminal to see stderr) |

---

## Running the Server Manually (debugging)

```bash
cd /path/to/battery_sim
python mcp_server.py
```

The server communicates over **stdio** (stdin/stdout) using the MCP protocol.
You won't see interactive output — it's designed to be driven by an MCP client.
Errors print to stderr.
