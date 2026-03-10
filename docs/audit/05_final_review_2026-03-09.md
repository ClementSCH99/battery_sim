# Final Audit Review - 2026-03-09

## Verdict

The refactor made meaningful architectural progress, but the audit objectives are not all fully reached.

The repository is in a better state than the baseline:

- the canonical execution output is now consistently `SimulationRun`
- the backend port is now core-owned in `core/simulation_backend.py`
- application services were introduced and are already used by higher-level modules
- static validation currently reports no workspace errors
- a functional smoke test of `AgentAPI.compare_presets(...)` succeeds and returns distinct chemistry-dependent metrics

However, the target architecture described in `01_target_architecture.md` is not fully reached yet.
The audit should therefore remain open, and the active audit documents should not be archived as closed architecture guidance yet.

## Evidence Collected

### Verified Improvements

- `core/simulation_backend.py` now owns the execution port.
- `backend/base.py` is only a compatibility shim.
- `core/simulation.py` now depends on the core-owned port rather than importing from `backend/`.
- `core/application_services.py` centralizes simulation execution, batch execution, comparison, sensitivity, and sweep orchestration.
- `core/agent_api.py` already delegates comparison and sensitivity work to application services.
- `core/investigation_tools.py` exposes `SimulationRun` consistently across its public helper paths.
- static validation reports no errors.
- runtime smoke testing succeeds for:
  - `APISchema()`
  - `AgentAPI()`
  - `AgentAPI.compare_presets(['LFP_5AH', 'NMC_5AH'])`

### Remaining Structural Gaps

The following gaps are still incompatible with the target architecture:

1. Domain-level protocol objects still expose PyBaMM-specific translation methods.
   Evidence: `to_pybamm()` is still defined directly in [core/protocol.py](core/protocol.py#L7).

2. The simulation request still embeds the backend adapter directly.
   Evidence: `Simulation` still carries a `backend` field in [core/simulation.py](core/simulation.py#L16).

3. Core investigation code still knows how to instantiate the concrete PyBaMM backend.
   Evidence: the default backend factory still lazy-loads `battery_sim.backend.pybamm_backend` in [core/investigation_tools.py](core/investigation_tools.py#L66).

4. Application services exist, but the target service split is only partial.
   Evidence: services are grouped in a single module at [core/application_services.py](core/application_services.py#L1) and there is still no dedicated feasibility or session service boundary.

5. Introspection is closer to runtime contracts, but not yet strictly derived from them.
   Evidence: `APISchema` still contains a large hand-maintained signal/tool catalog in [core/api_schema.py](core/api_schema.py#L387).

6. Root and documentation reset is advanced but not formally closed as an architectural endpoint.
   Evidence: the active audit set is still the working reference and remains necessary for ongoing refactor decisions.

## Phase Assessment

### Phase 0 - Audit Baseline

Status: complete.

The audit corpus exists and the legacy material is archived under `docs/audit/archive/2026-03-09_pre_audit/`.

### Phase 1 - Freeze the Canonical Contracts

Status: complete.

The canonical output contract is now `SimulationRun`, and current public execution paths inspected during this review no longer present `Result` as the competing runtime return type.

### Phase 2 - Normalize Naming and Vocabulary

Status: substantially complete, but not perfectly closed.

The `Environment` aliasing and `Model` normalization are in place, and the signal vocabulary was improved. Some older validation text and mixed historical naming remain outside the main architectural path.

### Phase 3 - Extract a Core-Owned Backend Port

Status: complete for the phase success criteria.

The core now owns the simulation backend port, and the main core execution path no longer imports from `backend/`.

### Phase 4 - Introduce Application Services

Status: partially complete.

The service layer exists and is already used, but it is still incomplete and not yet the sole orchestration boundary.

### Phase 5 - Consolidate Sweep and Investigation Logic

Status: partially complete.

Logic has moved inward toward services, but `investigation_tools.py` and `parameter_sweep.py` remain as substantial wrappers around similar orchestration concerns.

### Phase 6 - Rebuild Introspection from Runtime Contracts

Status: partially complete.

The schema is more aligned with runtime vocabulary, but it is still largely maintained by hand rather than generated from canonical contracts.

### Phase 7 - Improve Observability Integrity

Status: materially improved, not fully closed.

Telemetry semantics are more honest than the baseline, but some diagnostics remain unavailable or inferred rather than genuinely measured.

### Phase 8 - Preset and Parameter Mapping Hardening

Status: partially complete.

Parameter mapping is now centralized in `backend/parameter_mapper.py`, but the chemistry policy still needs a fuller closure against all preset semantics and explicit unsupported-case tests.

### Phase 9 - Root Cleanup and Documentation Reset

Status: partially complete.

The repository is cleaner and the historical sprawl is archived, but the architecture reset is not yet ready to be declared final and closed.

## Conclusion for This Session

This session leaves the repository in a credible intermediate architecture rather than a fully completed target architecture.

The strongest outcomes are:

- the execution contract is now stable and testable
- the backend port ownership is corrected
- the service layer has started to absorb orchestration logic
- the runtime path is valid and usable

The main reason the audit cannot be closed yet is that the domain/application boundary is still not fully protected from infrastructure assumptions.

## Archival Decision

Do not archive the active audit set as completed architecture documentation yet.

Reason:

- the audit documents under `docs/audit/` are still active working guidance
- the target architecture is not fully achieved
- archiving now would incorrectly signal that the architectural migration is complete

Only the already archived legacy material should remain under the archive subtree for now.

## Recommended Next Steps

1. Remove adapter-specific protocol translation from the domain layer.
   Target: move `to_pybamm()` behavior out of [core/protocol.py](core/protocol.py#L7) into backend-side translation.

2. Stop embedding the backend inside the simulation request object.
   Target: refactor [core/simulation.py](core/simulation.py#L16) so backend selection happens at the application-service boundary.

3. Remove the core-level default instantiation of the concrete PyBaMM backend.
   Target: replace the lazy concrete import in [core/investigation_tools.py](core/investigation_tools.py#L66) with explicit dependency injection from configuration/bootstrap code.

4. Split and formalize the service layer.
   Target: decompose [core/application_services.py](core/application_services.py#L1) into explicit simulation, comparison, sensitivity, sweep, feasibility, and session service modules.

5. Finish consolidation of sweep and investigation logic.
   Target: make `investigation_tools.py` and `parameter_sweep.py` thin façades or remove one of the duplicated orchestration paths.

6. Make introspection derive from runtime contracts instead of duplicating them.
   Target: reduce hand-maintained catalogs in [core/api_schema.py](core/api_schema.py#L387) by deriving signal and tool metadata from canonical enums and services.

7. Harden preset-to-backend mapping with explicit coverage tests.
   Target: verify every preset against [backend/parameter_mapper.py](backend/parameter_mapper.py#L1) and fail loudly on unsupported semantics.

8. Add a minimal automated architectural regression suite.
   Target:
   - assert no direct `core -> backend` imports
   - assert all public simulation paths return `SimulationRun`
   - assert schema/runtime signal vocabulary stays aligned

9. Re-run the audit closure review only after steps 1 through 8 are complete.
   At that point, archive the active audit set and replace it with concise maintained architecture docs.