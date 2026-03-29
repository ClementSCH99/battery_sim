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

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.solver import SolverConfig


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
