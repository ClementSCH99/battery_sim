"""Experimental lifetime and warranty tools with explicit evidence limits."""

import time
from typing import Any, Optional

import numpy as np

from battery_sim.core.cell import Cell
from battery_sim.core.degradation import DegradationConfig, UsageProfile
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.services import SimulationExecutionService
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.solver import SolverConfig
from battery_sim.types.signal import Signal


class DegradationToolHandler:
    """Run short aging studies and label their extrapolations as exploratory."""

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_model: Model,
    ) -> None:
        self._execution = SimulationExecutionService(backend)
        self._session = session
        self._default_model = default_model

    def predict_lifetime(
        self,
        preset_name: str,
        usage_profile: Optional[dict[str, Any]] = None,
        n_representative_cycles: int = 50,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Fit a linear trend to simulated cycles; never claim validated lifetime."""
        started = time.perf_counter()
        usage = self._usage_profile(usage_profile)
        if n_representative_cycles < 3:
            return self._lifetime_error(
                "At least three representative cycles are required for exploratory fitting",
                preset_name,
                usage,
            )

        cell = Cell.preset(preset_name)
        if cell.nominal_capacity_Ah is None or cell.nominal_voltage_V is None:
            return self._lifetime_error(
                "The selected cell requires nominal capacity and voltage",
                preset_name,
                usage,
            )

        current_A = cell.nominal_capacity_Ah * 0.5
        max_voltage_V = float(
            cell.metadata.get("max_voltage_v", cell.nominal_voltage_V * 1.05)
        )
        discharge_duration_s = 3600.0
        nominal_dod_fraction = current_A * discharge_duration_s / (
            cell.nominal_capacity_Ah * 3600.0
        )
        protocol = Protocol.cycle(
            charge=Protocol.cccv(
                charge_current_A=current_A,
                cutoff_voltage_V=max_voltage_V,
                taper_current_A=current_A * 0.1,
            ),
            discharge=Protocol.cc(
                current_A=current_A,
                duration_s=discharge_duration_s,
            ),
            n_cycles=n_representative_cycles,
            rest_s=600,
        )
        simulation = Simulation(
            cell=cell,
            model=self._default_model,
            protocol=protocol,
            environment=Environment(temperature_C=temperature_C),
            solver_config=SolverConfig(initial_soc=0.2),
            degradation=DegradationConfig(
                sei_growth=True,
                calendar_aging=True,
                storage_temperature_C=usage.storage_temperature_C,
                storage_soc=usage.storage_soc,
            ),
        )
        try:
            run = self._execution.execute(simulation)
        except Exception as exc:
            return self._lifetime_error(
                f"{type(exc).__name__}: {exc}", preset_name, usage
            )
        capacity_signal = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        if capacity_signal is None or len(capacity_signal.values) < 2:
            error_details = [error.summary() for error in run.errors]
            message = "No usable per-cycle discharge-capacity signal was produced"
            if error_details:
                message += f": {'; '.join(error_details)}"
            return self._lifetime_error(message, preset_name, usage)

        cycles = np.asarray(capacity_signal.time_s, dtype=float)
        capacities = np.asarray(capacity_signal.values, dtype=float)
        if not np.all(np.isfinite(cycles)) or not np.all(np.isfinite(capacities)):
            return self._lifetime_error(
                "Cycling data contain non-finite values", preset_name, usage
            )

        slope_Ah_per_cycle, intercept_Ah = np.polyfit(cycles, capacities, 1)
        fitted = slope_Ah_per_cycle * cycles + intercept_Ah
        residual_sum = float(np.sum((capacities - fitted) ** 2))
        total_sum = float(np.sum((capacities - np.mean(capacities)) ** 2))
        r_squared = 1.0 - residual_sum / total_sum if total_sum > 0 else None
        initial_capacity_Ah = float(capacities[0])
        eol_capacity_Ah = initial_capacity_Ah * 0.8

        estimated_cycles: Optional[int] = None
        estimated_years: Optional[float] = None
        extrapolation_ratio: Optional[float] = None
        projection_status = "no_decline_observed"
        if slope_Ah_per_cycle < 0:
            eol_cycle = (eol_capacity_Ah - intercept_Ah) / slope_Ah_per_cycle
            if np.isfinite(eol_cycle) and eol_cycle > cycles[-1]:
                estimated_cycles = max(int(np.ceil(eol_cycle)), 1)
                estimated_years = (
                    estimated_cycles / usage.daily_charge_cycles / 365.25
                )
                extrapolation_ratio = estimated_cycles / len(capacities)
                projection_status = "linear_extrapolation_available"
            else:
                projection_status = "fit_does_not_support_forward_projection"

        trajectory = [
            {
                "cycle": int(cycle),
                "discharge_capacity_Ah": float(capacity),
                "capacity_retention_pct": float(capacity / initial_capacity_Ah * 100),
            }
            for cycle, capacity in zip(cycles, capacities)
        ]
        usage_data = self._usage_data(usage)
        json_data = {
            "type": "lifetime_prediction",
            "maturity": "experimental",
            "preset": preset_name,
            "temperature_C": temperature_C,
            "n_representative_cycles": n_representative_cycles,
            "simulated_duty_cycle": {
                "charge_c_rate": 0.5,
                "discharge_c_rate": 0.5,
                "nominal_depth_of_discharge_fraction": nominal_dod_fraction,
                "rest_after_each_half_cycle_s": 600,
            },
            "usage_profile": usage_data,
            "estimated_years_to_eol": estimated_years,
            "estimated_cycles_to_eol": estimated_cycles,
            "capacity_fade_rate_per_cycle_Ah": float(max(-slope_Ah_per_cycle, 0.0)),
            "initial_capacity_Ah": initial_capacity_Ah,
            "eol_capacity_Ah": eol_capacity_Ah,
            "capacity_trajectory": trajectory,
            "projection": {
                "status": projection_status,
                "method": "ordinary least-squares linear fit",
                "slope_Ah_per_cycle": float(slope_Ah_per_cycle),
                "intercept_Ah": float(intercept_Ah),
                "r_squared": r_squared,
                "observed_cycle_count": len(capacities),
                "extrapolation_ratio": extrapolation_ratio,
                "extrapolation_distance": (
                    "far_beyond_observed_window"
                    if extrapolation_ratio is not None and extrapolation_ratio > 10
                    else "within_ten_times_observed_window"
                    if extrapolation_ratio is not None
                    else "not_available"
                ),
                "eol_threshold_fraction": 0.8,
            },
            "evidence": {
                "observed": "per-cycle discharge capacity from SimulationRun",
                "derived": "linear fit and conversion using daily charge cycles",
                "validation_status": "not validated against cell test data",
            },
        }
        years_text = f"{estimated_years:.1f}" if estimated_years is not None else "N/A"
        cycles_text = f"{estimated_cycles:,}" if estimated_cycles is not None else "N/A"
        markdown = "\n".join(
            [
                f"# Experimental Lifetime Extrapolation: {preset_name}",
                "",
                "> **Evidence limit:** this is a linear extrapolation of a short simulated "
                "aging window, not a validated lifetime prediction.",
                "",
                "| Quantity | Value |",
                "|---|---:|",
                f"| Simulated cycles with capacity data | {len(capacities)} |",
                f"| Estimated cycles to 80% capacity | {cycles_text} |",
                f"| Estimated years at {usage.daily_charge_cycles:g} cycles/day | {years_text} |",
                f"| Linear fade slope | {slope_Ah_per_cycle:.6g} Ah/cycle |",
                f"| Fit R² | {r_squared:.4f} |" if r_squared is not None else "| Fit R² | N/A |",
                f"| Projection status | {projection_status} |",
            ]
        )
        hints = [
            "Treat the result as an exploratory extrapolation, not a warranty-grade prediction",
            "Validate the degradation law and parameters against representative cell test data",
            "Temperature, SOC window, C-rate and rest history must match the intended duty cycle",
        ]
        self._session.record_investigation(
            investigation_type="predict_lifetime",
            parameters={
                "preset": preset_name,
                "n_cycles": n_representative_cycles,
                "temperature_C": temperature_C,
                "usage_profile": usage_profile,
            },
            result_summary=json_data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - started,
            key_findings=hints,
        )
        return DualFormatResult(json_data, markdown, hints)

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
