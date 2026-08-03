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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "src" / "battery_sim"
CORE_DIR = PACKAGE_ROOT / "core"
INTERFACE_DIR = PACKAGE_ROOT / "interface"
PYBAMM_BACKEND = PACKAGE_ROOT / "backend" / "pybamm_backend.py"
APPLICATION_SERVICES_SHIM = CORE_DIR / "application_services.py"
INVESTIGATION_TOOLS = CORE_DIR / "investigation_tools.py"
PARAMETER_SWEEP_FACADE = CORE_DIR / "parameter_sweep.py"
AGENT_API_FACADE = CORE_DIR / "agent_api.py"


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


class TestInterfaceDependsOnPorts:
    """Extracted interface handlers must not select concrete backends."""

    def test_interface_does_not_import_backend_implementations(self):
        violations = []
        for filepath in sorted(INTERFACE_DIR.glob("*.py")):
            tree = ast.parse(filepath.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("battery_sim.backend"):
                        violations.append(f"{filepath.name}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("battery_sim.backend"):
                            violations.append(f"{filepath.name}:{node.lineno}")

        assert not violations, (
            "Interface handlers must receive SimulationBackend through the core port: "
            + ", ".join(violations)
        )


class TestPyBaMMBackendResponsibilities:
    """Signal extraction must remain outside the backend orchestrator."""

    def test_result_extraction_delegates_to_focused_component(self):
        from battery_sim.backend.pybamm_backend import PyBaMMBackend

        source = inspect.getsource(PyBaMMBackend._extract_result)

        assert "PyBaMMResultExtractor" in source
        assert len(source.splitlines()) <= 5

    def test_problem_construction_delegates_to_focused_component(self):
        from battery_sim.backend.pybamm_backend import PyBaMMBackend

        source = inspect.getsource(PyBaMMBackend._execute_simulation)

        assert "PyBaMMProblemBuilder" in source
        assert "build_model(" not in source
        assert "build_parameters(" not in source

    def test_observability_delegates_to_focused_component(self):
        from battery_sim.backend.pybamm_backend import PyBaMMBackend

        source = inspect.getsource(PyBaMMBackend._build_observability_data)

        assert "PyBaMMObservabilityBuilder" in source

    def test_backend_stays_a_small_orchestrator(self):
        source = PYBAMM_BACKEND.read_text()

        assert len(source.splitlines()) <= 150


class TestFocusedApplicationServices:
    """Keep the old module as compatibility only and use focused services internally."""

    def test_legacy_application_services_module_defines_no_classes(self):
        tree = ast.parse(APPLICATION_SERVICES_SHIM.read_text())

        class_names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]

        assert class_names == []

    def test_active_code_does_not_import_legacy_services_module(self):
        violations = []
        source_files = [
            *CORE_DIR.glob("*.py"),
            *INTERFACE_DIR.glob("*.py"),
        ]
        for filepath in source_files:
            if filepath == APPLICATION_SERVICES_SHIM:
                continue
            tree = ast.parse(filepath.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "battery_sim.core.application_services"
                ):
                    violations.append(f"{filepath.name}:{node.lineno}")

        assert not violations, (
            "Active code must import focused battery_sim.core.services modules: "
            + ", ".join(violations)
        )

    def test_investigation_compatibility_module_stays_small(self):
        assert len(INVESTIGATION_TOOLS.read_text().splitlines()) <= 350

    def test_typed_parameter_sweep_facade_stays_small(self):
        assert len(PARAMETER_SWEEP_FACADE.read_text().splitlines()) <= 220

    def test_agent_api_facade_does_not_regrow(self):
        assert len(AGENT_API_FACADE.read_text().splitlines()) <= 700

    def test_discovery_methods_delegate_to_focused_handler(self):
        from battery_sim.core.agent_api import AgentAPI

        catalog_source = inspect.getsource(AgentAPI.get_available_tools)
        description_source = inspect.getsource(AgentAPI.describe_api)

        assert "discover_agent_tools" in catalog_source
        assert "self._discovery_tools" in description_source


class TestExperimentalToolExtraction:
    """Extracted experimental methods must stay thin compatibility delegates."""

    @pytest.mark.parametrize("method_name", ["predict_lifetime", "warranty_analysis"])
    def test_degradation_methods_delegate_to_handler(self, method_name):
        from battery_sim.core.agent_api import AgentAPI

        source = inspect.getsource(getattr(AgentAPI, method_name))

        assert "self._degradation_tools" in source
        assert len(source.splitlines()) <= 25

    @pytest.mark.parametrize(
        "method_name",
        ["pack_sizing", "cell_selection_wizard", "estimate_range"],
    )
    def test_vehicle_methods_delegate_to_handler(self, method_name):
        from battery_sim.core.agent_api import AgentAPI

        source = inspect.getsource(getattr(AgentAPI, method_name))

        assert "self._vehicle_tools" in source
        assert len(source.splitlines()) <= 35

    def test_model_to_test_method_delegates_to_handler(self):
        from battery_sim.core.agent_api import AgentAPI

        source = inspect.getsource(AgentAPI.compare_test_data)

        assert "self._test_comparison_tools" in source
        assert len(source.splitlines()) <= 40

    @pytest.mark.parametrize(
        "method_name",
        ["optimize_charging", "compare_charging_strategies"],
    )
    def test_charging_methods_delegate_to_handler(self, method_name):
        from battery_sim.core.agent_api import AgentAPI

        source = inspect.getsource(getattr(AgentAPI, method_name))

        assert "self._charging_tools" in source
        assert len(source.splitlines()) <= 35

    @pytest.mark.parametrize("method_name", ["operating_window", "derating_curves"])
    def test_operating_methods_delegate_to_handler(self, method_name):
        from battery_sim.core.agent_api import AgentAPI

        source = inspect.getsource(getattr(AgentAPI, method_name))

        assert "self._operating_tools" in source
        assert len(source.splitlines()) <= 35


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
        from battery_sim.core.simulation import SimulationBackend

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
        from battery_sim.core.result import Signal
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
        from battery_sim.core.result import Signal
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

    def test_backend_and_schema_units_match(self):
        """Runtime extraction units must agree with the public signal catalog."""
        from battery_sim.backend.pybamm_signal import (
            DERIVED_SIGNALS,
            PYBAMM_SIGNAL_MAP,
        )
        from battery_sim.core.api_schema import APISchema
        from battery_sim.core.result import Signal

        catalog = APISchema().get_signals().signals
        runtime_units = {
            signal: definition[1]
            for signal, definition in {**PYBAMM_SIGNAL_MAP, **DERIVED_SIGNALS}.items()
        }
        # SOC is read dimensionless from PyBaMM and explicitly converted to %
        # by PyBaMMBackend before constructing the TimeSeries.
        runtime_units[Signal.SOC] = "%"

        mismatches = {
            signal.value: (unit, catalog[signal.value].unit)
            for signal, unit in runtime_units.items()
            if unit != catalog[signal.value].unit
        }
        assert mismatches == {}


class TestToolDiscoverySingleSource:
    """APISchema must not maintain a second manual operation catalog."""

    def test_api_schema_contains_only_scientific_domain_metadata(self):
        from battery_sim.core.api_schema import APISchema

        schema = APISchema()

        assert not hasattr(schema, "get_tools")
        assert "tools" not in schema.to_dict()
