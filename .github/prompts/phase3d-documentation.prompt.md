# Phase 3d: Documentation

Write user-facing documentation: usage guide, MCP setup guide, and improved API docstrings.

## Prerequisites
- Phase 1 (MCP Server) should be complete (for MCP setup guide)
- Phase 2a (CC-CV) should be complete (for protocol examples)
- Phase 2b (Cycling) ideally complete (for cycling examples; can be added later)

## Context

Current documentation:
- `README.md` — installation and quick start (good, but limited to CC discharge)
- `docs/audit/` — architectural audit records (internal, not user-facing)
- Code docstrings — verbose teaching-style comments (good for learning, not API reference)

Missing: practical usage guide, MCP integration guide, concise API reference.

## Steps

### 1. Create `docs/usage_guide.md`

A practical tutorial covering real workflows:

**Sections:**
1. **Installation** — `pip install -e .` and `pip install -e ".[dev]"`
2. **Basic Simulation** — Run a single CC discharge, inspect results
3. **Cell Presets** — Browse and compare chemistries
4. **Protocols** — CC discharge, CC-CV charge, multi-step, cycling (if Phase 2b done)
5. **Comparing Chemistries** — Use ComparisonService or AgentAPI
6. **Sensitivity Analysis** — Which parameters matter?
7. **Feasibility Checking** — Physical constraint validation
8. **Session Tracking** — Recording investigations and reasoning chains
9. **Plotting** — Using result_plotting utilities
10. **Advanced: Parameter Sweeps** — Systematic parameter exploration

Each section should have a runnable code example and expected output description.

### 2. Create `docs/mcp_setup.md`

Guide for connecting battery_sim to LLM tools:

**Sections:**
1. **What is MCP?** — One-paragraph explanation
2. **Prerequisites** — Python 3.10+, battery_sim installed, `mcp` SDK
3. **VS Code Copilot Setup** — Copy `.vscode/mcp.json`, restart Copilot, verify tool discovery
4. **Claude Desktop Setup** — Add to `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "battery-sim": {
         "command": "python",
         "args": ["/path/to/battery_sim/mcp_server.py"]
       }
     }
   }
   ```
5. **Available Tools** — Table of all MCP tools with descriptions and example inputs
6. **Example Conversations** — Show what an LLM interaction looks like
7. **Troubleshooting** — Common issues (PyBaMM not installed, import errors, slow first run)

### 3. Improve key public API docstrings

Update docstrings on the main public classes to be concise API references (not teaching essays). Keep the teaching docstrings in internal modules but make the public API self-documenting.

**Classes to update:**
- `Cell` — parameters, preset factory, list_presets
- `Protocol` — factories (cc, rest, cccv, cycle), combination via `+`
- `Simulation` — fields, `run()`, `validate()`
- `SimulationRun` — `is_successful()`, `summary()`, key delegates
- `AgentAPI` — each `@agent_tool` method
- `Result` — signal access, metric methods

Guidelines:
- First line: one-sentence summary
- Args/Returns blocks for public methods
- Remove or shorten teaching paragraphs in public docstrings
- Keep examples where they add clarity

### 4. Update `README.md` with new capabilities

Once phases are complete, update the Quick Start to show:
- CC-CV charge example (if Phase 2a done)
- MCP server mention and link to `docs/mcp_setup.md`
- Link to `docs/usage_guide.md` for full tutorial

## Files to Read First
- `README.md` — current state
- `core/agent_api.py` — tool descriptions (copy into MCP guide)
- `core/cell.py`, `core/protocol.py`, `core/simulation.py`, `core/simulation_run.py`, `core/result.py` — current docstrings
- `mcp_server.py` (if exists) — tool definitions for MCP guide
- `.vscode/mcp.json` (if exists) — VS Code config for MCP guide

## Files to Create/Modify
- **Create**: `docs/usage_guide.md`
- **Create**: `docs/mcp_setup.md`
- **Modify**: `README.md` — add links, update examples
- **Modify**: public class docstrings in `core/` (see list above)

## Definition of Done
- [ ] `docs/usage_guide.md` covers all major workflows with runnable examples
- [ ] `docs/mcp_setup.md` covers VS Code Copilot and Claude Desktop setup
- [ ] README links to both guides
- [ ] Key public classes have concise, accurate docstrings
- [ ] All code examples in docs are syntactically correct (verify with `python -c "..."`)
