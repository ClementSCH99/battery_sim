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
    content_blocks = result[0] if isinstance(result, tuple) else result
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
    """get_session_summary returns a string through MCP."""

    def test_returns_string(self):
        """Session summary is returned as text (not JSON-wrapped)."""
        from mcp_server import mcp

        async def _invoke():
            return await mcp.call_tool("get_session_summary", {})

        result = _run(_invoke())
        content_blocks = result[0] if isinstance(result, tuple) else result
        text = content_blocks[0].text
        # Session summary is plain text / markdown, not necessarily JSON
        assert isinstance(text, str)
        assert len(text) > 0
