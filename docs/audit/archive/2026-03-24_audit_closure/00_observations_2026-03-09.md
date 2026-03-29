# Audit Observations - 2026-03-09

## Purpose

This document is the reference context for the audit restart.
It captures the current codebase state before refactoring, consolidates the architectural observations, and establishes the baseline for the next audit steps.

Planned follow-up documents:

- `01_target_architecture.md`
- `02_refactoring_plan.md`
- `03_module_matrix.md`

## Current Scope

The repository is a battery simulation toolkit centered on PyBaMM.
It combines:

- a domain model for batteries, protocols, environments, and simulations
- a concrete PyBaMM execution backend
- result extraction and observability wrappers
- agent-facing investigation tools and session tracking
- multiple historical B10/B11/B12 reports and examples at the repository root

The implementation is functional enough to express and run simulations, but the architecture is not yet stabilized.
The repository contains several generations of design layers that overlap.

## Main Modules

### Domain and Simulation Core

- `core/cell.py`
  Defines the `Cell` entity and minimal validation for cell-level parameters.
- `core/cell_presets.py`
  Stores predefined cell configurations by chemistry and form-factor flavor.
- `core/model.py`
  Defines the battery model choices exposed by the domain (`SPM`, `DFN`).
- `core/protocol.py`
  Defines protocol steps and converts them to PyBaMM experiment strings.
- `core/environment.py`
  Defines thermal and ambient conditions for a simulation.
- `core/solver.py`
  Defines solver choice, tolerances, time-step configuration, and initial SOC.
- `core/simulation.py`
  Aggregates all simulation inputs and delegates execution to the selected backend.
- `core/exceptions.py`
  Defines validation-related exceptions for the core domain.

### Backend Layer

- `backend/base.py`
  Defines the abstract simulation backend interface.
- `backend/pybamm_backend.py`
  Implements the full PyBaMM execution path: model building, experiment creation, parameter mapping, solve, result extraction, and observability wrapping.
- `backend/pybamm_signal.py`
  Defines the mapping from internal signals to PyBaMM variable names and aliases.

### Results and Observability

- `types/signal.py`
  Enumerates the internal signal vocabulary.
- `types/timeseries.py`
  Defines the basic time series container.
- `core/result.py`
  Holds extracted signals and exposes higher-level metrics such as energy, power, voltage extrema, efficiency, and plotting utilities.
- `core/simulation_run.py`
  Wraps a `Result` with metadata, diagnostics, and detected errors.
- `core/simulation_metadata.py`
  Captures run metadata such as solver settings, duration, and convergence status.
- `core/simulation_error.py`
  Defines simulation error categories and post-run detection helpers.
- `core/convergence_diagnostics.py`
  Defines convergence diagnostics and summary helpers.
- `core/result_analyzer.py`
  Provides advanced post-processing on a `Result`.

### Agent and Investigation Layer

- `core/api_schema.py`
  Provides self-description of parameters, signals, presets, and tools.
- `core/investigation_tools.py`
  Provides batch execution, comparisons, sensitivity analysis, constraints, and parameter exploration.
- `core/parameter_sweep.py`
  Provides parameter sweep utilities and override tracking.
- `core/result_formatter.py`
  Formats outputs for machine-readable and markdown-readable consumption.
- `core/simulation_session.py`
  Maintains investigation history, conclusions, and reports.
- `core/agent_api.py`
  Exposes the LLM-facing façade used to drive investigations.

## External Dependencies

Observed directly from imports:

- `pybamm`
- `numpy`
- `matplotlib` for plotting in `core/result.py`

Observed standard-library dependencies:

- `dataclasses`
- `typing`
- `enum`
- `datetime`
- `json`
- `time`
- `abc`

No packaging manifest was inspected during this pass, so the dependency inventory is code-derived.

## Internal Dependency Structure

### Effective Layering

The intended layering appears to be:

1. domain model
2. backend execution
3. results and observability
4. investigation tools
5. agent façade

### Actual Dependency Direction

The actual dependency graph is only partially aligned with that intention.

- `core/simulation.py` depends on `backend/base.py`
- `core/investigation_tools.py` depends directly on `backend/pybamm_backend.py`
- `core/agent_api.py` depends on both introspection and investigation layers
- `backend/pybamm_backend.py` depends on core domain objects and core observability objects

This means the repository does not currently enforce a clean separation where `core` is backend-agnostic.

## Full PyBaMM Simulation Data Flow

### 1. Input Construction

A simulation starts either:

- directly through `Simulation(...)`
- indirectly through `AgentAPI`, `BatchSimulator`, or parameter sweep helpers

The input state is composed of:

- `Cell`
- `Model`
- `Protocol`
- `Environment`
- `SolverConfig`
- a `SimulationBackend`

### 2. Validation and Delegation

`Simulation.run()` validates:

- backend presence and model support
- cell validity
- protocol validity
- environment validity
- solver configuration validity

It then delegates execution to `backend.run(simulation)`.

### 3. Backend Translation to PyBaMM

`PyBaMMBackend.run()` orchestrates the concrete execution path:

