"""Focused warranty behavior."""

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


class WarrantyMixin:
    def warranty_analysis(
        self,
        preset_name: str,
        warranty_years: float = 8.0,
        warranty_km: float = 160000.0,
        warranty_soh_threshold: float = 0.80,
        usage_profile: Optional[dict[str, Any]] = None,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Screen a warranty target using the experimental lifetime fit."""
        started = time.perf_counter()
        usage = self._usage_profile(usage_profile)
        if warranty_years < 0 or warranty_km < 0:
            raise ValueError("Warranty duration and distance must be non-negative")
        if not 0 < warranty_soh_threshold <= 1:
            raise ValueError("warranty_soh_threshold must be in (0, 1]")

        lifetime = self.predict_lifetime(
            preset_name=preset_name,
            usage_profile=usage_profile,
            n_representative_cycles=10,
            temperature_C=temperature_C,
        )
        if lifetime.json_data.get("type") != "lifetime_prediction":
            return self._warranty_error(
                "Could not obtain a lifetime fit", preset_name, usage
            )
        projection = lifetime.json_data["projection"]
        if projection["status"] != "linear_extrapolation_available":
            return self._warranty_error(
                "Observed cycles do not support a forward warranty projection",
                preset_name,
                usage,
            )

        mileage_years = (
            warranty_km / (usage.daily_km * 365.25)
            if usage.daily_km > 0
            else float("inf")
        )
        evaluation_years = min(warranty_years, mileage_years)
        limiting_condition = "time" if warranty_years <= mileage_years else "distance"
        warranty_cycles = int(evaluation_years * 365.25 * usage.daily_charge_cycles)
        slope = projection["slope_Ah_per_cycle"]
        intercept = projection["intercept_Ah"]
        initial_capacity = lifetime.json_data["initial_capacity_Ah"]
        predicted_soh = float(
            np.clip((slope * warranty_cycles + intercept) / initial_capacity, 0.0, 1.0)
        )
        margin_percent = (
            predicted_soh - warranty_soh_threshold
        ) / warranty_soh_threshold * 100.0
        passes = predicted_soh >= warranty_soh_threshold
        risk_level = self._risk_level(margin_percent)
        status = "Meets screening threshold" if passes else "Does not meet screening threshold"
        json_data = {
            "type": "warranty_analysis",
            "maturity": "experimental",
            "preset": preset_name,
            "temperature_C": temperature_C,
            "passes_warranty": passes,
            "status": status,
            "predicted_soh_at_warranty_end_pct": predicted_soh * 100.0,
            "warranty_soh_threshold_pct": warranty_soh_threshold * 100.0,
            "safety_margin_percent": margin_percent,
            "risk_level": risk_level,
            "warranty_years": warranty_years,
            "warranty_km": warranty_km,
            "warranty_cycles": warranty_cycles,
            "warranty_km_actual": evaluation_years * 365.25 * usage.daily_km,
            "evaluation_years": evaluation_years,
            "limiting_condition": limiting_condition,
            "estimated_years_to_eol": lifetime.json_data["estimated_years_to_eol"],
            "estimated_cycles_to_eol": lifetime.json_data["estimated_cycles_to_eol"],
            "usage_profile": self._usage_data(usage),
            "projection": projection,
            "evidence": {
                "status": "screening only",
                "validation_status": "not suitable for warranty commitment without test correlation",
            },
        }
        badge = "PASS" if passes else "FAIL"
        markdown = "\n".join(
            [
                f"# Experimental Warranty Screening: {preset_name}",
                "",
                "> **Decision limit:** this screening is based on an unvalidated linear "
                "extrapolation and must not be used for a warranty commitment.",
                "",
                f"## {badge} — {status}",
                "",
                "| Quantity | Value |",
                "|---|---:|",
                f"| Limiting warranty condition | {limiting_condition} |",
                f"| Evaluation point | {evaluation_years:.2f} years / {warranty_cycles:,} cycles |",
                f"| Projected SOH | {predicted_soh * 100:.1f}% |",
                f"| Screening threshold | {warranty_soh_threshold * 100:.1f}% |",
                f"| Relative margin | {margin_percent:+.1f}% |",
                f"| Heuristic risk band | {risk_level} |",
            ]
        )
        hints = [
            "Use this result only to screen scenarios, never to approve a warranty",
            "Correlate the model against cycle and calendar-aging tests over the intended duty cycle",
            "Warranty ends at the first of the time or distance limits",
        ]
        self._session.record_investigation(
            investigation_type="warranty_analysis",
            parameters={
                "preset": preset_name,
                "warranty_years": warranty_years,
                "warranty_km": warranty_km,
                "warranty_soh_threshold": warranty_soh_threshold,
                "temperature_C": temperature_C,
                "usage_profile": usage_profile,
            },
            result_summary=json_data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - started,
            key_findings=hints,
        )
        return DualFormatResult(json_data, markdown, hints)
