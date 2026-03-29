"""Architectural regression tests.

These tests enforce the dependency rules from the target architecture:
- Core domain must not import from backend infrastructure
- All public simulation paths return SimulationRun
- Signal vocabulary is consistent between runtime and schema

These are "fitness functions" — automated checks that run in CI and catch
architecture erosion before it becomes entrenched. They don't test behavior
(does the code produce correct output?), they test structure (does the code
follow the rules we set?).

Unlike unit tests that break when behavior changes, architectural tests break
when someone violates a design rule — making them extremely high-value guards
that prevent the most expensive kind of bugs: structural ones.
"""
import ast
import inspect
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CORE_DIR = Path(__file__).resolve().parent.parent / "core"


def _core_python_files():
    """Yield all .py files in the core/ package."""
    return sorted(CORE_DIR.glob("*.py"))


# ---------------------------------------------------------------------------
# Test 1: No core → backend imports
# ---------------------------------------------------------------------------

class TestNoCoreBackendImports:
    """Core domain must NEVER import from backend infrastructure.

    The only file allowed to mention 'backend' is simulation_backend.py —
    that's the abstract *port* (interface), not concrete infrastructure.

    WHY: If core/ depends on backend/, you can't swap simulation engines
    without modifying the domain.  Dependencies must point inward
    (infrastructure → domain), never outward (domain → infrastructure).
    """

    # Files that are allowed to reference "backend":
    # - simulation_backend.py: defines the abstract port (interface)
    # - agent_api.py: interface/outer layer — allowed to pick the concrete backend
    # - __init__.py: package marker
    ALLOWED_FILES = {"simulation_backend.py", "agent_api.py", "__init__.py"}

    def _imports_from_backend(self, filepath: Path) -> list[str]:
        """Return any import lines that reference battery_sim.backend."""
        violations = []
        source = filepath.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("battery_sim.backend"):
                    violations.append(
                        f"line {node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("battery_sim.backend"):
                        violations.append(
                            f"line {node.lineno}: import {alias.name}"
                        )
        return violations

    def test_no_core_imports_backend(self):
        """No file in core/ should import from battery_sim.backend."""
        all_violations: dict[str, list[str]] = {}

        for py_file in _core_python_files():
            if py_file.name in self.ALLOWED_FILES:
                continue
            violations = self._imports_from_backend(py_file)
            if violations:
                all_violations[py_file.name] = violations

        assert not all_violations, (
            "Core domain files import from backend infrastructure!\n"
            + "\n".join(
                f"  {name}: {'; '.join(v)}"
                for name, v in all_violations.items()
            )
        )


# ---------------------------------------------------------------------------
# Test 2: SimulationRun is the canonical output type
# ---------------------------------------------------------------------------

class TestSimulationRunCanonicalOutput:
    """Every public simulation execution path must return SimulationRun.

    This ensures a consistent contract: no matter how you trigger a
    simulation (Simulation.run, ExecutionService.execute, or
    SimulationBackend.run), you always get the same rich output type.
    """

    @staticmethod
    def _get_return_annotation(cls, method_name: str) -> str:
        """Get the return annotation string for a method."""
        method = getattr(cls, method_name)
        ann = inspect.get_annotations(method, eval_str=False)
        ret = ann.get("return", None)
        # Handle both string annotations and actual types
        if ret is None:
            return ""
        return ret if isinstance(ret, str) else getattr(ret, "__name__", str(ret))

    def test_simulation_backend_run_returns_simulation_run(self):
        from battery_sim.core.simulation_backend import SimulationBackend

        ret = self._get_return_annotation(SimulationBackend, "run")
        assert "SimulationRun" in ret, (
            f"SimulationBackend.run() should return SimulationRun, got: {ret}"
        )

    def test_execution_service_execute_returns_simulation_run(self):
        from battery_sim.core.application_services import SimulationExecutionService

        ret = self._get_return_annotation(SimulationExecutionService, "execute")
        assert "SimulationRun" in ret, (
            f"SimulationExecutionService.execute() should return SimulationRun, got: {ret}"
        )

    def test_simulation_run_returns_simulation_run(self):
        from battery_sim.core.simulation import Simulation

        ret = self._get_return_annotation(Simulation, "run")
        assert "SimulationRun" in ret, (
            f"Simulation.run() should return SimulationRun, got: {ret}"
        )


# ---------------------------------------------------------------------------
# Test 3: Signal vocabulary consistency
# ---------------------------------------------------------------------------

class TestSignalVocabularyConsistency:
    """The API schema's signal catalog must stay in sync with the Signal enum.

    The Signal enum in types/signal.py is the Single Source of Truth.
    The API schema builds SignalDefinition objects from those values.
    If someone adds a Signal enum member but forgets to add it to the
    schema (or vice-versa), this test catches the drift.
    """

    def test_all_signal_enum_values_in_schema(self):
        """Every Signal enum member should appear in the schema catalog."""
        from battery_sim.types.signal import Signal
        from battery_sim.core.api_schema import APISchema

        schema = APISchema()
        catalog = schema.get_signals()
        catalog_names = set(catalog.signals.keys())

        missing = []
        for sig in Signal:
            if sig.value not in catalog_names:
                missing.append(sig.name)

        assert not missing, (
            f"Signal enum members missing from API schema catalog: {missing}"
        )

    def test_schema_signals_are_valid(self):
        """Every signal in the schema catalog should either be a Signal enum
        value or a documented derived metric (like peak_voltage_V)."""
        from battery_sim.types.signal import Signal
        from battery_sim.core.api_schema import APISchema

        schema = APISchema()
        catalog = schema.get_signals()

        enum_values = {sig.value for sig in Signal}
        # Derived summary metrics are allowed — they're not in the enum
        # but they're documented extras (e.g., peak_voltage_V)
        for name in catalog.signals:
            if name not in enum_values:
                # It's okay if it's a derived metric, but it must have a unit
                defn = catalog.signals[name]
                assert defn.unit, (
                    f"Schema signal '{name}' is not in Signal enum and has no unit"
                )
