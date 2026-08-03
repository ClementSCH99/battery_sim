"""Guards for the small canonical documentation surface."""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"

CANONICAL_ROOT_DOCUMENTS = {
    "README.md",
    "architecture.md",
    "physics_and_validation.md",
    "project_direction.md",
    "roadmap.md",
}
CANONICAL_GUIDES = {
    "experiment_planning.md",
    "getting_started.md",
    "mcp.md",
    "test_comparison.md",
}
OBSOLETE_ACTIVE_REFERENCES = {
    "battery_sim.core.model",
    "battery_sim.core.protocol",
    "battery_sim.core.environment",
    "battery_sim.backend",
    "battery_sim.interface.",
    "core/agent_api.py",
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _canonical_documents() -> list[Path]:
    return [
        PROJECT_ROOT / "README.md",
        *(DOCS_ROOT / name for name in sorted(CANONICAL_ROOT_DOCUMENTS)),
        *(DOCS_ROOT / "guides" / name for name in sorted(CANONICAL_GUIDES)),
    ]


def test_documentation_surface_is_deliberately_small():
    root_documents = {
        path.name for path in DOCS_ROOT.glob("*.md")
    }
    guide_documents = {
        path.name for path in (DOCS_ROOT / "guides").glob("*.md")
    }

    assert root_documents == CANONICAL_ROOT_DOCUMENTS
    assert guide_documents == CANONICAL_GUIDES
    assert (DOCS_ROOT / "legacy" / "README.md").is_file()


def test_canonical_documents_do_not_use_pre_src_imports():
    violations: list[str] = []
    for path in _canonical_documents():
        text = path.read_text(encoding="utf-8")
        for reference in OBSOLETE_ACTIVE_REFERENCES:
            if reference in text:
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)} contains {reference}"
                )

    assert violations == []


def test_relative_links_in_canonical_documents_exist():
    broken: list[str] = []
    for path in _canonical_documents():
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or target.startswith(
                ("http://", "https://", "mailto:")
            ):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                broken.append(
                    f"{path.relative_to(PROJECT_ROOT)} -> {raw_target}"
                )

    assert broken == []
