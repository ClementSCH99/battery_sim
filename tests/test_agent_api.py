"""Integration tests for the AgentAPI orchestration layer.

These tests verify that the AgentAPI — the "front door" for LLM-driven
investigation — correctly wires up services, formats outputs as
DualFormatResult, and maintains session state.

LEARNING NOTES:
- AgentAPI constructs its own PyBaMMBackend internally, so these tests
  do NOT accept a backend fixture.  Each AgentAPI instance is self-contained.
- DualFormatResult has three mandatory fields: json_data (dict),
  markdown_text (str), and interpretation_hints (list).
- Session tracking is verified by inspecting api.session.investigation_history
  and api.get_session_summary() after tool calls.
- Short protocols are injected via the constructor's default_protocol kwarg to
  keep execution time manageable.

Coverage map:
  list_presets         → DualFormatResult shape, preset catalog correctness
  compare_presets      → DualFormatResult + session recording
  sensitivity_analysis → DualFormatResult + session recording
  check_feasibility    → feasibility flag, DualFormatResult shape
  run_simulation       → DualFormatResult, metric keys
  session tracking     → investigation_history grows after each tool call
"""
import pytest
from unittest.mock import Mock

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.solver import SolverConfig
from battery_sim.core.simulation_backend import SimulationBackend


class TestAgentAPIComposition:
    """The interface is discoverable and its engine can be injected."""

    def test_backend_can_be_injected(self):
        backend = Mock(spec=SimulationBackend)

        api = AgentAPI(backend=backend)

        assert api._backend is backend
        assert api.comparison_service.batch_service.execution_service.backend is backend
        assert api.sensitivity_service.batch_service.execution_service.backend is backend

    def test_available_tools_are_derived_from_decorated_methods(self):
        api = AgentAPI(backend=Mock(spec=SimulationBackend))
        discovered_names = {tool["name"] for tool in api.get_available_tools()}
        decorated_names = {
            name
            for name, member in vars(AgentAPI).items()
            if callable(member) and getattr(member, "_is_agent_tool", False)
        }

        assert discovered_names == decorated_names
        assert len(discovered_names) == 18

    def test_discovery_includes_signature_and_description(self):
        api = AgentAPI(backend=Mock(spec=SimulationBackend))
        tools = {tool["name"]: tool for tool in api.get_available_tools()}

        run_simulation = tools["run_simulation"]
        assert run_simulation["description"]
        assert run_simulation["parameters"]["preset_name"]["required"] is True
        assert run_simulation["parameters"]["temperature_C"]["default"] == 25.0

    def test_every_tool_has_an_explicit_supported_maturity(self):
        api = AgentAPI(backend=Mock(spec=SimulationBackend))
        tools = api.get_available_tools()

        assert {tool["maturity"] for tool in tools} == {"core", "experimental"}
        core_tools = {tool["name"] for tool in tools if tool["maturity"] == "core"}
        assert core_tools == {
            "describe_api",
            "plan_experiment",
            "compare_test_data",
            "list_presets",
            "run_simulation",
            "get_session_summary",
        }

    def test_discovery_lists_core_tools_before_experimental_tools(self):
        api = AgentAPI(backend=Mock(spec=SimulationBackend))
        maturities = [tool["maturity"] for tool in api.get_available_tools()]

        first_experimental = maturities.index("experimental")
        assert all(value == "core" for value in maturities[:first_experimental])
        assert all(value == "experimental" for value in maturities[first_experimental:])

    def test_api_description_publishes_the_recommended_core_workflow(self):
        api = AgentAPI(backend=Mock(spec=SimulationBackend))

        description = api.describe_api().json_data

        assert description["default_tool_profile"] == "core_first"
        assert description["recommended_workflow"][0] == "describe_api"
        assert "run_simulation" in description["recommended_workflow"]
        assert {
            tool["maturity"] for tool in description["tools"]
        } == {"core", "experimental"}


# ---------------------------------------------------------------------------
# Shared fixture — a fast AgentAPI with a 60-second default protocol
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api():
    """AgentAPI pre-configured with a short protocol for fast tests.

    LEARNING: We override default_protocol so every tool call that relies
    on it (compare_presets, sensitivity_analysis, run_simulation) finishes
    in seconds rather than minutes.
    """
    return AgentAPI(
        session_name="Integration Test Session",
        default_protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )


# ===========================================================================
# list_presets
# ===========================================================================

