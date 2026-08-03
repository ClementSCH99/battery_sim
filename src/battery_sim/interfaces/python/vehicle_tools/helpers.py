"""Focused helpers behavior."""

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

class HelpersMixin:
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
