"""Focused range behavior."""

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

class RangeMixin:
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
            "profile_name": f"synthetic_{normalized_cycle.lower()}",
            "profile_kind": "synthetic_normalized_power_trace",
            "regulatory_cycle": False,
            "temperature_effect_applied": False,
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
