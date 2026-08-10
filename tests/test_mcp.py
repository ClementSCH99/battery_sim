"""MCP server tests — schema validation and round-trip invocation.

TEACHING FOCUS: Testing an MCP server at two levels

MCP servers wrap application logic and expose it over a protocol.
Testing them requires verifying TWO distinct things:

1. **Schema correctness** (fast, no simulation):
   Does the server declare the right tools with the right parameter types?
   This catches wiring mistakes: a tool registered with the wrong name,
   a missing required parameter, or a wrong type annotation.

2. **Round-trip invocation** (slow, runs PyBaMM):
   Does calling a tool through the MCP interface actually reach the
   application layer, run a simulation, and return valid JSON?
   This catches integration bugs: serialisation errors, missing imports,
   or AgentAPI methods that don't match the MCP wrapper's expectations.

WHY BOTH LEVELS?
Schema tests run in milliseconds — developers get instant feedback when
they change a tool signature.  Round-trip tests take seconds but prove
the full pipe works.  Together they provide confidence without waste.

APPROACH:
We use FastMCP's async introspection API (list_tools, call_tool) directly,
which tests the same code path as a real MCP client without needing a
subprocess or transport layer.  This is "Approach A" from the test plan
— direct function testing — but exercised through the MCP SDK's own
dispatch, not by importing raw Python functions.
"""

import asyncio
import json
from functools import lru_cache
from typing import Any, cast

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously (avoids repeating asyncio.run)."""
    return asyncio.run(coro)


@lru_cache(maxsize=1)
def _get_tool_map() -> dict:
    """Fetch registered tools once and cache as {name: tool_object}."""
    from mcp_server import mcp

    async def _fetch():
        return {t.name: t for t in await mcp.list_tools()}

    return _run(_fetch())


def _schema(tool_name: str) -> dict:
    """Return the inputSchema dict for a given tool."""
    return _get_tool_map()[tool_name].inputSchema


def _call_tool(name: str, arguments: dict | None = None) -> dict:
    """Call an MCP tool and return parsed JSON from the first TextContent."""
    from mcp_server import mcp

    async def _invoke():
        return await mcp.call_tool(name, arguments or {})

    result = _run(_invoke())
    # call_tool returns (list[ContentBlock], ...) — first element is text list
    content_blocks = cast(list[Any], result[0] if isinstance(result, tuple) else result)
    text = content_blocks[0].text
    return json.loads(text)


# ===========================================================================
# 1. Import smoke test
# ===========================================================================

class TestMCPImport:
    """The MCP server module loads without errors."""

    def test_mcp_server_imports(self):
        """Importing mcp_server should not crash."""
        import mcp_server  # noqa: F401

    def test_mcp_instance_exists(self):
        """The module exposes a FastMCP instance named 'mcp'."""
        from mcp_server import mcp as server
        from mcp.server.fastmcp import FastMCP
        assert isinstance(server, FastMCP)


# ===========================================================================
# 2. Tool registration tests
# ===========================================================================

EXPECTED_TOOLS = {
    "describe_api",
    "plan_experiment",
    "compare_test_data",
    "list_presets",
    "run_simulation",
    "compare_presets",
    "sensitivity_analysis",
    "check_feasibility",
    "get_session_summary",
    "predict_lifetime",
    "warranty_analysis",
    "optimize_charging",
    "operating_window",
    "derating_curves",
    "estimate_range",
    "compare_charging_strategies",
    "pack_sizing",
    "cell_selection_wizard",
}


class TestToolRegistration:
    """All expected tools are registered on the FastMCP server."""

    def test_all_expected_tools_registered(self):
        """Every tool from the spec is present."""
        registered = set(_get_tool_map().keys())
        missing = EXPECTED_TOOLS - registered
        assert not missing, f"Missing tools: {missing}"

    def test_no_unexpected_tools(self):
        """No extra tools beyond what's expected (catches accidental exposure)."""
        registered = set(_get_tool_map().keys())
        extra = registered - EXPECTED_TOOLS
        assert not extra, f"Unexpected tools registered: {extra}"

    def test_every_tool_has_description(self):
        """MCP spec recommends descriptions — verify they are non-empty."""
        for name, tool in _get_tool_map().items():
            assert tool.description, f"Tool '{name}' has no description"


