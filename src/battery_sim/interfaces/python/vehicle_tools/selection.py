"""Focused selection behavior."""

import time
from typing import Any, Optional
from battery_sim.core.cell import CellPresets
from battery_sim.experimental.system.drive_cycles import get_drive_cycle, scale_drive_cycle
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.application.session import SimulationSession
DRIVE_CYCLE_DISTANCES_KM = {
    "WLTP": 23.3,
    "WLTP_CLASS3": 23.3,
    "US06": 12.9,
    "UDDS": 12.0,
}

class SelectionMixin:
    def cell_selection(
        self,
        range_km: float = 400.0,
        power_kW: float = 150.0,
        weight_budget_kg: float = 500.0,
        lifetime_years: float = 8.0,
        volume_budget_L: Optional[float] = None,
        cost_budget_usd: Optional[float] = None,
        charge_time_min: Optional[float] = None,
    ) -> DualFormatResult:
        started = time.perf_counter()
        for name, value in (
            ("range_km", range_km),
            ("power_kW", power_kW),
            ("weight_budget_kg", weight_budget_kg),
            ("lifetime_years", lifetime_years),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if volume_budget_L is not None and volume_budget_L <= 0:
            raise ValueError("volume_budget_L must be positive")
        if cost_budget_usd is not None and cost_budget_usd <= 0:
            raise ValueError("cost_budget_usd must be positive")
        if charge_time_min is not None and charge_time_min <= 0:
            raise ValueError("charge_time_min must be positive")

        target_energy_kWh = (
            range_km
            * self._REFERENCE_CONSUMPTION_KWH_PER_KM
            / self._USABLE_ENERGY_FRACTION
        )
        required_cycles = lifetime_years * self._FULL_EQUIVALENT_CYCLES_PER_YEAR
        rankings = []
        for preset_name in CellPresets.list_all():
            preset = CellPresets.get(preset_name)
            try:
                config = PackSizer.size_pack(preset, target_energy_kWh)
            except Exception as exc:
                rankings.append(
                    {
                        "preset_name": preset_name,
                        "chemistry": preset.chemistry,
                        "total_score": None,
                        "scores": {},
                        "meets_requirements": False,
                        "recommendation": f"Configuration failed: {type(exc).__name__}: {exc}",
                        "data_quality": {"configuration": "failed"},
                        "pack_config": None,
                    }
                )
                continue

            packaging = self._packaging_availability(preset)
            power_capability_kW = (
                config.pack_energy_kWh * preset.max_discharge_c_rate
            )
            scores: dict[str, Optional[float]] = {
                "energy": self._budget_score(
                    config.system_weight_kg if packaging["mass"] == "available" else None,
                    weight_budget_kg,
                ),
                "power": min(100.0, power_capability_kW / power_kW * 100.0),
                "cost": self._budget_score(
                    config.pack_cost_usd if packaging["cost"] == "available" else None,
                    cost_budget_usd,
                ) if cost_budget_usd is not None else None,
                "lifetime": (
                    min(100.0, preset.cycle_life_cycles / required_cycles * 100.0)
                    if preset.cycle_life_cycles > 0
                    else None
                ),
                "charge": (
                    min(100.0, preset.max_charge_c_rate / (42.0 / charge_time_min) * 100.0)
                    if charge_time_min is not None
                    else None
                ),
            }
            volume_ok = (
                True
                if volume_budget_L is None
                else packaging["volume"] == "available"
                and config.system_volume_L <= volume_budget_L
            )
            cost_ok = (
                True
                if cost_budget_usd is None
                else packaging["cost"] == "available"
                and config.pack_cost_usd <= cost_budget_usd
            )
            evidence_complete = (
                packaging["mass"] == "available"
                and preset.cycle_life_cycles > 0
                and (volume_budget_L is None or packaging["volume"] == "available")
                and (cost_budget_usd is None or packaging["cost"] == "available")
            )
            meets = (
                evidence_complete
                and config.system_weight_kg <= weight_budget_kg
                and volume_ok
                and cost_ok
                and power_capability_kW >= power_kW
                and preset.cycle_life_cycles >= required_cycles
                and (
                    charge_time_min is None
                    or preset.max_charge_c_rate >= 42.0 / charge_time_min
                )
            )
            available_scores = [score for score in scores.values() if score is not None]
            total_score = sum(available_scores) / len(available_scores)
            missing = [name for name, value in scores.items() if value is None]
            recommendation = (
                "Meets this assumption-based screening"
                if meets
                else "Does not meet constraints or lacks required evidence"
            )
            rankings.append(
                {
                    "preset_name": preset_name,
                    "chemistry": preset.chemistry,
                    "total_score": round(total_score, 1),
                    "scores": {
                        name: round(value, 1) if value is not None else None
                        for name, value in scores.items()
                    },
                    "meets_requirements": meets,
                    "recommendation": recommendation,
                    "missing_score_dimensions": missing,
                    "data_quality": packaging,
                    "estimated_power_capability_kW": power_capability_kW,
                    "pack_config": {
                        **self._configuration_data(config),
                        **self._physical_metrics(config, packaging),
                    },
                }
            )
        rankings.sort(
            key=lambda item: (
                item["meets_requirements"],
                item["total_score"] if item["total_score"] is not None else -1,
            ),
            reverse=True,
        )
        for index, ranking in enumerate(rankings, start=1):
            ranking["rank"] = index

        requirements = {
            "range_km": range_km,
            "power_kW": power_kW,
            "weight_budget_kg": weight_budget_kg,
            "lifetime_years": lifetime_years,
            "volume_budget_L": volume_budget_L if volume_budget_L is not None else "unlimited",
            "cost_budget_usd": cost_budget_usd if cost_budget_usd is not None else "unlimited",
            "charge_time_min": charge_time_min if charge_time_min is not None else "no_constraint",
        }
        json_data = {
            "type": "cell_selection",
            "maturity": "experimental",
            "requirements": requirements,
            "derived_target_energy_kWh": target_energy_kWh,
            "rankings": rankings,
            "assumptions": {
                "reference_consumption_kWh_per_km": self._REFERENCE_CONSUMPTION_KWH_PER_KM,
                "usable_energy_fraction": self._USABLE_ENERGY_FRACTION,
                "full_equivalent_cycles_per_year": self._FULL_EQUIVALENT_CYCLES_PER_YEAR,
                "power_capability": "nominal pack energy multiplied by preset max discharge C-rate",
                "weights": "equal average across available score dimensions",
            },
            "evidence": {
                "validation_status": "decision screening only; no cell test correlation",
                "missing_values": "remain N/A and make hard-constraint compliance false",
            },
        }
        markdown_lines = [
            "# Cell Selection Wizard — Experimental Screening",
            "",
            "> Rankings depend on explicit vehicle and packaging assumptions; they are not a cell qualification.",
            "",
            "## Application Requirements",
            "",
            f"Derived nominal pack energy: **{target_energy_kWh:.1f} kWh** from "
            f"{range_km:g} km at {self._REFERENCE_CONSUMPTION_KWH_PER_KM:.2f} kWh/km and "
            f"{self._USABLE_ENERGY_FRACTION:.0%} usable energy.",
            "",
            "## Rankings",
            "",
            "| Rank | Preset | Score | Power capability | Status | Missing evidence |",
            "|---:|---|---:|---:|---|---|",
        ]
        for ranking in rankings:
            status = "Meets" if ranking["meets_requirements"] else "Fails/incomplete"
            score = ranking["total_score"] if ranking["total_score"] is not None else "N/A"
            missing = ", ".join(ranking.get("missing_score_dimensions", [])) or "none"
            markdown_lines.append(
                f"| {ranking['rank']} | {ranking['preset_name']} | {score} | "
                f"{ranking.get('estimated_power_capability_kW', 0):.1f} kW | {status} | {missing} |"
            )
        markdown_lines.extend(
            [
                "",
                "## Recommendations",
                "",
                "Use the ranking to choose candidates for simulation and cell testing; "
                "do not select a production cell from this score alone.",
            ]
        )
        markdown = "\n".join(markdown_lines)
        hints = [
            "Change the reference consumption assumption before using a different vehicle class",
            "Missing packaging or cycle-life evidence prevents a preset from meeting requirements",
            "Validate power, fast-charge and lifetime limits on cell test data",
        ]
        self._record("cell_selection_wizard", json_data, markdown, hints, started)
        return DualFormatResult(json_data, markdown, hints)
