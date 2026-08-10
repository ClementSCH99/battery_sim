"""Derived agent-tool discovery and API presentation."""

import inspect
from typing import Any, Callable

from battery_sim.interfaces.python.schema import APISchema
from battery_sim.interfaces.presenters.result import DualFormatResult


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
        tools = self._catalog_provider()
        by_name = {tool["name"]: tool for tool in tools}
        by_name["pack_sizing"]["parameters"] = {
            "preset_name": {"type": "str", "required": True},
            "target_energy_kWh": {"type": "float", "required": False, "default": 60.0},
            "voltage_range_min_V": {"type": "float", "required": False, "default": 300.0},
            "voltage_range_max_V": {"type": "float", "required": False, "default": 400.0},
        }
        by_name["optimize_charging"]["parameters"] = {
            "preset_name": {"type": "str", "required": True},
            "charge_current_min_A": {"type": "float", "required": False, "default": 1.0},
            "charge_current_max_A": {"type": "float", "required": False, "default": 10.0},
            "n_sweep_points": {"type": "int", "required": False, "default": 5},
            "temperature_C": {"type": "float", "required": False, "default": 25.0},
        }
        by_name["sensitivity_analysis"]["parameters"]["parameters"].update({
            "allowed_values": ["temperature_C"],
            "response_metric": "peak_power_W",
        })
        by_name["plan_experiment"]["parameters"]["model"]["allowed_values"] = [
            "single_particle", "single_particle_electrolyte", "doyle_fuller_newman"
        ]
        by_name["plan_experiment"]["parameters"]["requested_signals"]["allowed_values"] = [
            "time", "voltage", "current", "power", "energy", "soc", "soh",
            "capacity", "temperature", "cell_temperature", "heat_generation",
            "internal_resistance", "electrolyte_concentration", "electrolyte_potential",
        ]
        by_name["estimate_range"]["parameters"]["cycle_name"]["allowed_values"] = [
            "WLTP", "WLTP_CLASS3", "US06", "UDDS"
        ]
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
                "tools": tools,
            },
            markdown_text=markdown,
            interpretation_hints=[
                "Plan before executing when assumptions are incomplete",
                "Use sourced test comparison before claiming model validity",
                "Treat experimental tools as screening only",
            ],
        )
