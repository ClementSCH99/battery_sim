"""Focused helpers behavior."""

import time
from typing import Any, Optional
import numpy as np
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import DegradationConfig, UsageProfile
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.application.services import SimulationExecutionService
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import SolverConfig
from battery_sim.core.result import Signal


class HelpersMixin:
    @staticmethod
    def _usage_profile(values: Optional[dict[str, Any]]) -> UsageProfile:
        usage = UsageProfile(**values) if values else UsageProfile()
        if usage.daily_charge_cycles <= 0:
            raise ValueError("daily_charge_cycles must be positive")
        if usage.daily_km < 0:
            raise ValueError("daily_km must be non-negative")
        if not 0 <= usage.storage_soc <= 1:
            raise ValueError("storage_soc must be between 0 and 1")
        if not 0 <= usage.fast_charge_ratio <= 1:
            raise ValueError("fast_charge_ratio must be between 0 and 1")
        return usage
    @staticmethod
    def _usage_data(usage: UsageProfile) -> dict[str, float]:
        return {
            "daily_km": usage.daily_km,
            "daily_charge_cycles": usage.daily_charge_cycles,
            "storage_temperature_C": usage.storage_temperature_C,
            "storage_soc": usage.storage_soc,
            "fast_charge_ratio": usage.fast_charge_ratio,
        }
    @staticmethod
    def _risk_level(margin_percent: float) -> str:
        if margin_percent > 20:
            return "Low Risk"
        if margin_percent > 10:
            return "Moderate Risk"
        if margin_percent > 0:
            return "High Risk"
        return "Critical"
    def _lifetime_error(
        self, message: str, preset_name: str, usage: UsageProfile
    ) -> DualFormatResult:
        data = {
            "type": "lifetime_prediction_error",
            "maturity": "experimental",
            "preset": preset_name,
            "error": message,
            "usage_profile": self._usage_data(usage),
            "evidence": {"validation_status": "no lifetime projection available"},
        }
        result = DualFormatResult(
            data,
            f"# Experimental Lifetime Extrapolation\n\nUnable to project lifetime: {message}",
            [
                "No degradation or lifetime conclusion can be drawn from this run",
                "Use a parameter set with aging physics and representative usage conditions",
            ],
        )
        self._session.record_investigation(
            investigation_type="predict_lifetime",
            parameters={"preset": preset_name, "usage_profile": self._usage_data(usage)},
            result_summary=data,
            result_markdown=result.markdown_text,
            duration_seconds=0.0,
            key_findings=result.interpretation_hints,
        )
        return result
    def _warranty_error(
        self, message: str, preset_name: str, usage: UsageProfile
    ) -> DualFormatResult:
        data = {
            "type": "warranty_analysis_error",
            "maturity": "experimental",
            "preset": preset_name,
            "error": message,
            "decision_ready": False,
            "passes_warranty": None,
            "risk_level": None,
            "usage_profile": self._usage_data(usage),
            "evidence": {"validation_status": "no warranty conclusion available"},
        }
        result = DualFormatResult(
            data,
            (
                "# Experimental Warranty Screening\n\n"
                f"## FAIL — screening unavailable\n\n{message}\n\n"
                "**Risk assessment:** unavailable because no supported aging projection exists."
            ),
            ["No warranty or risk conclusion can be drawn from this run"],
        )
        self._session.record_investigation(
            investigation_type="warranty_analysis",
            parameters={"preset": preset_name, "usage_profile": self._usage_data(usage)},
            result_summary=data,
            result_markdown=result.markdown_text,
            duration_seconds=0.0,
            key_findings=result.interpretation_hints,
        )
        return result
