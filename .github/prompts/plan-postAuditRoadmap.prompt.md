# Plan: battery_sim — Post-Audit Roadmap

The architectural audit is closed and clean. The next phase transforms battery_sim from a well-structured learning codebase into a capable, LLM-accessible simulation toolkit across three tracks: **(1) MCP server**, **(2) expanded simulation features**, **(3) hardening via tests and docs**.

---

## Phase 1: MCP Server for LLM Access
*Expose battery_sim as callable tools for Claude/Copilot via Model Context Protocol*

1. Add `mcp[cli]` dependency to `pyproject.toml`
2. Create `mcp_server.py` at project root — wrap each `@agent_tool` method from `AgentAPI` as an MCP tool with typed input schemas
3. Add a `run_simulation` tool to `core/agent_api.py` — currently only `compare_presets` triggers actual execution; a single-run tool is needed
4. Configure `.vscode/mcp.json` for local Copilot integration testing
5. **Verify**: MCP Inspector (`mcp dev mcp_server.py`) can list tools, call `list_presets`, `compare_presets(["LFP_5AH", "NMC_5AH"])`, `run_simulation("LFP_5AH")`

**Files**: `core/agent_api.py`, `core/result_formatter.py`, new `mcp_server.py`, `pyproject.toml`

---

## Phase 2: Expand Protocol & Simulation Capabilities

### 2a. CC-CV Protocol Support *(small, may partially work already)*
6. Verify `CC_CV` step handling in `backend/pybamm_backend.py` `translate_protocol_to_pybamm()` — add translation if missing
7. Validate end-to-end CC-CV execution with a smoke test

### 2b. Full Charge-Discharge Cycling *(depends on 2a)*
8. Add `Protocol.cycle(charge, discharge, n_cycles)` factory in `core/protocol.py`
9. Add PyBaMM multi-cycle experiment translation
10. Add per-cycle metric extraction (capacity per cycle, efficiency trend)
11. Add `CyclingAnalyzer` service in `core/application_services.py`

### 2c. Degradation Modeling *(depends on 2b, largest scope)*
12. Add `Model.SPMe` in `core/model.py`
13. Integrate PyBaMM's built-in degradation sub-models (SEI growth, lithium plating) via backend configuration
14. Add degradation signals to `types/signal.py` and extraction in `backend/pybamm_signal.py`

---

## Phase 3: Test Coverage & Documentation *(parallel with Phase 2)*

### 3a. Unit Tests
- Domain validation edge cases (`Cell`, `Protocol`, `Environment`, `SolverConfig`)
- `Result` metric calculations with mock `TimeSeries` data
- `ErrorDetector` with synthetic anomalous data
- `ConstraintChecker` feasibility checks

### 3b. Integration Tests
- `ComparisonService`, `SensitivityService`, `ParameterSweep` end-to-end

### 3c. MCP Tests
- Tool schema validation, MCP call → result round-trip

### 3d. Documentation
- Usage guide, MCP setup guide, API reference on key public classes

**New files**: `tests/test_domain.py`, `tests/test_result.py`, `tests/test_services.py`, `tests/test_mcp.py`, `docs/usage_guide.md`, `docs/mcp_setup.md`

---

## Execution Order

| Priority | What | Depends On |
|----------|------|------------|
| **1** | Phase 1 — MCP Server | Nothing |
| **2** | Phase 2a — CC-CV | Nothing |
| **3** | Phase 3a — Unit Tests | Nothing *(parallel)* |
| **4** | Phase 2b — Cycling | 2a |
| **5** | Phase 3b-c — Integration + MCP Tests | Phases 1 + 2a |
| **6** | Phase 2c — Degradation | 2b |
| **7** | Phase 3d — Documentation | Phases 1 + 2a-b |

## Scope Exclusions
- No REST API/CLI (MCP is the LLM interface)
- No CI/CD pipeline (add later when publishing)
- No alternative backends (not needed yet)
- `ParameterExplorer.grid_search()` remains stubbed (implement when DOE becomes priority)
