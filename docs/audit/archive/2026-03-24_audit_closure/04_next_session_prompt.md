> **SUPERSEDED** — This prompt was written for the March 24 session, which has been completed.
> For the final audit status, see [07_audit_closure_2026-03-24.md](07_audit_closure_2026-03-24.md).

# Next Session Prompt

Use this repository as an audit-driven refactor.

Before changing code, read these files in this order:

1. `docs/audit/00_observations_2026-03-09.md`
2. `docs/audit/01_target_architecture.md`
3. `docs/audit/02_refactoring_plan.md`
4. `docs/audit/03_module_matrix.md`

Working rules:

- Do not re-open the archived legacy reports unless strictly needed.
- Keep the refactor incremental and leave the repo runnable after each step.
- Prefer contract cleanup before structural moves.
- Do not refactor Phase 2 or 3 topics until Phase 1 is coherent.
- Use `SimulationRun` as the canonical simulation output.
- Treat `Result` as a payload inside `SimulationRun`, not as a competing execution return type.

Current status from the previous session:

- The main Phase 1 contract drift was corrected in `core/simulation.py`, `core/simulation_run.py`, `core/parameter_sweep.py`, `core/investigation_tools.py`, and `core/result.py`.
- `Simulation.run()` is documented as returning `SimulationRun`.
- Sweep and batch helper signatures were normalized to `SimulationRun` or `Optional[SimulationRun]` on explicit failure paths.
- `Result` was clarified as an embedded payload, not the canonical execution return type.
- Compatibility delegates on `SimulationRun` were intentionally preserved.

Your mission for this session:

- Stay in Phase 1 only and finish the remaining contract freeze work.
- Audit the remaining public surfaces that were not part of the first minimal patch and check whether they still describe, type, or assume execution outputs as `Result` instead of `SimulationRun`.
- Focus especially on agent-facing and formatting-facing modules that may still carry stale assumptions indirectly.
- Keep backward compatibility where practical with delegation helpers, but do not re-introduce ambiguous public return contracts.

Files to inspect first for Phase 1:

- `core/agent_api.py`
- `core/result_formatter.py`
- `core/api_schema.py`
- any tests or examples still active in the current tree that describe simulation outputs

Expected approach:

1. Gather remaining public contract mismatches after the first Phase 1 pass.
2. Propose a minimal second edit set limited to those mismatches.
3. Apply the changes.
4. Validate impacted files for errors.
5. Summarize what is now fully frozen in Phase 1 and what still remains before Phase 2 can start.

Definition of done for this session:

- no public simulation path claims to return `Result` if it actually returns `SimulationRun`
- sweep and batch abstractions no longer expose contradictory result types
- documentation/comments in touched files match the real contract
- interface-facing modules do not reintroduce `Result` as a competing execution output

Do not start renaming fields, moving backend ports, or rebuilding the schema in this session unless strictly required to complete Phase 1.