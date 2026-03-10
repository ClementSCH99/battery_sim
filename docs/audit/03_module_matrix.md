# Detailed Module Matrix

## Reading Guide

This matrix is intended as an operational audit support.
It answers four questions for each module:

- what it is supposed to do
- what it currently depends on
- what is architecturally problematic
- how urgent the refactor is

Priority scale:

- P1: blocks architectural cleanup or creates contract ambiguity
- P2: important structural cleanup
- P3: useful cleanup after core stabilization

## Matrix

| Module | Current Role | Main Dependencies | Main Issues | Priority |
|---|---|---|---|---|
| `core/cell.py` | Cell entity and basic validation | `core/exceptions.py`, lazy access to presets | Domain model is acceptable, but validation remains minimal and some preset coupling leaks into the entity API | P3 |
| `core/cell_presets.py` | Preset registry and preset metadata | `core/cell.py` | Preset semantics are mixed with backend assumptions; chemistry naming is not fully aligned with backend mapping | P2 |
| `core/model.py` | Model selection enum | standard library `Enum` | Public enum values contain spelling issues and unstable naming | P2 |
| `core/protocol.py` | Protocol DSL and PyBaMM step translation | `core/exceptions.py` | Domain and adapter concerns are partially mixed because `to_pybamm()` is embedded in protocol steps | P2 |
| `core/environment.py` | Thermal and ambient inputs | `core/exceptions.py` | Ambiguous semantics between cell and ambient temperature; misspelled public field | P1 |
| `core/solver.py` | Solver configuration and validation | `core/protocol.py`, `numpy` | Mostly coherent, but still blends domain-level intent and backend-oriented execution details | P3 |
| `core/simulation.py` | Simulation aggregate and execution entry point | `backend/base.py`, domain modules | Core depends directly on backend package; backend injection is embedded in the domain object | P1 |
| `core/exceptions.py` | Validation exception hierarchy | none | Structurally fine; messages should be normalized | P3 |
| `backend/base.py` | Backend execution interface | `core/model.py` | Interface is owned by infrastructure package instead of core-owned port layer | P1 |
| `backend/pybamm_backend.py` | Concrete PyBaMM adapter | `pybamm`, `numpy`, domain modules, observability modules | Too many responsibilities in one class: engine setup, mapping, extraction, derived metrics, diagnostics, metadata | P1 |
| `backend/pybamm_signal.py` | Signal name mapping to PyBaMM variables | `types/signal.py` | Useful adapter module, but must be aligned with schema vocabulary and result guarantees | P2 |
| `types/signal.py` | Canonical signal enum | standard library `Enum` | Good candidate for canonical runtime vocabulary, but currently not used consistently by schema and formatter layers | P1 |
| `types/timeseries.py` | Base time-series container | standard library only | Structurally fine | P3 |
| `core/result.py` | Result container, convenience metrics, plotting | `numpy`, signal and timeseries types | Rich but oversized; mixes canonical data object, analytics, and plotting concerns | P2 |
| `core/simulation_run.py` | Canonical full simulation output | `Result`, metadata, diagnostics, errors | Good direction; must become the single explicit output contract everywhere | P1 |
| `core/simulation_metadata.py` | Run metadata model | `core/solver.py`, `datetime` | Current fields are fine, but semantics are weakened by placeholder values upstream | P2 |
| `core/simulation_error.py` | Error taxonomy and post-run detection | `numpy`, runtime signal access | Useful, but error thresholds and detection logic need review; current implementation reaches into `result._data` directly | P2 |
| `core/convergence_diagnostics.py` | Diagnostics model and summaries | standard library only | Model is fine, but current values are often synthetic rather than measured | P2 |
| `core/result_analyzer.py` | Advanced post-processing on results | `numpy`, `core/result.py` | Useful as analysis layer; should stay downstream of canonical results and not absorb orchestration logic | P3 |
| `core/parameter_sweep.py` | Parameter sweeps and override tracking | `core/simulation.py`, `core/result.py` | Contract drift: still typed around `Result` while execution now returns `SimulationRun`; overlaps with investigation layer | P1 |
| `core/investigation_tools.py` | Batch runs, comparison, sensitivity, constraints | `core/simulation.py`, concrete `PyBaMMBackend` | Central orchestration utility but tightly coupled to concrete backend; overlaps with parameter sweep logic; heavy use of `Any` | P1 |
| `core/result_formatter.py` | JSON and markdown rendering for agent outputs | `json`, standard library | Valuable interface-layer concern, but should rely on canonical vocabulary and service outputs only | P2 |
| `core/simulation_session.py` | Investigation history and reasoning trace | `datetime`, `json` | Structurally acceptable; should depend on stable application outputs rather than unstable intermediate shapes | P3 |
| `core/api_schema.py` | Introspection and discoverability metadata | `core/cell_presets.py` | Duplicates runtime vocabulary and manually describes concepts that diverge from actual outputs | P1 |
| `core/agent_api.py` | User-facing and LLM-facing façade | schema, investigation, formatting, session, domain defaults | Too much orchestration and default policy in one place; should become a thin façade over application services | P1 |