# ===========================================================================
# 3. Schema correctness tests (fast, no PyBaMM)
# ===========================================================================

class TestListPresetsSchema:
    """list_presets has an optional 'chemistry' string parameter."""

    def test_chemistry_is_optional(self):
        schema = _schema("list_presets")
        props = schema["properties"]
        assert "chemistry" in props
        # Optional: has a default of None
        assert props["chemistry"].get("default") is None

    def test_chemistry_accepts_string(self):
        schema = _schema("list_presets")
        prop = schema["properties"]["chemistry"]
        # FastMCP encodes Optional[str] as anyOf: [string, null]
        type_options = {opt["type"] for opt in prop.get("anyOf", [])}
        assert "string" in type_options

    def test_no_required_params(self):
        schema = _schema("list_presets")
        assert "required" not in schema or schema["required"] == []


class TestRunSimulationSchema:
    """run_simulation requires preset_name; others optional."""

    def test_preset_name_required(self):
        schema = _schema("run_simulation")
        assert "preset_name" in schema.get("required", [])

    def test_preset_name_is_string(self):
        schema = _schema("run_simulation")
        assert schema["properties"]["preset_name"]["type"] == "string"

    def test_optional_params_have_defaults(self):
        schema = _schema("run_simulation")
        for param in ("current_A", "duration_s", "temperature_C"):
            assert param in schema["properties"], f"Missing param: {param}"
            assert "default" in schema["properties"][param], (
                f"'{param}' should have a default value"
            )

    def test_temperature_default_is_25(self):
        schema = _schema("run_simulation")
        assert schema["properties"]["temperature_C"]["default"] == 25.0


class TestComparePresetsSchema:
    """compare_presets requires preset_names as list[str]."""

    def test_preset_names_required(self):
        schema = _schema("compare_presets")
        assert "preset_names" in schema.get("required", [])

    def test_preset_names_is_array_of_strings(self):
        schema = _schema("compare_presets")
        prop = schema["properties"]["preset_names"]
        assert prop["type"] == "array"
        assert prop["items"]["type"] == "string"

    def test_environment_temp_is_optional(self):
        schema = _schema("compare_presets")
        assert "environment_temp_C" in schema["properties"]
        assert schema["properties"]["environment_temp_C"].get("default") is None


class TestSensitivityAnalysisSchema:
    """sensitivity_analysis requires preset_name and parameters."""

    def test_required_params(self):
        schema = _schema("sensitivity_analysis")
        required = set(schema.get("required", []))
        assert {"preset_name", "parameters"} == required

    def test_parameters_is_array_of_strings(self):
        schema = _schema("sensitivity_analysis")
        prop = schema["properties"]["parameters"]
        assert prop["type"] == "array"
        assert prop["items"]["type"] == "string"


class TestCheckFeasibilitySchema:
    """check_feasibility requires preset_name; temperature optional."""

    def test_preset_name_required(self):
        schema = _schema("check_feasibility")
        assert "preset_name" in schema.get("required", [])

    def test_temperature_default_is_25(self):
        schema = _schema("check_feasibility")
        assert schema["properties"]["temperature_C"]["default"] == 25.0


class TestGetSessionSummarySchema:
    """get_session_summary takes no parameters."""

    def test_no_properties(self):
        schema = _schema("get_session_summary")
        props = schema.get("properties", {})
        assert len(props) == 0


