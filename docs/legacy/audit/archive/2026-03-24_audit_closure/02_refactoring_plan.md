# Prioritized Refactoring Plan

## Objective

Refactor the repository from the current mixed architecture toward the target architecture with minimal disruption to existing behavior.

This plan is ordered to reduce risk.
Each phase should leave the codebase in a coherent intermediate state.

## Refactoring Strategy

The safest sequence is:

1. stabilize contracts
2. reduce naming and typing ambiguity
3. isolate backend concerns
4. consolidate duplicated application logic
5. rebuild interface and introspection layers on top of stable services

## Phase 0 - Audit Baseline

Status:

- completed by creating the audit documents under `docs/audit/`
- completed by archiving legacy root-level reports and examples

Deliverables:

- `00_observations_2026-03-09.md`
- `01_target_architecture.md`
- this plan
- `03_module_matrix.md`

## Phase 1 - Freeze the Canonical Contracts

### Goal

Make the execution and output contracts unambiguous before moving code.

### Tasks

- declare `SimulationRun` as the only canonical output of simulation execution
- update sweep and batch utilities so their type signatures explicitly use `SimulationRun`
- remove stale annotations that still claim functions return `Result`
- document which methods are convenience delegates and which are the true source objects

### Target Files

- `core/simulation.py`
- `core/simulation_run.py`
- `core/parameter_sweep.py`
- `core/investigation_tools.py`
- `core/result.py`

### Why First

If output contracts remain inconsistent, every later refactor multiplies uncertainty.

### Success Criteria

- no public simulation path claims to return `Result` when it actually returns `SimulationRun`
- sweep and batch tools expose one consistent result model

## Phase 2 - Normalize Naming and Vocabulary

### Goal

Eliminate vocabulary drift that currently leaks into the API and mapping logic.

### Tasks

- rename `ambiant_temperature_C` to `ambient_temperature_C`
- decide whether `Environment.temperature_C` means cell temperature, ambient temperature, or requested initial temperature
- normalize `Model` enum values and public labels
- align signal names across `Signal`, `api_schema`, and formatter outputs
- normalize exception text and language usage

### Target Files

- `core/environment.py`
- `core/model.py`
- `types/signal.py`
- `backend/pybamm_signal.py`
- `core/api_schema.py`
- `core/result_formatter.py`
- `core/exceptions.py`

### Why Second

Stable naming is a prerequisite for reliable extraction, formatting, and future persistence.

### Success Criteria

- one canonical spelling for each domain concept
- one canonical signal vocabulary used everywhere

## Phase 3 - Extract a Core-Owned Backend Port

### Goal

Move the execution contract out of infrastructure ownership.

### Tasks

- relocate the simulation backend interface into a core-owned port module
- update `Simulation` or `SimulationService` to depend on that port instead of `backend/base.py`
- keep PyBaMM implementation behind the port

### Target Files

- current `backend/base.py`
- `core/simulation.py`
- `backend/pybamm_backend.py`
- all imports that reference the current backend base module

### Why Third

This is the first structural decoupling step.
It should happen only after the contracts and names are stabilized.

### Success Criteria

- core modules no longer import from `backend/`
- concrete backend implementations depend inward on core contracts

## Phase 4 - Introduce Application Services

### Goal

Remove orchestration logic from ad hoc helpers and centralize use cases.

### Tasks

- introduce a simulation execution service
- introduce a batch execution service
- introduce comparison and sensitivity services
- move orchestration logic out of `AgentAPI` and utility-heavy modules into those services

### Target Files

- new application service modules
- `core/investigation_tools.py`
- `core/agent_api.py`
- `core/parameter_sweep.py`

### Why Fourth

Once the backend boundary is clean, the next risk is duplicated orchestration and business logic spread.

### Success Criteria

- `AgentAPI` becomes a façade over application services
- batch, comparison, and sweep operations share one execution pipeline

## Phase 5 - Consolidate Sweep and Investigation Logic

### Goal

Remove overlapping responsibilities and duplicated concepts.

### Tasks

