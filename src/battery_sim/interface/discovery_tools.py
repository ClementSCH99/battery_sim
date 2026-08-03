"""Derived agent-tool discovery and API presentation."""

import inspect
from typing import Any, Callable

from battery_sim.core.api_schema import APISchema
from battery_sim.core.result_formatter import DualFormatResult


def discover_agent_tools(api: Any) -> list[dict[str, Any]]:
    """Derive the callable catalog from decorated methods on the real facade."""
    tools: list[dict[str, Any]] = []
    for name, member in vars(type(api)).items():
        if not callable(member) or not getattr(member, "_is_agent_tool", False):
            continue
        signature = inspect.signature(getattr(api, name))
        parameters: dict[str, dict[str, Any]] = {}
        for parameter_name, parameter in signature.parameters.items():
            annotation = parameter.annotation
            if annotation is inspect.Parameter.empty:
                type_name = "unknown"
            else:
                type_name = getattr(annotation, "__name__", str(annotation))
                type_name = type_name.replace("typing.", "")
            definition: dict[str, Any] = {
                "type": type_name,
                "required": parameter.default is inspect.Parameter.empty,
            }
            if parameter.default is not inspect.Parameter.empty:
                definition["default"] = parameter.default
            parameters[parameter_name] = definition
        tools.append(
            {
                "name": name,
                "description": getattr(member, "_tool_description", ""),
                "maturity": getattr(member, "_tool_maturity", "experimental"),
                "parameters": parameters,
                "examples": list(getattr(member, "_tool_examples", [])),
            }
        )
    maturity_order = {"core": 0, "experimental": 1, "legacy": 2}
    return sorted(
        tools,
        key=lambda tool: maturity_order.get(tool["maturity"], 99),
    )


class DiscoveryToolHandler:
    """Present the domain schema and executable tool catalog core-first."""

    def __init__(
        self,
        *,
        schema: APISchema,
        catalog_provider: Callable[[], list[dict[str, Any]]],
    ) -> None:
        self._schema = schema
        self._catalog_provider = catalog_provider

    def describe(self) -> DualFormatResult:
        workflow = [
            "describe_api",
            "list_presets",
            "plan_experiment",
            "run_simulation",
            "compare_test_data",
            "get_session_summary",
        ]
        markdown = "\n".join(
            [
                "# Battery Simulation API Overview",
                "",
                "The core workflow plans, executes, checks and compares cell-level experiments.",
                "Experimental pack, vehicle, charging and ageing screeners remain callable but secondary.",
                "",
                "## Recommended workflow",
                *[f"{index}. `{name}`" for index, name in enumerate(workflow, start=1)],
                "",
                self._schema.full_summary(),
            ]
        )
        return DualFormatResult(
            json_data={
                "type": "api_description",
                "default_tool_profile": "core_first",
                "recommended_workflow": workflow,
                "tools": self._catalog_provider(),
            },
            markdown_text=markdown,
            interpretation_hints=[
                "Plan before executing when assumptions are incomplete",
                "Use sourced test comparison before claiming model validity",
                "Treat experimental tools as screening only",
            ],
        )