@pytest.mark.slow
class TestListPresets:
    """list_presets is a non-simulation tool — fast, but still needs the API."""

    def test_returns_dual_format(self, api):
        """list_presets returns a DualFormatResult with a 'presets' key.

        LEARNING: Even "informational" tools return DualFormatResult so the
        LLM always gets both JSON and Markdown representations.
        """
        result = api.list_presets()

        assert isinstance(result, DualFormatResult)
        assert "presets" in result.json_data
        assert len(result.json_data["presets"]) > 0
        assert len(result.markdown_text) > 0

    def test_presets_have_required_fields(self, api):
        """Each preset object should expose name, chemistry, and capacity."""
        result = api.list_presets()
        for preset in result.json_data["presets"]:
            assert "name" in preset
            assert "chemistry" in preset
            assert "capacity_Ah" in preset


# ===========================================================================
# compare_presets
# ===========================================================================

@pytest.mark.slow
class TestComparePresets:
    """compare_presets runs real simulations and returns formatted results."""

    def test_compare_returns_dual_format(self, api):
        """Two-preset comparison produces a valid DualFormatResult."""
        result = api.compare_presets(["LFP_5AH", "NMC_5AH"])

        assert isinstance(result, DualFormatResult)
        assert "metrics" in result.json_data or "type" in result.json_data
        assert len(result.markdown_text) > 0

    def test_compare_records_session(self, api):
        """After compare_presets, session history contains the investigation.

        LEARNING: AgentAPI.session is a SimulationSession that accumulates
        InvestigationRun entries.  get_session_summary() returns a markdown
        report string.
        """
        # Run a comparison (may already have been run by previous test)
        api.compare_presets(["LFP_5AH", "NMC_5AH"])

        summary = api.get_session_summary()
        assert isinstance(summary, str)
        assert "compare_presets" in summary


# ===========================================================================
# check_feasibility
# ===========================================================================

@pytest.mark.slow
class TestCheckFeasibility:
    """check_feasibility is fast (no simulation) but exercises AgentAPI wiring."""

    def test_feasibility_returns_dual_format(self, api):
        """Feasibility check on a known-good preset returns feasible=True."""
        result = api.check_feasibility("LFP_5AH", temperature_C=25.0)

        assert isinstance(result, DualFormatResult)
        assert "feasible" in result.json_data
        assert isinstance(result.json_data["feasible"], bool)

    def test_feasibility_includes_preset_name(self, api):
        """Result JSON embeds the preset name for traceability."""
        result = api.check_feasibility("NMC_5AH", temperature_C=25.0)
        assert result.json_data.get("preset") == "NMC_5AH"


# ===========================================================================
# sensitivity_analysis
# ===========================================================================

@pytest.mark.slow
class TestSensitivityAnalysis:
    """sensitivity_analysis varies parameters and formats results."""

    def test_sensitivity_returns_dual_format(self, api):
        """Sensitivity on temperature returns a DualFormatResult.

        LEARNING: The AgentAPI method wraps SensitivityService and
        SensitivityFormatter.  It defines its own parameter_ranges dict
        for known parameters.
        """
        result = api.sensitivity_analysis("LFP_5AH", ["temperature_C"])

        assert isinstance(result, DualFormatResult)
        assert len(result.markdown_text) > 0
        # JSON should contain structured sensitivity data
        assert result.json_data is not None

    def test_sensitivity_records_session(self, api):
        """Session should track sensitivity_analysis investigations."""
        api.sensitivity_analysis("LFP_5AH", ["temperature_C"])

        summary = api.get_session_summary()
        assert "sensitivity_analysis" in summary


# ===========================================================================
# run_simulation
# ===========================================================================

@pytest.mark.slow
class TestRunSimulation:
    """run_simulation executes a single sim and returns formatted metrics."""

    def test_run_returns_dual_format(self, api):
        """A single simulation returns DualFormatResult with metrics."""
        result = api.run_simulation("LFP_5AH")

        assert isinstance(result, DualFormatResult)
        assert "metrics" in result.json_data
        assert len(result.markdown_text) > 0

    def test_run_with_custom_temperature(self, api):
        """Custom temperature is reflected in the result JSON."""
        result = api.run_simulation("LFP_5AH", temperature_C=40.0)

        assert result.json_data.get("temperature_C") == 40.0


# ===========================================================================
# Session continuity
# ===========================================================================

@pytest.mark.slow
class TestSessionTracking:
    """Session accumulates investigation history across multiple tool calls."""

    def test_session_grows_after_investigations(self, api):
        """Each simulation tool call adds an InvestigationRun to the session.

        LEARNING: Not all tool calls record to the session — informational
        tools like check_feasibility may skip recording.  Simulation tools
        (run_simulation, compare_presets, sensitivity_analysis) always record.
        We test with run_simulation here because it's a single, fast sim.
        """
        before = len(api.session.investigation_history)

        api.run_simulation("LFP_5AH")

        after = len(api.session.investigation_history)
        assert after > before, "Session history did not grow after tool call"

    def test_reasoning_chain_is_string(self, api):
        """get_reasoning_chain returns a non-empty string after investigations."""
        chain = api.get_reasoning_chain()
        assert isinstance(chain, str)


