"""Experimental cell-to-pack-to-vehicle screening tools."""

import time
from typing import Any, Optional

from battery_sim.core.cell import CellPresets
from battery_sim.core.drive_cycles import get_drive_cycle, scale_drive_cycle
from battery_sim.core.pack import PackConfiguration, PackSizer
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.simulation_session import SimulationSession


DRIVE_CYCLE_DISTANCES_KM = {
    "WLTP": 23.3,
    "WLTP_CLASS3": 23.3,
    "US06": 12.9,
    "UDDS": 12.0,
}


class VehicleToolHandler:
    """Screen topology and vehicle implications with visible assumptions."""

    _REFERENCE_CONSUMPTION_KWH_PER_KM = 0.18
    _USABLE_ENERGY_FRACTION = 0.90
    _FULL_EQUIVALENT_CYCLES_PER_YEAR = 100.0

    def __init__(
        self,
        *,
        session: SimulationSession,
    ) -> None:
        self._session = session

    def pack_sizing(
        self,
        preset_name: str,
        target_energy_kWh: float = 60.0,
        voltage_range: tuple[float, float] = (300.0, 400.0),
    ) -> DualFormatResult:
        started = time.perf_counter()
        preset = CellPresets.get(preset_name)
        config = PackSizer.size_pack(preset, target_energy_kWh, voltage_range)
        packaging = self._packaging_availability(preset)
        physical_metrics = self._physical_metrics(config, packaging)
        json_data = {
            "type": "pack_sizing",
            "maturity": "experimental",
            "preset": preset_name,
            "target_energy_kWh": target_energy_kWh,
            "voltage_range": voltage_range,
            "configuration": self._configuration_data(config),
            "physical_metrics": physical_metrics,
            "assumptions": {
                "series_selection": "nominal voltage near midpoint of requested range",
                "cell_balancing": "ideal and identical cells",
                "weight_overhead_fraction": PackSizer.SYSTEM_OVERHEAD_WEIGHT_FRACTION,
                "volume_overhead_fraction": PackSizer.SYSTEM_OVERHEAD_VOLUME_FRACTION,
                "electrical_losses": "not modeled",
            },
            "data_quality": packaging,
            "benchmarks": {
                "status": "not_provided",
                "reason": "current sourced market benchmarks are outside this calculation",
            },
            "evidence": {
                "topology": "arithmetic derived from nominal cell voltage and capacity",
                "physical_metrics": "preset packaging assumptions when available",
                "validation_status": "not a mechanical, thermal, safety, or costed pack design",
            },
        }
        metric = lambda value, unit: f"{value:.1f} {unit}" if value is not None else "N/A"
        markdown = "\n".join(
            [
                f"# Pack Sizing: {preset_name} → {target_energy_kWh:g} kWh",
                "",
                "> **Screening only:** topology uses nominal values and ideal cells; "
                "it is not a qualified pack design.",
                "",
                "## Configuration",
                "",
                "| Quantity | Value |",
                "|---|---:|",
                f"| Topology | {config.n_series}S × {config.n_parallel}P |",
                f"| Total cells | {config.total_cells:,} |",
                f"| Nominal voltage | {config.pack_voltage_nominal_V:.1f} V |",
                f"| Nominal capacity | {config.pack_capacity_Ah:.1f} Ah |",
                f"| Nominal energy | {config.pack_energy_kWh:.2f} kWh |",
                "",
                "## Physical Metrics",
                "",
                "| Quantity | Value |",
                "|---|---:|",
                f"| Cell mass total | {metric(physical_metrics['pack_weight_kg'], 'kg')} |",
                f"| Assumed system mass | {metric(physical_metrics['system_weight_kg'], 'kg')} |",
                f"| Cell volume total | {metric(physical_metrics['pack_volume_L'], 'L')} |",
                f"| Assumed system volume | {metric(physical_metrics['system_volume_L'], 'L')} |",
                f"| Cell purchase cost | {metric(physical_metrics['pack_cost_usd'], 'USD')} |",
                "",
                "## Industry Benchmark Comparison",
                "",
                "No current benchmark is embedded. Add a dated, sourced benchmark before comparison.",
            ]
        )
        hints = [
            "Verify voltage limits across SOC, not only nominal voltage",
            "Replace illustrative packaging overhead with a mechanical and thermal concept",
            "Do not use missing mass, volume, or cost as zero",
        ]
        self._record("pack_sizing", json_data, markdown, hints, started)
        return DualFormatResult(json_data, markdown, hints)

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

    def estimate_range(
        self,
        preset_name: str,
        cycle_name: str = "WLTP",
        n_series: int = 96,
        n_parallel: int = 40,
        vehicle_mass_kg: float = 1800.0,
        peak_power_kW: float = 150.0,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        started = time.perf_counter()
        if n_series < 1 or n_parallel < 1:
            raise ValueError("n_series and n_parallel must be positive integers")
        if vehicle_mass_kg <= 0 or peak_power_kW <= 0:
            raise ValueError("vehicle_mass_kg and peak_power_kW must be positive")
        normalized_cycle = cycle_name.upper()
        if normalized_cycle not in DRIVE_CYCLE_DISTANCES_KM:
            raise ValueError(
                f"Unsupported cycle {cycle_name!r}; choose {sorted(DRIVE_CYCLE_DISTANCES_KM)}"
            )
        preset = CellPresets.get(preset_name)
        cell = preset.cell
        if cell.nominal_voltage_V is None or cell.nominal_capacity_Ah is None:
            raise ValueError("Range screening requires nominal cell voltage and capacity")

        total_cells = n_series * n_parallel
        pack_voltage_V = n_series * cell.nominal_voltage_V
        pack_capacity_Ah = n_parallel * cell.nominal_capacity_Ah
        pack_energy_kWh = pack_voltage_V * pack_capacity_Ah / 1000.0
        estimated_power_capability_kW = (
            pack_energy_kWh * preset.max_discharge_c_rate
        )
        if peak_power_kW > estimated_power_capability_kW:
            return self._range_error(
                preset_name,
                normalized_cycle,
                ValueError(
                    f"requested peak profile {peak_power_kW:g} kW exceeds the "
                    f"preset C-rate screening limit {estimated_power_capability_kW:.1f} kW "
                    f"for this {n_series}S{n_parallel}P topology"
                ),
            )
        profile = get_drive_cycle(normalized_cycle)
        pack_segments = scale_drive_cycle(
            profile,
            vehicle_mass_kg=vehicle_mass_kg,
            peak_power_kW=peak_power_kW,
        )
        cycle_energy_kWh = sum(
            max(power_W, 0.0) * duration_s
            for power_W, duration_s in pack_segments
        ) / 3_600_000.0
        if cycle_energy_kWh <= 0:
            return self._range_error(
                preset_name,
                normalized_cycle,
                ValueError("Integrated synthetic profile energy must be positive"),
            )

        usable_pack_energy_kWh = pack_energy_kWh * self._USABLE_ENERGY_FRACTION
        cycles_possible = usable_pack_energy_kWh / cycle_energy_kWh
        cycle_distance_km = DRIVE_CYCLE_DISTANCES_KM[normalized_cycle]
        estimated_range_km = cycles_possible * cycle_distance_km
        json_data = {
            "type": "range_estimation",
            "maturity": "experimental",
            "preset": preset_name,
            "cycle": normalized_cycle,
            "pack_configuration": {
                "n_series": n_series,
                "n_parallel": n_parallel,
                "total_cells": total_cells,
                "pack_voltage_V": pack_voltage_V,
                "pack_capacity_Ah": pack_capacity_Ah,
            },
            "energy": {
                "pack_energy_kWh": pack_energy_kWh,
                "usable_pack_energy_kWh": usable_pack_energy_kWh,
                "energy_per_cycle_kWh": cycle_energy_kWh,
            },
            "range": {
                "cycles_possible": cycles_possible,
                "cycle_distance_km": cycle_distance_km,
                "estimated_range_km": estimated_range_km,
            },
            "temperature_C": temperature_C,
            "vehicle_mass_kg": vehicle_mass_kg,
            "power_scaling": {
                "vehicle_peak_profile_kW": peak_power_kW,
                "per_cell_peak_profile_W": peak_power_kW * 1000.0 / total_cells,
                "distribution": "ideal equal power used only for C-rate screening",
                "preset_c_rate_screening_limit_kW": estimated_power_capability_kW,
            },
            "assumptions": {
                "usable_energy_fraction": self._USABLE_ENERGY_FRACTION,
                "profile": "synthetic normalized power trace named after the requested cycle",
                "temperature_effect": "not modeled; temperature is recorded for scenario context only",
                "pack_losses": "not modeled",
                "auxiliary_loads": "not modeled",
                "cell_imbalance": "not modeled",
            },
            "evidence": {
                "cycle_energy": "direct integral of the synthetic pack-level power trace",
                "electrochemical_simulation": "not used by this vehicle screening tool",
                "validation_status": "not a regulatory or correlated vehicle range prediction",
            },
        }
        markdown = "\n".join(
            [
                "# EV Range Estimation — Experimental Screening",
                "",
                f"**Cell preset:** {preset_name}",
                f"**Synthetic profile:** {normalized_cycle}",
                f"**Pack:** {n_series}S × {n_parallel}P ({pack_energy_kWh:.2f} kWh nominal)",
                "",
                f"## Estimated range: {estimated_range_km:.0f} km",
                "",
                f"Cycle energy: {cycle_energy_kWh:.3f} kWh over {cycle_distance_km:.1f} km.",
                "",
                "## Assumptions and evidence limits",
                "",
                "- Vehicle power is checked against an ideal equal distribution across all cells.",
                f"- Usable energy is fixed at {self._USABLE_ENERGY_FRACTION:.0%}.",
                "- The included profiles are normalized synthetic power traces, not regulatory speed traces.",
                "- Temperature, pack losses, auxiliaries, imbalance and HVAC are not modeled.",
            ]
        )
        hints = [
            "Use a measured or longitudinal-model vehicle power trace before making a range decision",
            "Add pack losses, auxiliary loads, thermal conditioning and SOC reserve",
            "Correlate the resulting Wh/km against chassis-dynamometer or fleet data",
        ]
        self._record("estimate_range", json_data, markdown, hints, started)
        return DualFormatResult(json_data, markdown, hints)

    @staticmethod
    def _configuration_data(config: PackConfiguration) -> dict[str, Any]:
        return {
            "n_series": config.n_series,
            "n_parallel": config.n_parallel,
            "total_cells": config.total_cells,
            "pack_voltage_nominal_V": config.pack_voltage_nominal_V,
            "pack_capacity_Ah": config.pack_capacity_Ah,
            "pack_energy_kWh": config.pack_energy_kWh,
        }

    @staticmethod
    def _packaging_availability(preset) -> dict[str, str]:
        return {
            "mass": "available" if preset.weight_kg > 0 else "missing",
            "volume": "available" if preset.volume_L > 0 else "missing",
            "cost": "available" if preset.cost_usd > 0 else "missing",
            "provenance": preset.cell.metadata.get("source", "not documented"),
        }

    @staticmethod
    def _physical_metrics(
        config: PackConfiguration, packaging: dict[str, str]
    ) -> dict[str, Optional[float]]:
        mass_available = packaging["mass"] == "available"
        volume_available = packaging["volume"] == "available"
        cost_available = packaging["cost"] == "available"
        return {
            "pack_weight_kg": config.pack_weight_kg if mass_available else None,
            "pack_volume_L": config.pack_volume_L if volume_available else None,
            "pack_cost_usd": config.pack_cost_usd if cost_available else None,
            "system_weight_kg": config.system_weight_kg if mass_available else None,
            "system_volume_L": config.system_volume_L if volume_available else None,
            "system_energy_density_Wh_per_kg": (
                round(config.system_energy_density_Wh_per_kg, 1)
                if mass_available
                else None
            ),
            "cost_per_kwh": round(config.cost_per_kWh, 2) if cost_available else None,
        }

    @staticmethod
    def _budget_score(value: Optional[float], budget: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if budget is None:
            return None
        return min(100.0, budget / value * 100.0) if value > 0 else None

    def _range_error(
        self, preset_name: str, cycle_name: str, exc: Exception
    ) -> DualFormatResult:
        data = {
            "type": "range_estimation_error",
            "maturity": "experimental",
            "preset": preset_name,
            "cycle": cycle_name,
            "error": f"{type(exc).__name__}: {exc}",
            "evidence": {"validation_status": "no range conclusion available"},
        }
        markdown = f"# EV Range Screening\n\nUnable to estimate range: {data['error']}"
        hints = ["No vehicle range conclusion can be drawn from this run"]
        self._session.record_investigation(
            investigation_type="estimate_range",
            parameters={"preset": preset_name, "cycle": cycle_name},
            result_summary=data,
            result_markdown=markdown,
            duration_seconds=0.0,
            key_findings=hints,
        )
        return DualFormatResult(data, markdown, hints)

    def _record(
        self,
        investigation_type: str,
        json_data: dict[str, Any],
        markdown: str,
        hints: list[str],
        started: float,
    ) -> None:
        self._session.record_investigation(
            investigation_type=investigation_type,
            parameters=json_data.get("requirements", {"preset": json_data.get("preset")}),
            result_summary=json_data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - started,
            key_findings=hints,
        )
