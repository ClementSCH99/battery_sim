"""Focused sizing behavior."""

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

class SizingMixin:
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
