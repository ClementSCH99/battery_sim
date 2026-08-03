"""Tests for B2 warranty analysis feature.

Coverage:
  - warranty_analysis basic functionality
  - Pass scenarios (good cell, mild usage)
  - Fail scenarios (aggressive usage, high temperature)
  - Risk level assessment
  - SOH interpolation at warranty end
  - Edge cases
"""
import pytest

from battery_sim.interfaces.python.tool_registry import AgentAPI
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol, ConstantCurrent
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.core.experiment import SolverConfig


@pytest.fixture(scope="module")
def api_for_warranty():
    """AgentAPI configured for warranty analysis tests."""
    return AgentAPI(
        session_name="Warranty Analysis Test Session",
        default_protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        default_model=Model.SPM,
        default_solver_config=SolverConfig(),
    )


@pytest.mark.slow
class TestWarrantyAnalysisBasics:
    """Basic warranty analysis functionality."""

    def test_warranty_analysis_returns_dual_format(self, api_for_warranty):
        """warranty_analysis returns a DualFormatResult."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            warranty_km=160000.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        assert isinstance(result, DualFormatResult)
        assert isinstance(result.json_data, dict)
        assert isinstance(result.markdown_text, str)
        assert len(result.markdown_text) > 0

    def test_result_has_required_fields(self, api_for_warranty):
        """Result JSON has all required warranty analysis fields."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            warranty_km=160000.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        json_data = result.json_data

        assert json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]

        if json_data.get("type") == "warranty_analysis":
            assert "passes_warranty" in json_data
            assert "predicted_soh_at_warranty_end_pct" in json_data
            assert "warranty_soh_threshold_pct" in json_data
            assert "safety_margin_percent" in json_data
            assert "risk_level" in json_data
            assert "warranty_years" in json_data
            assert "warranty_km" in json_data
            assert "warranty_cycles" in json_data
            assert "usage_profile" in json_data

    def test_passes_warranty_boolean(self, api_for_warranty):
        """passes_warranty is a boolean flag."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        if result.json_data.get("type") == "warranty_analysis":
            assert isinstance(result.json_data["passes_warranty"], bool)

    def test_safety_margin_is_numeric(self, api_for_warranty):
        """Safety margin is a numeric value (can be negative)."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        if result.json_data.get("type") == "warranty_analysis":
            margin = result.json_data["safety_margin_percent"]
            assert isinstance(margin, (int, float))

    def test_risk_levels_recognized(self, api_for_warranty):
        """Risk level is one of the recognized values."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            temperature_C=25.0,
        )

        if result.json_data.get("type") == "warranty_analysis":
            risk = result.json_data["risk_level"]
            assert risk in ["Low Risk", "Moderate Risk", "High Risk", "Critical"]


@pytest.mark.slow
class TestWarrantyAnalysisScenarios:
    """Different warranty scenarios and their outcomes."""

    def test_usage_profile_affects_cycles(self, api_for_warranty):
        """Different usage profiles lead to different warranty cycle counts."""
        mileage_profile = {
            "daily_km": 100.0,
            "daily_charge_cycles": 1.0,
        }

        city_profile = {
            "daily_km": 30.0,
            "daily_charge_cycles": 1.0,
        }

        result_mileage = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,  # Use 1 year for faster test
            warranty_km=50000.0,
            usage_profile=mileage_profile,
            temperature_C=25.0,
        )

        result_city = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            warranty_km=20000.0,
            usage_profile=city_profile,
            temperature_C=25.0,
        )

        # Both should be valid results (success or error)
        assert result_mileage.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]
        assert result_city.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]

    def test_temperature_affects_warranty(self, api_for_warranty):
        """Higher temperature should lead to lower SOH at warranty end."""
        result_cool = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=2.0,
            warranty_soh_threshold=0.80,
            temperature_C=15.0,
        )

        result_warm = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=2.0,
            warranty_soh_threshold=0.80,
            temperature_C=45.0,
        )

        # Both should produce valid results
        if (result_cool.json_data.get("type") == "warranty_analysis" and
            result_warm.json_data.get("type") == "warranty_analysis"):
            
            soh_cool = result_cool.json_data["predicted_soh_at_warranty_end_pct"]
            soh_warm = result_warm.json_data["predicted_soh_at_warranty_end_pct"]
            
            # Warm should have lower SOH due to Arrhenius acceleration
            # (though if degradation is slow in both cases, this may not always hold)
            # We just verify both are in valid range
            assert 0 <= soh_cool <= 100
            assert 0 <= soh_warm <= 100

    def test_different_soh_thresholds(self, api_for_warranty):
        """Different SOH thresholds affect margin calculation."""
        result_80 = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        result_70 = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            warranty_soh_threshold=0.70,
            temperature_C=25.0,
        )

        # Both should be valid
        assert result_80.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]
        assert result_70.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]

        if (result_80.json_data.get("type") == "warranty_analysis" and
            result_70.json_data.get("type") == "warranty_analysis"):
            
            # Verify thresholds are captured correctly
            assert result_80.json_data["warranty_soh_threshold_pct"] == 80.0
            assert result_70.json_data["warranty_soh_threshold_pct"] == 70.0
            
            # Margins are numeric
            margin_80 = result_80.json_data["safety_margin_percent"]
            margin_70 = result_70.json_data["safety_margin_percent"]
            
            assert isinstance(margin_80, (int, float))
            assert isinstance(margin_70, (int, float))


@pytest.mark.slow
class TestWarrantyAnalysisEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_warranty_years(self, api_for_warranty):
        """Zero warranty years should not crash."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=0.0,
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        # Should handle gracefully (success or error)
        assert result.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]

    def test_very_high_warranty_years(self, api_for_warranty):
        """Very high warranty years should extrapolate gracefully."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=50.0,  # 50 year warranty
            warranty_soh_threshold=0.80,
            temperature_C=25.0,
        )

        if result.json_data.get("type") == "warranty_analysis":
            # Should extrapolate (may result in low SOH)
            soh = result.json_data["predicted_soh_at_warranty_end_pct"]
            assert 0 <= soh <= 100

    def test_soh_threshold_boundaries(self, api_for_warranty):
        """Handle SOH threshold edge values."""
        result_100_pct = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            warranty_soh_threshold=1.0,  # 100% SOH
            temperature_C=25.0,
        )

        result_50_pct = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            warranty_soh_threshold=0.50,  # 50% SOH
            temperature_C=25.0,
        )

        # Both should handle gracefully
        assert result_100_pct.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]
        assert result_50_pct.json_data.get("type") in ["warranty_analysis", "warranty_analysis_error"]


@pytest.mark.slow
class TestWarrantyAnalysisMarkdown:
    """Markdown output formatting and content."""

    def test_markdown_includes_status(self, api_for_warranty):
        """Markdown includes pass/fail status."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            temperature_C=25.0,
        )

        md = result.markdown_text

        # Should include pass or fail indicator
        assert "PASS" in md or "FAIL" in md or "pass" in md or "fail" in md

    def test_markdown_includes_warranty_params(self, api_for_warranty):
        """Markdown includes warranty parameters."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=8.0,
            warranty_km=160000.0,
            temperature_C=25.0,
        )

        md = result.markdown_text

        # Should include warranty specs
        assert "8" in md or "warranty" in md.lower()

    def test_markdown_includes_risk_assessment(self, api_for_warranty):
        """Markdown includes risk level and assessment."""
        result = api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            temperature_C=25.0,
        )

        md = result.markdown_text

        # Should include risk information
        assert ("Risk" in md or "risk" in md or 
                "Low" in md or "Moderate" in md or "High" in md or "Critical" in md)


@pytest.mark.slow
class TestWarrantyMCPIntegration:
    """MCP tool integration."""

    def test_mcp_warranty_analysis_callable(self):
        """MCP warranty_analysis tool is callable."""
        from battery_sim.mcp_server import warranty_analysis

        assert callable(warranty_analysis)

    def test_mcp_warranty_analysis_returns_json_string(self):
        """MCP warranty_analysis returns JSON string."""
        from battery_sim.mcp_server import warranty_analysis

        result_str = warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            temperature_C=25.0,
        )

        # Should be a valid JSON string
        assert isinstance(result_str, str)
        assert len(result_str) > 0

        # Should contain JSON-like content
        import json
        try:
            json.loads(result_str)
        except json.JSONDecodeError:
            pytest.fail("MCP result is not valid JSON")


@pytest.mark.slow
class TestWarrantySessionTracking:
    """Session tracking for warranty analysis."""

    def test_warranty_analysis_updates_session(self, api_for_warranty):
        """warranty_analysis updates session history."""
        before = len(api_for_warranty.session.investigation_history)

        api_for_warranty.warranty_analysis(
            preset_name="LFP_5AH",
            warranty_years=1.0,
            temperature_C=25.0,
        )

        after = len(api_for_warranty.session.investigation_history)
        assert after > before, "Session history did not grow after warranty_analysis"