- `_build_model()` maps `Model` and thermal settings to a PyBaMM model
- `_build_experiment()` converts protocol steps into PyBaMM experiment strings
- `_build_solver()` maps the internal solver enum to a concrete PyBaMM solver class
- `_build_parameters()` builds `pybamm.ParameterValues` from the selected cell and environment

### 4. Solve Phase

The backend creates `pybamm.Simulation(...)` and calls `solve(initial_soc=...)`.

The raw PyBaMM solution object is the primary runtime output of this phase.

### 5. Signal Extraction

`_extract_result()` converts the PyBaMM solution into the internal representation.

It:

- extracts the simulation time vector
- maps PyBaMM variable names to internal `Signal` values
- normalizes units where needed
- converts raw arrays into `TimeSeries`

### 6. Derived Metric Computation

The backend computes additional signals from the primary traces:

- power
- cumulative energy
- cumulative capacity
- charge/discharge split
- efficiency
- approximate internal resistance

These are packaged into `Result`.

### 7. Observability Wrapping

The backend also builds:

- `SimulationMetadata`
- `SimulationError` list from `ErrorDetector`
- `ConvergenceDiagnostics`

These are combined with the `Result` in `SimulationRun`.

### 8. Agent Consumption

Higher layers then consume `SimulationRun`:

- `SimulationComparison` extracts comparable metrics
- `SensitivityAnalyzer` computes parameter influence
- `ResultFormatter` generates JSON and markdown outputs
- `SimulationSession` records investigation history
- `AgentAPI` exposes those capabilities as user-facing tools

## Architectural Inconsistencies

### 1. Core Depends on Backend

`core/simulation.py` imports the backend interface from `backend/base.py`.

Consequence:

- the domain layer is not independent from the infrastructure layer
- backend abstraction is not owned by the core boundary

### 2. Investigation Layer Depends on Concrete PyBaMM Backend

`core/investigation_tools.py` defaults directly to `PyBaMMBackend` rather than depending only on a backend abstraction.

Consequence:

- alternative backends are structurally possible but not practically integrated
- the exploration layer is tightly coupled to PyBaMM

### 3. Output Contract Drift After B11

`Simulation.run()` now returns `SimulationRun`, but some modules still model outputs as `Result`.

Observed mismatch:

- `core/parameter_sweep.py` types `simulation_result: Result`
- the sweep code actually stores the return value of `modified_sim.run()`

Consequence:

- type contracts are inconsistent
- APIs rely on duck typing and `Any`
- downstream code becomes harder to trust and reason about

### 4. Synthetic Observability

The observability layer exists, but key values are currently synthesized instead of sourced from real solver telemetry.

Examples in `backend/pybamm_backend.py`:

- `success=True` is forced
- convergence reason is always `Converged`
- diagnostics use fixed placeholder iteration counts

Consequence:

- the observability layer currently behaves more like a reporting façade than genuine runtime diagnostics

### 5. Inconsistent Naming and Domain Vocabulary

Examples:

- `ambiant_temperature_C` is misspelled and coexists with `temperature_C`
- `Model.SPM = "single_particule"` contains a spelling error
- several validation messages mix English and French and include inconsistent wording

Consequence:

- the public model vocabulary is unstable
- naming mistakes leak into the API and persistence surfaces

### 6. Chemistry Mapping Does Not Fully Cover Presets

Preset library includes variants such as:

- `NMC-HE`
- `LFP-HP`

Backend chemistry-to-parameter mapping only recognizes a narrower set such as `LFP`, `NMC`, `NCA`, `LCO`, `LMNO`.

Consequence:

- some presets silently fall back to generic parameter sets
- chemistry-specific behavior may be partially lost for specialized presets

### 7. Duplicate Exploration Responsibilities

`core/investigation_tools.py` and `core/parameter_sweep.py` both implement exploration and sweep logic.

Consequence:

- duplicated concepts
- partially duplicated APIs
- inconsistent data contracts and extension patterns

### 8. Introspection Vocabulary Diverges from Runtime Vocabulary

`core/api_schema.py` documents signals with names like:

- `voltage_V`
- `current_A`
- `state_of_charge_percent`

The runtime uses `Signal.VOLTAGE`, `Signal.CURRENT`, `Signal.SOC`.

Consequence:

- the introspection layer is not a faithful projection of the runtime model
- agent integration risks translation overhead and confusion

## Quality Observations

### Strengths

- the repository already exposes a coherent high-level investigation story
- the `SimulationRun` wrapper is a good direction for reproducibility and observability
- the result model is rich enough to support meaningful analysis and future reporting
- presets and protocols make the API approachable

### Weaknesses

- layering is blurred
- backend coupling is high
- historical B10/B11/B12 materials create noise at the repository root
- contracts evolved faster than the type model and documentation

## Audit Restart Decision

To restart on clean foundations:

- root-level historical reports and exploratory examples should be archived, not deleted permanently
- audit outputs should be grouped under `docs/audit/`
- future work should be driven by a new stable set of documents rather than the existing B10/B11/B12 report set

## Next Audit Steps

The next documents should be produced in this order:

1. target architecture
2. prioritized refactoring plan
3. detailed module matrix

This document is the baseline for those three steps.