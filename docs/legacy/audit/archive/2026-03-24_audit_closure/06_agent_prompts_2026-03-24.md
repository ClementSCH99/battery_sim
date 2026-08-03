# Agent Prompts for Audit Completion — 2026-03-24

> Each prompt below is self-contained. Copy-paste one into a new chat session to delegate that round of work. Execute them in order (Round 1 → Round 5).
>
> **Learning mode:** The user is learning software architecture, Python development, and AI-assisted coding through this project. For every change you make, briefly explain *why* it matters — what principle it serves, what would go wrong without it, and what pattern it follows. Don't just execute; teach as you go.

---

## Round 1 — Fix Critical Architecture Violations

```
You are working on the battery_sim repository at /home/clement/battery_sim.

CONTEXT:
This is a battery simulation toolkit built on PyBaMM. An architectural audit identified 3 critical violations of the clean architecture principle "domain must not depend on infrastructure". Your job is to fix all 3. The codebase must remain fully functional after your changes.

LEARNING CONTEXT:
The user is learning software architecture and Python through this project. For every change:
1. Explain WHY the change matters (what architectural principle it enforces)
2. Show a BEFORE/AFTER mental model (how the dependency arrow changes)
3. Name the PATTERN being applied (e.g., "Dependency Inversion", "Adapter Pattern", "Port & Adapter")
4. Point out TRAPS to watch for (what would break if done wrong)
After each task, write a brief "What you just learned" summary (3-4 bullet points).

Read these files first to understand the architecture:
- docs/audit/01_target_architecture.md
- docs/audit/05_final_review_2026-03-09.md

TASK A1 — Move to_pybamm() out of domain protocol (CRITICAL)

File: core/protocol.py

WHAT'S WRONG:
The domain protocol classes (Step, ConstantCurrent, Rest, CC_CV) each have a `to_pybamm()` method that returns PyBaMM-specific experiment strings. This is adapter logic living in domain code.

WHY IT MATTERS (explain this to the user):
This violates the "Dependency Inversion Principle" (the D in SOLID). The domain layer should define WHAT a protocol is (charge at 2A for 60 seconds), not HOW a specific tool represents it ("Discharge at 2 A for 60 seconds" as a PyBaMM string). If we ever switch to a different simulation engine, we'd have to modify our domain classes — that's backward. The domain should be stable; adapters should adapt to the domain, not the other way around.

The pattern we're applying is called "Adapter Pattern" or "Anti-Corruption Layer" — the backend translates between its own language and the domain's language.

What to do:
1. Remove all `to_pybamm()` methods from Step, ConstantCurrent, Rest, and CC_CV in core/protocol.py
2. Create a translation function in backend/pybamm_backend.py (or a new backend/protocol_translator.py) that takes a Protocol and returns the list of PyBaMM experiment strings. Something like:
   ```python
   def translate_protocol_to_pybamm(protocol: Protocol) -> list[str]:
       """Convert domain protocol steps to PyBaMM experiment strings."""
       strings = []
       for step in protocol.steps:
           if isinstance(step, ConstantCurrent):
               if step.current_A > 0:
                   strings.append(f"Discharge at {step.current_A} A for {step._duration_s} seconds")
               else:
                   strings.append(f"Charge at {abs(step.current_A)} A for {step._duration_s} seconds")
           elif isinstance(step, Rest):
               strings.append(f"Rest for {step._duration_s} seconds")
           elif isinstance(step, CC_CV):
               strings.append(f"Charge at {step.charge_current_A} A until {step.cutoff_voltage_V} V")
               strings.append(f"Hold at {step.cutoff_voltage_V} V until {step.taper_current_A} A")
       return strings
   ```
3. Update PyBaMMBackend._build_experiment() to call this new function instead of step.to_pybamm()
4. The Step base class should no longer mention PyBaMM at all

Also fix validation bug in core/protocol.py line 94: `if not step.current_A != 0:` is a double negation — fix it to `if step.current_A == 0:`. Explain to the user how `not X != 0` evaluates (truthiness chain) so they understand why it's a bug.

TASK A2 — Remove backend field from Simulation dataclass

File: core/simulation.py

WHAT'S WRONG:
Currently `Simulation` is a frozen dataclass with a `backend: SimulationBackend` field. This embeds infrastructure concern in the domain object.

WHY IT MATTERS (explain this to the user):
A Simulation should describe WHAT to simulate (which cell, protocol, environment), not HOW to simulate it (which backend engine). It's like a recipe: the recipe describes ingredients and steps, not which oven brand to use. The oven choice belongs to the kitchen (the service layer), not the recipe (the domain). This is the "Separation of Concerns" principle. When the backend is a field on Simulation, every part of the code that constructs a Simulation must know about backends — that's coupling spreading everywhere.

What to do:
1. Remove the `backend` field from the Simulation dataclass
2. Remove the backend-related validation from Simulation.validate() (the `backend is None` check and `supports_model` check)
3. Change Simulation.run() to accept backend as a parameter: `def run(self, backend: SimulationBackend, **solver_options) -> SimulationRun`
4. Update core/application_services.py — the SimulationExecutionService and BatchExecutionService need to pass the backend at run time instead of expecting it on the Simulation object. The backend should be injected into SimulationExecutionService.__init__() and used when calling simulation.run(backend=self.backend). Explain to the user that this is "Dependency Injection" — the service receives its dependency from outside rather than creating it internally.
5. Update all places that construct Simulation(...) to no longer pass backend=. Search the whole codebase for `Simulation(` and fix each call site. Key files:
   - core/application_services.py (BatchExecutionService.run_presets, run_parameter_variations)
   - core/investigation_tools.py (BatchSimulationConfig has backend field — keep it there as config, but don't pass it to Simulation)
   - core/parameter_sweep.py (ParameterSweep methods)
   - backend/pybamm_backend.py (if it creates Simulations)
6. The backend should now live on BatchSimulationConfig (it already does) and be passed to services, not to Simulation.

TASK A3 — Remove lazy PyBaMMBackend import from core

File: core/investigation_tools.py

WHAT'S WRONG:
The function `_create_default_backend()` at line 66 does `import_module("battery_sim.backend.pybamm_backend")` — this is core importing from infrastructure.

WHY IT MATTERS (explain this to the user):
Even a lazy import is still a dependency. If you delete the PyBaMM backend, this core module breaks — that proves the dependency exists. In clean architecture, dependencies point INWARD (infrastructure → domain), never outward (domain → infrastructure). The lazy import is a clever trick that hides the coupling but doesn't eliminate it. We want to make it truly clean: the interface layer (agent_api.py) is allowed to pick the concrete backend because it sits at the outer ring.

Show the user a before/after dependency diagram:
- BEFORE: agent_api → investigation_tools → (lazy) pybamm_backend
- AFTER:  agent_api → pybamm_backend (direct, at the edge) → passes backend into services

What to do:
1. Remove the `_create_default_backend()` function from core/investigation_tools.py
2. The `BatchSimulationConfig.backend` field currently defaults to `_create_default_backend()`. Change its default to require explicit backend injection (no default, or `None` with a clear error).
3. Make sure agent_api.py creates the backend at the interface layer and passes it down. The interface layer is allowed to know about the concrete backend. Add the import and instantiation there.
4. Search for any other place in core/ that imports from backend/ — there should be NONE except for core/simulation_backend.py (the abstract port).

AFTER ALL TASKS — Write a "Round 1 Learning Summary" for the user:
- List the 3 architecture principles applied (Dependency Inversion, Separation of Concerns, Dependency Injection)
- Draw a simple BEFORE/AFTER text diagram showing how dependency arrows changed
- Explain in one sentence why these changes make the codebase more maintainable

VERIFICATION:
After all changes:
- Run: `grep -r "from battery_sim.backend" core/` — should return NOTHING except simulation_backend re-exports
- Run: `grep -r "to_pybamm" core/` — should return NOTHING
- Run: `grep -r "pybamm" core/` — should return NOTHING (no PyBaMM references in domain)
- Run: `python -c "from battery_sim.core.simulation import Simulation; print('OK')"` — should work
- If possible, run a smoke test to confirm simulations still execute

Explain each verification command to the user — what it checks and why it proves the architecture is correct.

Keep backward compatibility where practical. Do NOT restructure files beyond what's needed. Do NOT rename modules or create new packages.
```

---

## Round 2 — Eliminate Duplication Layer

```
You are working on the battery_sim repository at /home/clement/battery_sim.

CONTEXT:
This is a battery simulation toolkit. An architectural audit found that core/investigation_tools.py (468 LOC) is almost entirely a thin wrapper that duplicates core/application_services.py. Similarly, core/parameter_sweep.py has overlapping sweep logic. The goal is to remove the duplication while keeping the unique value each module provides.

LEARNING CONTEXT:
The user is learning software architecture and Python through this project. For every change:
1. Explain the DRY principle ("Don't Repeat Yourself") and why duplication is dangerous (bugs fixed in one place but not the other, confusing API surface for users)
2. Explain the difference between a "facade" (simplifies an interface) and a "wrapper that adds nothing" (just indirection for no reason)
3. Show how to decide what to keep vs. what to remove: does the code add unique value, or just forward calls?
4. After each task, write a brief "What you just learned" summary.

Read these files first:
- docs/audit/01_target_architecture.md
- docs/audit/03_module_matrix.md (Hotspot C)
- core/application_services.py
- core/investigation_tools.py (full file)
- core/parameter_sweep.py (full file)
- core/agent_api.py (to see what it imports from these)

TASK B1 — Remove pure delegation wrappers from investigation_tools.py

WHAT'S WRONG (explain to user):
These classes in investigation_tools.py are "pass-through wrappers" — they accept the same arguments, do no transformation, and just call the equivalent method in application_services. This is the opposite of useful abstraction: it adds a layer of indirection that makes debugging harder (you have to trace through an extra hop), creates a maintenance burden (two places to update), and confuses developers about which module to import from.

The question to ask yourself: "If I delete this class, does any BEHAVIOR disappear?" If the answer is no — only an import path changes — then the class is dead weight.

These classes add NO logic beyond delegating to application_services:
- BatchSimulator.run_presets() → just calls BatchExecutionService.run_presets()
- BatchSimulator.run_parameter_variations() → just calls BatchExecutionService.run_parameter_variations()
- SimulationComparison.extract_metrics() → just calls ComparisonService.extract_metrics()
- SimulationComparison.compare_batch_results() → just calls ComparisonService.compare_batch_results()
- SensitivityAnalyzer.analyze_single_parameter() → just calls SensitivityService.analyze_single_parameter()

What to do:
1. Remove BatchSimulator, SimulationComparison, and SensitivityAnalyzer classes entirely from investigation_tools.py
2. Keep these items that provide UNIQUE value (explain to the user what makes each one worth keeping):
   - BatchSimulationConfig dataclass (used throughout as config container — it's a VALUE OBJECT, not a wrapper)
   - ComparisonMetric dataclass (used as value object — carries data, doesn't delegate)
   - ConstraintViolation dataclass (same — data carrier)
   - ConstraintChecker class (unique feasibility logic, not duplicated elsewhere — provides real BEHAVIOR)
   - ParameterExplorer class (unique, even if incomplete — it's a real algorithm stub, not a delegation)
3. Update all imports in other files that referenced the removed classes. Key files to check:
   - core/agent_api.py (likely imports BatchSimulator, SimulationComparison, SensitivityAnalyzer — redirect to application_services)
   - Any other file that imports from investigation_tools

TASK B2 — Consolidate parameter_sweep.py

WHY (explain to user):
core/parameter_sweep.py provides ParameterSweep class that wraps ParameterSweepService from application_services. But it also provides UNIQUE value objects: ParameterOverride and SweepResult. So we can't just delete it — we need to keep the unique parts and remove the duplication. This is the "Extract and Merge" refactoring pattern.

What to do:
1. Move ParameterOverride and SweepResult dataclasses into application_services.py (or keep them in parameter_sweep.py as the canonical location — your choice based on what's cleanest). Explain your reasoning to the user.
2. The ParameterSweep class methods are all @staticmethod wrappers. Make parameter_sweep.py a thin re-export module that just imports from application_services, OR fold the unique wrapping logic (SweepResult construction) into ParameterSweepService
3. Remove duplicated sensitivity analysis logic if it exists in parameter_sweep.py (check analyze_sensitivity vs SensitivityService)

Explain to the user: when you have value objects (dataclasses that just hold data) vs. service objects (classes that DO things), value objects can live anywhere reasonable, but services should exist in exactly one place.

TASK B3 — Update agent_api.py to depend on application_services directly

WHY (explain to user):
This is about making the dependency graph HONEST. When agent_api.py imports from investigation_tools which then imports from application_services, the real dependency is on application_services — investigation_tools is just an unnecessary middleman. Direct dependencies are easier to understand, debug, and maintain. The import graph should match the actual dependency graph.

What to do:
1. agent_api.py currently imports from both investigation_tools AND application_services. After B1, some investigation_tools imports will be gone.
2. Update agent_api.py to import orchestration services (BatchExecutionService, ComparisonService, SensitivityService) directly from application_services
3. Keep importing BatchSimulationConfig and ConstraintChecker from investigation_tools (they remain there)
4. Verify all agent_api methods still work — the behavior should be identical, just with cleaner import paths

AFTER ALL TASKS — Write a "Round 2 Learning Summary" for the user:
- Explain the difference between accidental duplication and meaningful abstraction
- How to spot "wrapper classes that add nothing" in any codebase
- The rule of thumb: "If deleting this code only changes import paths, it's dead weight"
- Draw the BEFORE/AFTER module dependency diagram

VERIFICATION:
After all changes:
- investigation_tools.py should be ~150-200 LOC (down from 468), containing only BatchSimulationConfig, ComparisonMetric, ConstraintViolation, ConstraintChecker, ParameterExplorer
- No class in investigation_tools.py should delegate to application_services — if it delegates, remove it
- Run: `python -c "from battery_sim.core.agent_api import AgentAPI; print('OK')"` — should work
- Run: `python -c "from battery_sim.core.investigation_tools import ConstraintChecker; print('OK')"` — should work
- Verify no circular imports

Explain each verification step to the user.

Keep the teaching docstrings/comments in investigation_tools.py if they're valuable — just remove the dead code.
```

---

## Round 3 — Make the Repo Installable and Testable

```
You are working on the battery_sim repository at /home/clement/battery_sim.

CONTEXT:
This is a battery simulation toolkit (~6800 LOC). It currently has NO __init__.py files, NO pyproject.toml, and NO test suite. The repo is not installable as a package and has no automated quality gates. Your job is to add basic project infrastructure.

LEARNING CONTEXT:
The user is learning Python packaging, testing, and CI practices through this project. For every change:
1. Explain WHAT each file does and WHY it's needed (__init__.py, pyproject.toml, conftest.py)
2. Explain how Python's import system works — why __init__.py matters, what `pip install -e .` does
3. Explain the difference between unit tests, integration tests, and architectural tests
4. Show how tests serve as "living documentation" of architectural decisions
5. After each task, write a brief "What you just learned" summary.

The code uses `from battery_sim.core.X import Y` style imports throughout, so the package structure needs __init__.py files under a battery_sim root.

Current directory layout:
```
battery_sim/          ← this is the workspace root AND the package root
  backend/
    base.py
    parameter_mapper.py
    pybamm_backend.py
    pybamm_signal.py
  core/
    agent_api.py
    api_schema.py
    application_services.py
    cell.py
    cell_presets.py
    convergence_diagnostics.py
    environment.py
    exceptions.py
    investigation_tools.py
    model.py
    parameter_sweep.py
    protocol.py
    result.py
    result_analyzer.py
    result_formatter.py
    simulation.py
    simulation_backend.py
    simulation_error.py
    simulation_metadata.py
    simulation_run.py
    simulation_session.py
    solver.py
  types/
    signal.py
    timeseries.py
  docs/
  .venv/
```

TASK C1 — Add __init__.py files

WHY (explain to user):
In Python, a directory is only a "package" (importable) if it contains an __init__.py file. Without it, `from battery_sim.core.cell import Cell` can't work — Python doesn't know that `battery_sim/core/` is a package to look inside. The __init__.py can be empty or contain re-exports. Think of it as a "this folder is part of the project" marker.

Explain to the user:
- The difference between a "package" (directory with __init__.py) and a "module" (single .py file)
- What `__all__` does and when you'd use it
- Why we keep __init__.py minimal (to avoid circular imports and unclear APIs)

What to do:
1. Create __init__.py at the workspace root (battery_sim/) — this makes it the top-level package
2. Create backend/__init__.py — expose key public names
3. Create core/__init__.py — expose key public names
4. Create types/__init__.py — expose key public names

Each __init__.py should have minimal content. Example for core/:
```python
"""Battery simulation core domain and services."""
```

You may add selective re-exports of the most important public classes if it improves usability, but keep it minimal. Don't re-export everything.

TASK C2 — Create pyproject.toml

WHY (explain to user):
pyproject.toml is the modern standard for Python project configuration (replaces setup.py). It tells pip:
- What your project is called and its version
- What dependencies it needs (so `pip install` grabs them automatically)
- How to build the package (so others can install it)
- Where to find tests and how to configure tools like pytest

Explain to the user:
- The difference between `pip install .` (install a copy) vs `pip install -e .` (install in "editable" mode — your code changes take effect immediately without reinstalling)
- What "dependencies" vs "optional dependencies" means (numpy is always needed; pytest is only needed for development)
- Why the build system matters (setuptools vs hatchling vs flit — keep it simple with setuptools)

Create a pyproject.toml at the workspace root with:
- Project name: battery-sim
- Version: 0.1.0
- Python requirement: >=3.10
- Dependencies: pybamm, numpy
- Optional dev dependencies: pytest, matplotlib
- Build system: setuptools or hatchling (whichever is simpler)
- Make sure the package discovery finds backend/, core/, types/ as sub-packages of battery_sim

Important: The workspace root IS the package. The imports are `from battery_sim.core.X import Y`, so the package name is `battery_sim` and the source root is `.` (the workspace root itself). Configure packaging accordingly. You may need to set `packages = ["battery_sim"]` with a `tool.setuptools.packages.find` configuration, or use a src layout approach if simpler. Check what works with the existing import style.

Run `pip show battery-sim` or `pip list | grep battery` to check if it's already installed, and inspect how.

TASK C3 — Create architectural guard tests

WHY (explain to user):
Architectural tests are a special kind of test: they don't test BEHAVIOR (does the code produce correct output?), they test STRUCTURE (does the code follow the rules we set?). Without them, future changes can silently break architecture decisions — someone adds a quick `from backend.pybamm_backend import ...` in core/ and nobody notices until the architecture has rotted.

These tests are "executable architecture documentation." They encode the rules from docs/audit/01_target_architecture.md as code that runs automatically.

Explain to the user:
- The concept of "fitness functions" — automated checks that verify architectural properties
- How to use Python's `ast` module or simple string search to inspect code structure
- Why these tests are MORE valuable than unit tests for long-term project health

Create tests/test_architecture.py with these tests:

```python
"""Architectural regression tests.

These tests enforce the dependency rules from the target architecture:
- Core domain must not import from backend infrastructure
- All public simulation paths return SimulationRun
- Signal vocabulary is consistent between runtime and schema
"""
```

Test 1: No core → backend imports
- Parse all .py files under core/ 
- Assert none of them contain `from battery_sim.backend` or `import battery_sim.backend`
- Exception: core/simulation_backend.py can be referenced (it's the port, not infrastructure)

Test 2: SimulationRun is the canonical output
- Import SimulationBackend and check that run() is annotated to return SimulationRun
- Import SimulationExecutionService and check execute() returns SimulationRun
- Import Simulation and check run() returns SimulationRun

Test 3: Signal vocabulary consistency
- Import Signal enum from types/signal.py
- Import api_schema and check all signals in the schema correspond to real Signal enum values

TASK C4 — Create smoke test

WHY (explain to user):
A smoke test answers one question: "Does the system basically work?" It's not about edge cases or perfect coverage — it's about catching catastrophic regressions. If someone breaks the PyBaMM integration, the smoke test fails immediately. Named after the hardware testing practice of plugging in a device and checking if smoke comes out.

Explain to the user:
- The difference between smoke tests (does it start?), integration tests (do the parts work together?), and unit tests (does this function work?)
- Why we use `@pytest.mark.slow` — so developers can run fast tests quickly and save slow tests for CI
- Why we use SHORT protocols in tests (60 seconds instead of hours) — tests should be fast

Create tests/test_smoke.py:
```python
"""Smoke tests that run real PyBaMM simulations.

These tests verify end-to-end execution paths work.
Mark them with @pytest.mark.slow so they can be skipped in fast CI.
"""
import pytest
```

Test 1: Single simulation runs and returns SimulationRun
- Create a simple Simulation with LFP_5AH preset, SPM model, 1C discharge for 60 seconds, 25°C
- Run it and assert result is a SimulationRun with non-empty result.available_signals()

Test 2: Compare presets works
- Use application_services or AgentAPI to compare LFP_5AH and NMC_5AH
- Assert both results are non-None

Keep tests minimal and fast. Use short protocols (60 seconds max).

TASK C5 — Create tests/__init__.py and a pytest config

Add a tests/__init__.py (empty file).
Add pytest configuration in pyproject.toml:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["slow: marks tests as slow (run with -m slow)"]
```

Explain to the user what each pytest config option does.

AFTER ALL TASKS — Write a "Round 3 Learning Summary":
- The Python packaging mental model: module → package → distribution
- Why `pip install -e .` is your best friend during development
- The testing pyramid: architectural tests (few but high-value) → integration (medium) → unit (many)
- How tests prevent "architecture erosion" over time

VERIFICATION:
- Run: `pip install -e ".[dev]"` (or equivalent) — package installs
- Run: `python -c "import battery_sim; print('OK')"` — import works
- Run: `pytest tests/test_architecture.py -v` — architectural tests pass
- Run: `pytest tests/test_smoke.py -v` — smoke tests pass (requires PyBaMM)

Explain each verification command to the user.
```

---

## Round 4 — Improve Introspection and Code Quality

```
You are working on the battery_sim repository at /home/clement/battery_sim.

CONTEXT:
This is a battery simulation toolkit. The architectural audit found that core/api_schema.py (830 LOC) contains a hand-maintained signal catalog that duplicates and can drift from the canonical Signal enum in types/signal.py. The goal is to derive the schema from runtime contracts instead of maintaining parallel definitions.

LEARNING CONTEXT:
The user is learning software design principles through this project. For every change:
1. Explain the "Single Source of Truth" (SSOT) principle — why duplicated definitions always drift apart
2. Explain the "Separation of Concerns" principle when splitting plotting from data
3. Show what "code generation from metadata" means (deriving schema from enums)
4. Point out common code smells and how to recognize them
5. After each task, write a brief "What you just learned" summary.

Read these files first:
- types/signal.py (the canonical Signal enum — ~30 LOC, 17 signal values)
- core/api_schema.py (full file — note the _build_signal_catalog() method)
- core/result.py (to understand what analysis methods exist)

TASK D1 — Derive signal catalog from Signal enum

WHAT'S WRONG (explain to user):
Currently, the Signal enum defines 17 signals (VOLTAGE, CURRENT, etc.) and api_schema.py manually re-creates those same 17 signals as SignalDefinition objects with hand-typed names, units, and descriptions. This is TWO sources of truth for the same information. The problem: when someone adds Signal.NEW_SIGNAL to the enum but forgets to add it to api_schema.py, the API lies about what the system supports. This is called "definition drift" and it's a class of bugs that ONLY automated derivation can prevent.

The fix applies the "Single Source of Truth" (SSOT) principle: the Signal enum IS the truth, and the schema should READ from it, not duplicate it.

What to do:
1. In core/api_schema.py, find the _build_signal_catalog() method (or wherever SignalDefinition objects are hand-created)
2. Replace the hand-maintained signal definitions with auto-generation from the Signal enum
3. Create a mapping that associates each Signal enum value with its metadata (unit, description, aliases). This can be a dict constant in api_schema.py:
   ```python
   _SIGNAL_METADATA = {
       Signal.VOLTAGE: {"unit": "V", "description": "Terminal voltage", "aliases": ["voltage_V"]},
       Signal.CURRENT: {"unit": "A", "description": "Cell current", "aliases": ["current_A"]},
       # etc.
   }
   ```
4. Generate SignalDefinition objects by iterating over Signal enum members and looking up metadata
5. Any Signal enum value NOT in the metadata dict should either:
   - Be included with a sensible default ("unit": "?", "description": Signal.name)
   - Or raise a warning at build time
6. This ensures that adding a new signal to the enum automatically surfaces it in the schema (even if with placeholder metadata)

Explain to the user: This is a form of "code generation" — not from an external file, but from the codebase's own type definitions. It's a powerful pattern that keeps things in sync automatically.

TASK D2 — Split plotting out of result.py

WHAT'S WRONG (explain to user):
The Result class currently contains plot() and plot_single() methods that depend on matplotlib. This is a classic "Separation of Concerns" violation: a DATA class shouldn't know how to RENDER itself. Why does it matter?
- Importing result.py forces importing matplotlib (slow, unnecessary for headless/server use)
- Testing result.py requires matplotlib installed
- If you change the plotting library (e.g., to plotly), you have to modify the data class

The pattern is: data objects hold data, utility functions transform or display data. The Result class should be "I store simulation signals." A separate module should be "I can plot simulation signals."

What to do:
1. Create core/result_plotting.py with the plotting functions extracted from Result
2. The new module should accept a Result object and produce plots:
   ```python
   def plot_result(result: Result, signals=None, figsize=None, save_path=None):
       ...
   def plot_single_signal(result: Result, signal, figsize=None, save_path=None):
       ...
   ```
3. Remove plot() and plot_single() from the Result class
4. Add backward-compatibility shims if needed (delegate methods that warn about deprecation), OR just remove them if nothing in the codebase calls result.plot() 
5. Check if anything calls result.plot() or result.plot_single() — search the codebase. If nothing does, just remove cleanly.

TASK D3 — Minor code quality fixes

Explain each fix as a "code smell" lesson:

1. In core/protocol.py: confirm the validation bug is fixed (Round 1 should have done this, but verify)
   - `if not step.current_A != 0:` should be `if step.current_A == 0:`
   - CODE SMELL: "Double negation" — always simplify boolean expressions. `not X != Y` is especially confusing because it combines logical NOT with inequality. Teach the user to use De Morgan's laws.

2. In core/simulation_run.py: the 44 backward-compat delegate methods are acceptable for now, but add a single comment block at the top of that section:
   ```python
   # --- Backward-compatible Result delegates ---
   # These methods forward to self.result for migration convenience.
   # TODO: Deprecate in a future version once all callers use .result directly.
   ```
   - CODE SMELL: "Excessive delegation" — when a class delegates 44 methods to another class, it's usually a sign they should be merged or the delegation should be removed. But during migration, it's acceptable as a temporary compatibility layer. Teach the user the concept of "technical debt with a known payoff date."

3. Clean up any remaining `else: pass` patterns (e.g., in core/solver.py around line 45-46)
   - CODE SMELL: "Dead code" — `else: pass` does nothing and confuses readers into thinking something was intended there. Remove it.

AFTER ALL TASKS — Write a "Round 4 Learning Summary":
- Single Source of Truth (SSOT) and why it prevents drift
- Separation of Concerns (data vs. presentation)
- Recognizing code smells: double negation, excessive delegation, dead code
- The pattern: "generate from metadata" instead of "maintain by hand"

VERIFICATION:
- Run: `python -c "from battery_sim.core.api_schema import APISchema; s = APISchema(); print(len(s.get_signals().signals), 'signals')"` — should show ~17 signals
- Run: `python -c "from battery_sim.types.signal import Signal; print(len(Signal), 'enum values')"` — should match schema count
- Run: `pytest tests/ -v` — all tests still pass
- Run: `grep -r "matplotlib" core/result.py` — should return nothing (plotting moved out)

Explain each verification to the user.
```

---

## Round 5 — Documentation and Audit Closure

```
You are working on the battery_sim repository at /home/clement/battery_sim.

CONTEXT:
This is the final round of an architectural audit for a battery simulation toolkit. Rounds 1-4 have been completed:
- Round 1: Fixed critical architecture violations (to_pybamm moved to backend, backend removed from Simulation, no core→backend imports)
- Round 2: Eliminated duplication layer (investigation_tools trimmed, parameter_sweep consolidated)
- Round 3: Made repo installable (pyproject.toml, __init__.py, tests)
- Round 4: Improved introspection (signal catalog derived from enum, plotting separated)

Your job is to close the audit with proper documentation.

LEARNING CONTEXT:
The user is learning software engineering practices through this project. For every change:
1. Explain WHY documentation matters as much as code (code says HOW, docs say WHY and WHAT)
2. Explain the difference between a README (entry point for newcomers), architecture docs (for contributors), and audit docs (historical record of decisions)
3. Show what makes a good README (scannable, shows installation in <30 seconds, has a working code example)
4. Explain why archiving audit documents matters (decisions without recorded reasoning get re-debated endlessly)
5. After each task, write a brief "What you just learned" summary.

Read these files first:
- docs/audit/05_final_review_2026-03-09.md (previous final review)
- docs/audit/01_target_architecture.md (the target we aimed for)
- docs/audit/02_refactoring_plan.md (the phases)

TASK E1 — Write final audit closure document

WHY (explain to user):
An audit closure document serves the same purpose as a "merge commit message" for an entire architectural project. It records: what was the goal, what was done, what wasn't done, and why. Without it, the next developer (or your future self) won't know whether the half-finished code is intentional or abandoned. This is called "Architecture Decision Record" (ADR) thinking — document decisions at the time they're made, because context fades fast.

Create docs/audit/07_audit_closure_2026-03-24.md with:

1. A summary of what was accomplished in the March 24 session (Rounds 1-4)
2. Phase-by-phase status update:
   - Phase 0: Complete (unchanged)
   - Phase 1: Complete (unchanged)
   - Phase 2: Complete (unchanged)
   - Phase 3: FULLY Complete — core no longer imports from backend at all
   - Phase 4: Complete — application services are the sole orchestration layer
   - Phase 5: Complete — investigation_tools trimmed to unique value, no duplication
   - Phase 6: Complete — signal catalog auto-generated from Signal enum
   - Phase 7: Materially complete — remaining gaps are PyBaMM limitations
   - Phase 8: Materially complete — parameter mapping centralized
   - Phase 9: Complete — repo has pyproject.toml, tests, proper packaging
3. Remaining technical debt (minor items not worth blocking audit closure):
   - Convergence diagnostics limited by PyBaMM telemetry availability
   - ParameterExplorer.grid_search() still stubbed
   - Teaching docstrings could be trimmed in a future pass
4. Architectural guard rails now in place (test_architecture.py)
5. A clear "AUDIT CLOSED" verdict
6. A "What we learned" section — summarize the key architectural principles applied across all 5 rounds (for the user's future reference)

TASK E2 — Write README.md

WHY (explain to user):
The README is the "front door" of your project. When someone (including future-you) opens the repo, it's the first thing they see. A good README answers three questions in under 60 seconds: "What is this?", "How do I install it?", "How do I use it?". Everything else is secondary. If your README can't answer those three questions, people leave.

Create a README.md at the repo root (/home/clement/battery_sim/README.md) with:

1. Project title and one-paragraph description
2. Installation:
   ```bash
   pip install -e .
   # or with dev dependencies:
   pip install -e ".[dev]"
   ```
3. Quick start example showing:
   - Creating a Cell from preset
   - Setting up a Protocol
   - Running a Simulation
   - Accessing results from SimulationRun
4. Architecture overview (2-3 sentences pointing to docs/audit/01_target_architecture.md)
5. Running tests: `pytest tests/`
6. Dependencies: PyBaMM, NumPy, (optional) matplotlib

Keep it concise — under 100 lines. Explain to the user the "README-driven development" philosophy: if you can't explain your project simply in the README, the design might be too complex.

TASK E3 — Archive the audit

WHY (explain to user):
Archiving doesn't mean deleting. It means marking documents so readers know their status: "this is historical context" vs. "this is current guidance." A common mistake is leaving old planning documents alongside current ones with no indication of which is which. A simple header note solves this.

What to do:
1. The audit documents in docs/audit/ (00 through 07) should remain in place as the current architecture reference
2. Add a brief note at the top of docs/audit/04_next_session_prompt.md marking it as SUPERSEDED by 07_audit_closure_2026-03-24.md
3. Do NOT move or delete any audit documents

AFTER ALL TASKS — Write a "Complete Audit Learning Summary":
This is the capstone summary. List the key concepts the user learned across all 5 rounds:
- Round 1: Dependency Inversion, Adapter Pattern, Separation of Concerns
- Round 2: DRY principle, recognizing dead abstraction layers, facade vs. wrapper
- Round 3: Python packaging, testing pyramid, architectural fitness functions
- Round 4: Single Source of Truth, code generation from metadata, code smells
- Round 5: Documentation as code, Architecture Decision Records, README-driven development

End with a "What to explore next" list: 3-5 topics the user could study to continue growing (e.g., "hexagonal architecture", "property-based testing", "continuous integration").

VERIFICATION:
- README.md exists at repo root and renders correctly
- docs/audit/07_audit_closure_2026-03-24.md exists with clear phase statuses
- All tests still pass: `pytest tests/ -v`
```

---

## Quick Reference — Execution Order

| Round | Theme | Key Concepts Learned | Depends On |
|-------|-------|---------------------|-----------|
| **1** | Fix architecture violations | Dependency Inversion, Adapter Pattern, Dependency Injection | Nothing |
| **2** | Eliminate duplication | DRY, facade vs. dead wrapper, honest dependency graphs | Round 1 |
| **3** | Packaging & tests | Python packaging, testing pyramid, architectural fitness functions | Round 1+2 |
| **4** | Introspection & quality | Single Source of Truth, code smells, separation of data & presentation | Round 1+2 |
| **5** | Documentation closure | ADRs, README-driven development, documentation as code | Round 1-4 |

> **Tip for the learner:** After each round, re-read the "What you just learned" summaries and try to explain the concepts to someone else (or write them down in your own words). Teaching is the fastest way to solidify understanding.