## Hotspots

### Hotspot A - Execution Boundary

Modules involved:

- `core/simulation.py`
- `backend/base.py`
- `backend/pybamm_backend.py`

Problem:

- the execution boundary exists, but it is owned from the wrong side and mixes domain and infrastructure concerns

Refactor direction:

- extract a core-owned backend port
- reduce `PyBaMMBackend` into smaller adapter components

### Hotspot B - Result Contract Drift

Modules involved:

- `core/simulation_run.py`
- `core/result.py`
- `core/parameter_sweep.py`
- `core/investigation_tools.py`

Problem:

- the repository conceptually moved to `SimulationRun`, but several APIs and annotations still behave as if `Result` were the primary execution output

Refactor direction:

- normalize all execution outputs to `SimulationRun`
- keep `Result` strictly as the signal payload object

### Hotspot C - Agent and Investigation Overlap

Modules involved:

- `core/agent_api.py`
- `core/investigation_tools.py`
- `core/parameter_sweep.py`
- `core/result_formatter.py`

Problem:

- orchestration, analysis, and presentation are spread across multiple modules without a stable application-service layer

Refactor direction:

- introduce application services and leave `AgentAPI` and formatting modules thin

### Hotspot D - Vocabulary Mismatch

Modules involved:

- `types/signal.py`
- `backend/pybamm_signal.py`
- `core/api_schema.py`
- `core/result_formatter.py`

Problem:

- schema and runtime describe similar concepts with different names and not always with the same guarantees

Refactor direction:

- derive schema and formatter labels from canonical internal signal definitions

## Immediate Refactoring Priorities

Recommended first implementation slice:

1. `core/simulation.py`
2. `backend/base.py`
3. `core/simulation_run.py`
4. `core/parameter_sweep.py`
5. `core/investigation_tools.py`
6. `core/api_schema.py`
7. `core/agent_api.py`

This order resolves the dependency and contract problems before cosmetic or secondary cleanup.

## Stable Modules

These modules are comparatively stable and should mostly be adapted, not redesigned:

- `types/timeseries.py`
- `core/exceptions.py`
- parts of `core/cell.py`
- parts of `core/simulation_session.py`

## Modules Likely to Split

These modules are strong candidates for decomposition:

- `backend/pybamm_backend.py`
  Suggested split: backend adapter, parameter mapper, signal extractor, observability builder
- `core/result.py`
  Suggested split: canonical result object, analysis helpers, plotting helpers
- `core/agent_api.py`
  Suggested split: façade only, with orchestration moved into services
- `core/api_schema.py`
  Suggested split: parameter catalog, signal catalog, preset catalog, tool registry

## Audit Conclusion

The repository has a viable conceptual core, but its current structure blurs domain, orchestration, and infrastructure boundaries.

The highest-value changes are not cosmetic.
They are:

- correcting ownership of the backend port
- stabilizing the canonical output contract
- consolidating orchestration into explicit services
- aligning vocabulary across runtime and introspection

This matrix should be used as the working reference when implementing the refactor plan.