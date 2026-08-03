"""Phase 0 governance checks.

These tests turn the recovery decisions into executable constraints. They are
deliberately structural: scientific validity is covered by separate reference
and model-to-test tests.
"""

import ast
from pathlib import Path

from battery_sim.interface.agent_api import AgentAPI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "src" / "battery_sim"
SOURCE_ROOTS = (
    PACKAGE_ROOT / "core",
    PACKAGE_ROOT / "backend",
    PACKAGE_ROOT / "interface",
    PACKAGE_ROOT / "types",
)
MAX_MODULE_LINES = 300

# Existing debt is frozen. Moving one of these files does not transfer its
# exception: the target module must be split below MAX_MODULE_LINES.
OVERSIZED_MODULE_BUDGETS = {
    Path("core/result_formatter.py"): 951,
    Path("core/api_schema.py"): 948,
    Path("core/agent_api.py"): 700,
    Path("core/cell_presets.py"): 624,
    Path("interface/vehicle_tools.py"): 549,
    Path("core/charging_strategies.py"): 476,
    Path("core/simulation_session.py"): 473,
    Path("core/cell_selection.py"): 447,
    Path("core/operating_window.py"): 446,
    Path("interface/degradation_tools.py"): 443,
    Path("core/simulation_run.py"): 390,
    Path("core/result_analyzer.py"): 370,
    Path("interface/planning_tools.py"): 368,
    Path("core/simulation_error.py"): 353,
    Path("core/protocol.py"): 302,
}

STABLE_CORE_MODULES = {
    "cell.py",
    "environment.py",
    "model.py",
    "protocol.py",
    "solver.py",
    "degradation.py",
    "exceptions.py",
    "simulation.py",
    "simulation_backend.py",
    "simulation_run.py",
    "simulation_metadata.py",
    "simulation_error.py",
    "convergence_diagnostics.py",
    "result/model.py",
    "reference_cases.py",
    "test_trace.py",
}


def _internal_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("battery_sim."):
                imports.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("battery_sim."):
                    imports.append((node.lineno, alias.name))
    return imports


def test_pybamm_is_locked_during_reference_validation():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert '"pybamm==25.12.2"' in pyproject
    assert '"pybamm",' not in pyproject
    assert '"pybamm>=' not in pyproject
    assert '"pybamm~=' not in pyproject


def test_every_tool_has_a_supported_lifecycle():
    tools = AgentAPI().get_available_tools()
    supported = {"core", "experimental", "legacy"}

    assert tools
    assert {tool["maturity"] for tool in tools} <= supported
    assert all(tool["maturity"] in supported for tool in tools)


def test_unvalidated_screeners_are_not_core():
    tools = {
        tool["name"]: tool["maturity"]
        for tool in AgentAPI().get_available_tools()
    }

    assert tools["compare_presets"] == "experimental"
    assert tools["sensitivity_analysis"] == "experimental"
    assert tools["check_feasibility"] == "experimental"


def test_stable_core_does_not_depend_on_interfaces_or_infrastructure():
    violations: list[str] = []
    for module_name in sorted(STABLE_CORE_MODULES):
        path = PACKAGE_ROOT / "core" / module_name
        for line, imported_module in _internal_imports(path):
            if imported_module.startswith(
                ("battery_sim.backend", "battery_sim.interface")
            ):
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{line} imports "
                    f"{imported_module}"
                )

    assert violations == []


def test_module_size_debt_cannot_grow():
    violations: list[str] = []
    seen_budgeted_modules: set[Path] = set()

    for source_root in SOURCE_ROOTS:
        for path in source_root.rglob("*.py"):
            relative_path = path.relative_to(PACKAGE_ROOT)
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            limit = OVERSIZED_MODULE_BUDGETS.get(
                relative_path,
                MAX_MODULE_LINES,
            )
            if relative_path in OVERSIZED_MODULE_BUDGETS:
                seen_budgeted_modules.add(relative_path)
            if line_count > limit:
                violations.append(
                    f"{relative_path}: {line_count} lines exceeds budget {limit}"
                )

    stale_budgets = set(OVERSIZED_MODULE_BUDGETS) - seen_budgeted_modules
    assert not stale_budgets, (
        "Remove obsolete oversized-module budgets after splitting files: "
        + ", ".join(str(path) for path in sorted(stale_budgets))
    )
    assert violations == []


def test_phase0_governance_documents_exist():
    required_documents = {
        "module_matrix.md",
        "architecture_rules.md",
        "api_lifecycle.md",
        "compatibility_inventory.md",
    }
    docs = PROJECT_ROOT / "docs"

    assert required_documents <= {path.name for path in docs.iterdir()}