- choose a single home for sweep logic
- choose a single home for comparison logic
- keep utility modules thin and purpose-specific
- ensure parameter override tracking remains compatible with the canonical output contract

### Target Files

- `core/parameter_sweep.py`
- `core/investigation_tools.py`
- `core/result_analyzer.py`

### Success Criteria

- one implementation path for parameter sweep
- one implementation path for comparison metric extraction
- no parallel concepts with conflicting type contracts

## Phase 6 - Rebuild Introspection from Runtime Contracts

### Goal

Make the schema trustworthy by deriving it from real domain and result contracts.

### Tasks

- derive signal catalog from the internal signal vocabulary
- derive preset metadata from the preset registry without duplicating semantics
- align tool descriptions with the actual service layer
- remove schema items that describe metrics not actually guaranteed by runtime

### Target Files

- `core/api_schema.py`
- `core/result_formatter.py`
- `core/agent_api.py`

### Success Criteria

- no introspection item contradicts runtime behavior
- no duplicated manual mapping exists unless strictly presentation-specific

## Phase 7 - Improve Observability Integrity

### Goal

Distinguish real telemetry from estimated or placeholder diagnostics.

### Tasks

- audit what PyBaMM telemetry is actually available
- mark unavailable solver telemetry explicitly as unavailable instead of fabricating values
- separate post-run derived diagnostics from backend-emitted telemetry
- revisit error detection thresholds and classification logic

### Target Files

- `backend/pybamm_backend.py`
- `core/simulation_metadata.py`
- `core/convergence_diagnostics.py`
- `core/simulation_error.py`

### Success Criteria

- reported diagnostics are either true, estimated, or unavailable with clear semantics
- metadata and diagnostics do not imply a precision they do not have

## Phase 8 - Preset and Parameter Mapping Hardening

### Goal

Ensure preset semantics are carried correctly into PyBaMM parameterization.

### Tasks

- align all preset chemistry identifiers with backend mapping rules
- decide explicit fallback behavior for unsupported chemistry variants
- log or reject silent fallback cases where chemistry-specific semantics would be lost
- centralize parameter mapping in a dedicated mapper module

### Target Files

- `core/cell_presets.py`
- `backend/pybamm_backend.py`
- future `parameter_mapper.py`

### Success Criteria

- every preset has an explicit mapping policy
- no specialized chemistry variant silently degrades to a generic mapping without visibility

## Phase 9 - Root Cleanup and Documentation Reset

### Goal

Finish the audit reset and make the repository root intentional again.

### Tasks

- keep new audit documentation under `docs/audit/`
- reintroduce only the examples that survive the audit and match the target architecture
- replace historical B10/B11/B12 report sprawl with concise maintained docs

### Success Criteria

- root contains only current documentation and current examples
- archived material remains available but no longer competes with active guidance

## Cross-Cutting Risk Notes

### Risk 1 - Backward Compatibility

Many convenience methods currently mask contract drift.
Removing ambiguity too aggressively may break example scripts or external callers.

Mitigation:

- keep compatibility shims during transition
- deprecate before removing

### Risk 2 - Hidden PyBaMM Assumptions

Some current domain fields are really PyBaMM parameter-mapping hints rather than stable business concepts.

Mitigation:

- make the mapping layer explicit before aggressively redesigning domain classes

### Risk 3 - Tooling Layers Repeating Business Logic

`AgentAPI`, `investigation_tools`, and formatters currently overlap in responsibilities.

Mitigation:

- move behavior into services first
- leave façades thin

## Recommended Execution Order Summary

1. canonical output and typing cleanup
2. naming and vocabulary normalization
3. backend port extraction
4. application service introduction
5. sweep and investigation consolidation
6. introspection rebuild
7. observability integrity fixes
8. preset-to-backend mapping hardening
9. final documentation and example reset

## Definition of Done

The refactor can be considered complete when:

- the code follows the target dependency direction
- outputs are type-consistent across all execution paths
- naming is stable across domain, backend, and interface layers
- PyBaMM is replaceable in principle without changing the domain model
- the agent-facing API describes exactly what the runtime guarantees