class TestMCPBoundaryValidation:
    """Raw wrapper functions return structured validation errors."""

    @staticmethod
    def _assert_validation_error(raw_result: str, message_fragment: str) -> None:
        payload = json.loads(raw_result)
        assert payload["error"] is True
        assert payload["error_type"] == "ValidationError"
        assert message_fragment in payload["message"]

    def test_optimize_charging_rejects_inverted_current_range(self):
        from mcp_server import optimize_charging

        raw_result = optimize_charging(
            preset_name="LFP_5AH",
            charge_current_min_A=5.0,
            charge_current_max_A=1.0,
        )
        self._assert_validation_error(raw_result, "charge_current_min_A")

    def test_compare_presets_rejects_empty_list(self):
        from mcp_server import compare_presets

        raw_result = compare_presets([])
        self._assert_validation_error(raw_result, "preset_names")

    def test_pack_sizing_rejects_invalid_voltage_range(self):
        from mcp_server import pack_sizing

        raw_result = pack_sizing(
            preset_name="LFP_5AH",
            target_energy_kWh=60.0,
            voltage_range_min_V=400.0,
            voltage_range_max_V=300.0,
        )
        self._assert_validation_error(raw_result, "voltage_range_min_V")

    def test_compare_charging_strategies_rejects_zero_cycles(self):
        from mcp_server import compare_charging_strategies

        raw_result = compare_charging_strategies(
            preset_name="LFP_5AH",
            n_cycles=0,
        )
        self._assert_validation_error(raw_result, "n_cycles")

    def test_invalid_preset_name_returns_available_presets(self):
        from mcp_server import run_simulation

        raw_result = run_simulation(
            preset_name="NOT_A_PRESET",
            duration_s=30.0,
        )
        payload = json.loads(raw_result)
        assert payload["error"] is True
        assert payload["error_type"] == "ValidationError"
        assert "Unknown preset_name" in payload["message"]
        assert "Available presets:" in payload["message"]

    def test_out_of_range_temperature_returns_validation_error(self):
        from mcp_server import check_feasibility

        raw_result = check_feasibility(
            preset_name="LFP_5AH",
            temperature_C=150.0,
        )
        self._assert_validation_error(raw_result, "temperature_C")

    def test_invalid_grid_size_returns_validation_error(self):
        from mcp_server import operating_window

        raw_result = operating_window(
            preset_name="LFP_5AH",
            grid_size="ultra",
        )
        self._assert_validation_error(raw_result, "grid_size")

    def test_unimplemented_medium_grid_is_rejected_at_boundary(self):
        from mcp_server import operating_window

        raw_result = operating_window(
            preset_name="LFP_5AH",
            grid_size="medium",
        )
        self._assert_validation_error(raw_result, "grid_size")

    def test_invalid_cycle_name_returns_validation_error(self):
        from mcp_server import estimate_range

        raw_result = estimate_range(
            preset_name="LFP_5AH",
            cycle_name="BAD_CYCLE",
        )
        payload = json.loads(raw_result)
        assert payload["error"] is True
        assert payload["error_type"] == "ValidationError"
        assert "cycle_name" in payload["message"]
        assert "WLTP" in payload["message"]

    def test_error_payload_has_stable_contract_metadata(self):
        from mcp_server import optimize_charging

        payload = json.loads(
            optimize_charging(
                preset_name="LFP_5AH",
                charge_current_min_A=5.0,
                charge_current_max_A=1.0,
            )
        )

        assert payload["tool"] == "optimize_charging"
        assert payload["maturity"] == "experimental"
        assert payload["error_code"] == "validation_error"
        assert payload["retryable"] is False
        assert payload["contract"]["schema_version"] == "2.0"
        assert payload["ok"] is False
        assert payload["response"]["status"] == "error"