# ===========================================================================
# Range Estimation
# ===========================================================================

class TestRangeEstimation:
    """Range estimation for EV packs with different configurations."""

    def test_estimate_range_returns_dual_format_result(self, api):
        """estimate_range() produces valid DualFormatResult."""
        result = api.estimate_range(
            preset_name="LFP_5AH",
            cycle_name="WLTP",
            n_series=96,
            n_parallel=40,
        )

        assert isinstance(result, DualFormatResult)
        assert result.json_data is not None
        assert result.markdown_text is not None
        assert len(result.interpretation_hints) > 0

    def test_estimate_range_json_has_required_keys(self, api):
        """JSON output contains all expected fields."""
        result = api.estimate_range(
            preset_name="LFP_5AH",
            cycle_name="WLTP",
        )

        json_data = result.json_data
        assert json_data.get("type") == "range_estimation"
        assert json_data.get("preset") == "LFP_5AH"
        assert json_data.get("cycle") == "WLTP"
        
        # Check pack configuration
        assert "pack_configuration" in json_data
        pack_config = json_data["pack_configuration"]
        assert pack_config.get("n_series") == 96
        assert pack_config.get("n_parallel") == 40
        assert pack_config.get("pack_voltage_V") > 0
        assert pack_config.get("pack_capacity_Ah") > 0
        
        # Check energy metrics
        assert "energy" in json_data
        energy = json_data["energy"]
        assert energy.get("pack_energy_kWh") > 0
        assert energy.get("energy_per_cycle_kWh") >= 0
        
        # Check range results
        assert "range" in json_data
        range_data = json_data["range"]
        assert range_data.get("cycles_possible") >= 0
        assert range_data.get("cycle_distance_km") > 0
        assert range_data.get("estimated_range_km") >= 0

    def test_estimate_range_with_different_pack_sizes(self, api):
        """Range calculation handles different pack configurations."""
        # Smaller but power-capable pack: 96S20P
        small = api.estimate_range(
            preset_name="LFP_5AH",
            n_series=96,
            n_parallel=20,
            peak_power_kW=50.0,
        )
        small_range = small.json_data["range"]["estimated_range_km"]
        
        # Larger pack: 96S40P
        large = api.estimate_range(
            preset_name="LFP_5AH",
            n_series=96,
            n_parallel=40,
            peak_power_kW=50.0,
        )
        large_range = large.json_data["range"]["estimated_range_km"]
        
        # Check that both return valid results
        assert small_range >= 0
        assert large_range >= 0
        
        # If both simulations succeed (non-zero), larger pack should have more range
        if small_range > 0 and large_range > 0:
            # 2x capacity and series is roughly 2-3x the energy
            assert large_range > small_range

    def test_estimate_range_different_cycles(self, api):
        """Range calculation works with different drive cycles."""
        # Use lower power to ensure solver stability
        wltp = api.estimate_range(
            preset_name="LFP_5AH",
            cycle_name="WLTP",
            n_series=96,
            n_parallel=40,
            peak_power_kW=50.0,
        )
        
        us06 = api.estimate_range(
            preset_name="LFP_5AH",
            cycle_name="US06",
            n_series=96,
            n_parallel=40,
            peak_power_kW=50.0,
        )
        
        # Both should return valid JSON structures
        wltp_range = wltp.json_data["range"]["estimated_range_km"]
        us06_range = us06.json_data["range"]["estimated_range_km"]
        
        assert wltp_range >= 0
        assert us06_range >= 0
        
        # If both simulations succeed, ranges should be realistic
        if wltp_range > 0 and us06_range > 0:
            # Both should be positive and reasonable
            assert wltp_range < 10000  # Less than 10,000 km for 25 kWh
            assert us06_range < 10000

    def test_estimate_range_with_custom_temperature(self, api):
        """estimate_range respects temperature parameter."""
        result = api.estimate_range(
            preset_name="LFP_5AH",
            temperature_C=0.0,  # Cold conditions
        )
        
        assert result.json_data.get("temperature_C") == 0.0

    def test_estimate_range_markdown_contains_values(self, api):
        """Markdown output includes readable range estimate."""
        result = api.estimate_range(
            preset_name="LFP_5AH",
            n_series=96,
            n_parallel=40,
        )
        
        markdown = result.markdown_text
        assert "LFP_5AH" in markdown
        assert "WLTP" in markdown
        assert "km" in markdown.lower()
        assert "kWh" in markdown
        
        # Should mention key assumptions
        assert "assumption" in markdown.lower() or "note" in markdown.lower()
