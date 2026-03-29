# Target Architecture

## Goal

The target architecture should separate:

- domain decisions
- simulation orchestration
- backend execution
- result and observability contracts
- agent-facing investigation workflows

The primary objective is to make the codebase easier to evolve, easier to audit, and less coupled to PyBaMM.

## Target Principles

### 1. Domain First

The domain model must not depend on concrete infrastructure.

This includes:

- cell definitions
- protocol definitions
- environment definitions
- solver intent and execution settings
- simulation request objects

### 2. Backend as Adapter

PyBaMM should be treated as one adapter behind a stable internal port.

The rest of the codebase should depend on an execution contract, not on PyBaMM types or PyBaMM-specific object construction rules.

### 3. Stable Output Contract

There must be exactly one canonical simulation output contract.

Target choice:

- `SimulationRun` is the canonical output
- `Result` is a component of `SimulationRun`, not a competing return type

### 4. Investigation Layer Uses Application Services

Batch comparison, sensitivity analysis, and agent workflows should consume application-level services instead of rebuilding orchestration logic ad hoc.

### 5. Introspection Mirrors Runtime Contracts

The schema exposed to agents must derive from the same domain vocabulary as the runtime.

No parallel naming system should exist for signals, parameters, or result shapes.

## Target Layering

## Layer 1 - Domain

Contents:

- `Cell`
- `CellPreset` metadata model
- `Protocol` and `Step`
- `Environment`
- `Model`
- `SolverConfig`
- domain validation exceptions
- signal vocabulary and base time-series types

Responsibilities:

- express battery simulation intent
- validate invariant rules
- stay independent from execution technology

Rules:

- no imports from `backend`
- no imports from agent or formatting layers
- no PyBaMM dependency

## Layer 2 - Application

Contents:

- simulation execution service
- batch execution service
- comparison service
- sensitivity service
- feasibility service
- session service

Responsibilities:

- orchestrate domain objects
- route execution to a backend port
- normalize outputs to `SimulationRun`
- expose use-case level operations

Rules:

- depends on domain and backend ports only
- does not depend on concrete PyBaMM implementation

## Layer 3 - Ports

Contents:

- simulation backend interface
- result extraction contracts if needed
- observability provider contracts if needed

Responsibilities:

- define what the application expects from execution adapters

Rules:

- owned by the core architecture, not by the infrastructure package

## Layer 4 - Infrastructure

Contents:

- PyBaMM backend
- PyBaMM parameter mapping
- PyBaMM signal mapping
- optional future backends

Responsibilities:

- convert application requests into concrete simulation engine calls
- extract runtime outputs into canonical internal contracts

Rules:

- depends on domain and ports
- may depend on external libraries such as PyBaMM and NumPy
- must not define competing business contracts

## Layer 5 - Interface

Contents:

- `AgentAPI`
- formatting layer
- introspection layer
- session presentation helpers
- future CLI or HTTP entry points

Responsibilities:

- provide user-facing and agent-facing APIs
- format and present outputs
- expose discoverable capabilities built on application services

Rules:

- depends on application and domain contracts
- should not directly instantiate concrete backends unless configuration explicitly asks for it

## Target Package Shape

Suggested structure:

```text
core/
  domain/
    cell.py
    cell_presets.py
    environment.py
    model.py
    protocol.py
    solver.py
    result_types.py
    exceptions.py
  application/
    simulation_service.py
    comparison_service.py
    sensitivity_service.py
    feasibility_service.py
    session_service.py
  ports/
    simulation_backend.py
  observability/
    simulation_run.py
    simulation_metadata.py
    simulation_error.py
    convergence_diagnostics.py
  analysis/
    result_analyzer.py
    parameter_sweep.py

backend/
  pybamm/
    backend.py
    parameter_mapper.py
    signal_mapper.py

interface/
  agent_api.py
  api_schema.py
  result_formatter.py
```

This exact split is optional, but the dependency direction is not.

## Canonical Contracts

### Simulation Request

Target canonical request:

- cell
- model
- protocol
- environment
- solver config

The backend should be injected at the application service boundary, not embedded in the domain object itself.

Recommended direction:

- turn `Simulation` into a pure request object, or replace it with `SimulationRequest`
- let a `SimulationService` select or receive the backend adapter

### Simulation Output

Target canonical output:

- `SimulationRun`
  - `result`
  - `metadata`
  - `errors`
  - `diagnostics`

Rules:

- every simulation execution path returns `SimulationRun`
- sweep and batch tools return collections of `SimulationRun`
- formatting layer never receives raw PyBaMM solution objects

### Signal Vocabulary

Target canonical signal system:

- use one internal signal enum
- derive schema names from it
- derive formatter labels from it

No hand-maintained second vocabulary should exist in the schema layer.

## Target Runtime Flow

1. Interface layer receives a user or agent request.
2. Application service builds or accepts a simulation request.
3. Application service selects a backend adapter via a port.
4. Infrastructure adapter executes the simulation engine.
5. Infrastructure adapter returns canonical `SimulationRun`.
6. Application service applies higher-level comparison, sensitivity, or session logic.
7. Interface layer formats and returns the result.

## Configuration Strategy

Target configuration rules:

- default backend configured once, close to application bootstrapping
- default protocol and solver config owned by interface or application bootstrap, not hidden inside infrastructure
- presets remain in domain or domain-support layer

## Observability Strategy

The target observability model should separate:

- actual runtime telemetry captured from the backend
- derived diagnostics inferred after execution
- user-facing summaries

Concrete rule:

- placeholder values are acceptable during bootstrap, but must be marked as estimated or unavailable
- `success=True` and fixed iteration counts must not be emitted as if they were true measurements

## Migration Guardrails

### Preserve

- `SimulationRun` as the common output object
- the high-level `AgentAPI` user experience
- `Cell.preset(...)` and preset discoverability
- protocol-to-experiment conversion logic conceptually

### Remove or Reduce

- direct `core -> backend` dependency
- direct `investigation_tools -> PyBaMMBackend` dependency
- duplicated batch and sweep logic across modules
- parallel naming systems for signals and metrics

### Normalize

- spelling and naming
- exception messages
- parameter mapping behavior across all presets
- type annotations around simulation results

## Success Criteria

The target architecture is reached when:

- domain modules have no backend imports
- investigation and agent layers depend on application services, not concrete adapters
- all execution paths return `SimulationRun`
- signal names are consistent across runtime, schema, and formatting
- infrastructure-specific logic is isolated in backend adapters
- audit documents become smaller because the code structure is self-explanatory