class TestMCPResponseContract:
    def test_success_payload_includes_derived_maturity_and_domain(self):
        from mcp_server import list_presets

        payload = json.loads(list_presets())

        assert payload["tool"] == "list_presets"
        assert payload["maturity"] == "core"
        assert payload["contract"]["maturity"] == "core"
        assert payload["contract"]["domain_of_validity"]
        assert payload["contract"]["assumptions"]

    def test_error_payload_also_exposes_assumptions(self):
        from mcp_server import run_simulation

        payload = json.loads(run_simulation(preset_name="UNKNOWN"))

        assert payload["error"] is True
        assert payload["contract"]["assumptions"]

    def test_session_summary_uses_the_same_json_contract(self):
        from mcp_server import get_session_summary

        payload = json.loads(get_session_summary())

        assert payload["type"] == "session_summary"
        assert isinstance(payload["summary"], str)
        assert payload["contract"]["assumptions"]

    def test_describe_api_is_exposed_as_core_discovery_tool(self):
        from mcp_server import describe_api

        payload = json.loads(describe_api())

        assert payload["type"] == "api_description"
        assert payload["tool"] == "describe_api"
        assert payload["maturity"] == "core"
        assert payload["default_tool_profile"] == "core_first"
        assert payload["recommended_workflow"][0] == "describe_api"

    def test_plan_experiment_exposes_missing_inputs_without_executing(self):
        from mcp_server import plan_experiment

        payload = json.loads(plan_experiment(question="Characterize voltage response"))

        assert payload["type"] == "experiment_plan"
        assert payload["status"] == "needs_input"
        assert payload["ready_for_execution"] is False
        assert "preset_name" in payload["missing_inputs"]
        assert payload["tool"] == "plan_experiment"
        assert payload["maturity"] == "core"

    def test_plan_experiment_extracts_supported_question_fields_with_evidence(self):
        from mcp_server import plan_experiment

        payload = json.loads(
            plan_experiment(
                question=(
                    "Simule une décharge de NMC_CHEN_LGM50 à -10 °C "
                    "et donne la tension."
                )
            )
        )

        assert payload["status"] == "draft_ready"
        assert payload["configuration"]["preset_name"] == "NMC_CHEN_LGM50"
        assert payload["configuration"]["ambient_temperature_C"] == -10.0
        evidence = payload["traceability"]["question_interpretation"]["fields"]
        assert evidence["preset_name"]["evidence"] == "NMC_CHEN_LGM50"

    def test_temperature_extracted_from_question_uses_boundary_validation(self):
        from mcp_server import plan_experiment

        payload = json.loads(
            plan_experiment(
                question="Décharge NMC_CHEN_LGM50 à 125 °C"
            )
        )

        assert payload["error"] is True
        assert payload["error_code"] == "validation_error"
        assert "temperature_C" in payload["message"]

    def test_test_comparison_rejects_misaligned_trace_at_boundary(self):
        from mcp_server import compare_test_data

        payload = json.loads(
            compare_test_data(
                preset_name="NMC_CHEN_LGM50",
                source="cycler export",
                time_s=[0.0, 1.0, 2.0],
                voltage_V=[4.1, 4.0],
                applied_current_A=5.0,
            )
        )

        assert payload["error"] is True
        assert payload["error_code"] == "validation_error"
        assert "same length" in payload["message"]

    def test_every_core_agent_tool_has_an_mcp_wrapper(self):
        import mcp_server

        core_names = {
            tool["name"]
            for tool in mcp_server.api.get_available_tools()
            if tool["maturity"] == "core"
        }
        exposed = {
            name
            for name, value in vars(mcp_server).items()
            if name in core_names and callable(value)
        }

        assert exposed == core_names


# ===========================================================================
# 4. Round-trip invocation tests (slow, require PyBaMM)
# ===========================================================================

@pytest.mark.slow
class TestListPresetsRoundTrip:
    """list_presets returns valid preset data through the MCP interface."""

    def test_returns_preset_list(self):
        data = _call_tool("list_presets")
        assert data["type"] == "preset_list"
        assert "presets" in data
        assert len(data["presets"]) > 0

    def test_each_preset_has_required_fields(self):
        data = _call_tool("list_presets")
        required_keys = {"name", "chemistry", "capacity_Ah", "nominal_voltage_V"}
        for preset in data["presets"]:
            missing = required_keys - set(preset.keys())
            assert not missing, f"Preset {preset.get('name')} missing: {missing}"

    def test_filter_by_chemistry(self):
        data = _call_tool("list_presets", {"chemistry": "LFP"})
        assert all(p["chemistry"] == "LFP" for p in data["presets"])


@pytest.mark.slow
class TestRunSimulationRoundTrip:
    """run_simulation returns metrics through the MCP interface."""

    def test_returns_simulation_result(self):
        data = _call_tool("run_simulation", {
            "preset_name": "LFP_5AH",
            "duration_s": 60,
        })
        assert data["type"] == "simulation_result"
        assert data["preset"] == "LFP_5AH"
        assert data["simulation_id"]
        assert "metrics" in data
        assert isinstance(data["metrics"], dict)
        assert len(data["metrics"]) > 0

    def test_custom_temperature(self):
        data = _call_tool("run_simulation", {
            "preset_name": "LFP_5AH",
            "duration_s": 60,
            "temperature_C": 35.0,
        })
        assert data["temperature_C"] == 35.0


@pytest.mark.slow
class TestCompareTestDataRoundTrip:
    """A sourced trace reaches PyBaMM and returns explicit residual evidence."""

    def test_returns_model_to_test_comparison(self):
        data = _call_tool(
            "compare_test_data",
            {
                "preset_name": "NMC_CHEN_LGM50",
                "source": "synthetic MCP integration fixture",
                "test_id": "MCP-TRACE-001",
                "time_s": [0.0, 5.0, 10.0],
                "voltage_V": [4.18, 4.17, 4.16],
                "applied_current_A": 5.0,
                "measured_current_A": [-5.0, -5.0, -5.0],
                "current_sign_convention": "discharge_negative",
                "temperature_C": 25.0,
            },
        )

        assert data["type"] == "test_comparison"
        assert data["simulation_id"]
        assert data["coverage"]["extrapolation_used"] is False
        assert data["metrics"]["voltage_rmse_V"] >= 0
        assert data["evidence"]["parameter_fitting_performed"] is False
        assert data["assessment"]["confidence"] in {"low", "insufficient"}
        assert data["assessment"]["decision_ready"] is False
        assert data["assessment"]["next_experiments"]
        assert data["contract"]["assumptions"]

@pytest.mark.slow
class TestCheckFeasibilityRoundTrip:
    """check_feasibility returns feasibility verdict through MCP."""

    def test_returns_feasibility_result(self):
        data = _call_tool("check_feasibility", {"preset_name": "LFP_5AH"})
        assert data["type"] == "feasibility_check"
        assert "feasible" in data
        assert isinstance(data["feasible"], bool)

    def test_includes_preset_and_temperature(self):
        data = _call_tool("check_feasibility", {
            "preset_name": "LFP_5AH",
            "temperature_C": 40.0,
        })
        assert data["preset"] == "LFP_5AH"
        assert data["ambient_temperature_C"] == 40.0


@pytest.mark.slow
class TestGetSessionSummaryRoundTrip:
    """get_session_summary returns the shared JSON envelope through MCP."""

    def test_returns_string(self):
        """Session summary remains text inside a machine-readable response."""
        from mcp_server import mcp

        async def _invoke():
            return await mcp.call_tool("get_session_summary", {})

        result = _run(_invoke())
        content_blocks = cast(list[Any], result[0] if isinstance(result, tuple) else result)
        payload = json.loads(content_blocks[0].text)
        assert payload["type"] == "session_summary"
        assert isinstance(payload["summary"], str)
        assert payload["summary"]
        assert payload["contract"]["assumptions"]
