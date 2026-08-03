"""Nominal battery-pack topology and packaging arithmetic."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PackConfiguration:
    """Ideal series/parallel topology plus assumption-derived packaging totals."""

    n_series: int
    n_parallel: int
    total_cells: int
    pack_voltage_nominal_V: float
    pack_capacity_Ah: float
    pack_energy_kWh: float
    pack_weight_kg: float
    pack_volume_L: float
    pack_cost_usd: float
    overhead_weight_kg: float
    overhead_volume_L: float
    system_weight_kg: float
    system_volume_L: float
    pack_energy_density_Wh_per_kg: float
    system_energy_density_Wh_per_kg: float
    cost_per_kWh: float


class PackSizer:
    """Compute an ideal nominal topology; this is not a pack design solver."""

    SYSTEM_OVERHEAD_WEIGHT_FRACTION = 0.20
    SYSTEM_OVERHEAD_VOLUME_FRACTION = 0.30

    @classmethod
    def size_pack(
        cls,
        cell_preset,
        target_energy_kWh: float,
        voltage_range: tuple[float, float] = (300.0, 400.0),
    ) -> PackConfiguration:
        if not math.isfinite(target_energy_kWh) or target_energy_kWh <= 0:
            raise ValueError("target_energy_kWh must be positive and finite")
        if len(voltage_range) != 2:
            raise ValueError("voltage_range must contain exactly (min_V, max_V)")
        minimum_voltage_V, maximum_voltage_V = voltage_range
        if (
            not math.isfinite(minimum_voltage_V)
            or not math.isfinite(maximum_voltage_V)
            or minimum_voltage_V <= 0
            or maximum_voltage_V <= 0
            or minimum_voltage_V > maximum_voltage_V
        ):
            raise ValueError("voltage_range must satisfy 0 < min_V <= max_V")

        cell = cell_preset.cell
        if cell.nominal_voltage_V is None or cell.nominal_voltage_V <= 0:
            raise ValueError("Pack sizing requires a positive nominal cell voltage")
        if cell.nominal_capacity_Ah is None or cell.nominal_capacity_Ah <= 0:
            raise ValueError("Pack sizing requires a positive nominal cell capacity")

        midpoint_voltage_V = (minimum_voltage_V + maximum_voltage_V) / 2.0
        minimum_series = math.ceil(minimum_voltage_V / cell.nominal_voltage_V)
        maximum_series = math.floor(maximum_voltage_V / cell.nominal_voltage_V)
        if maximum_series < 1 or minimum_series > maximum_series:
            raise ValueError(
                f"No integer series count places nominal cell voltage "
                f"{cell.nominal_voltage_V:g} V inside {voltage_range}"
            )
        n_series = min(
            max(round(midpoint_voltage_V / cell.nominal_voltage_V), minimum_series),
            maximum_series,
        )

        cell_energy_Wh = cell.nominal_capacity_Ah * cell.nominal_voltage_V
        series_string_energy_Wh = n_series * cell_energy_Wh
        n_parallel = math.ceil(target_energy_kWh * 1000.0 / series_string_energy_Wh)
        total_cells = n_series * n_parallel
        pack_voltage_nominal_V = n_series * cell.nominal_voltage_V
        pack_capacity_Ah = n_parallel * cell.nominal_capacity_Ah
        pack_energy_kWh = pack_voltage_nominal_V * pack_capacity_Ah / 1000.0

        pack_weight_kg = total_cells * cell_preset.weight_kg
        pack_volume_L = total_cells * cell_preset.volume_L
        pack_cost_usd = total_cells * cell_preset.cost_usd
        overhead_weight_kg = pack_weight_kg * cls.SYSTEM_OVERHEAD_WEIGHT_FRACTION
        overhead_volume_L = pack_volume_L * cls.SYSTEM_OVERHEAD_VOLUME_FRACTION
        system_weight_kg = pack_weight_kg + overhead_weight_kg
        system_volume_L = pack_volume_L + overhead_volume_L
        pack_energy_Wh = pack_energy_kWh * 1000.0

        return PackConfiguration(
            n_series=n_series,
            n_parallel=n_parallel,
            total_cells=total_cells,
            pack_voltage_nominal_V=pack_voltage_nominal_V,
            pack_capacity_Ah=pack_capacity_Ah,
            pack_energy_kWh=pack_energy_kWh,
            pack_weight_kg=pack_weight_kg,
            pack_volume_L=pack_volume_L,
            pack_cost_usd=pack_cost_usd,
            overhead_weight_kg=overhead_weight_kg,
            overhead_volume_L=overhead_volume_L,
            system_weight_kg=system_weight_kg,
            system_volume_L=system_volume_L,
            pack_energy_density_Wh_per_kg=(
                pack_energy_Wh / pack_weight_kg if pack_weight_kg > 0 else 0.0
            ),
            system_energy_density_Wh_per_kg=(
                pack_energy_Wh / system_weight_kg if system_weight_kg > 0 else 0.0
            ),
            cost_per_kWh=(
                pack_cost_usd / pack_energy_kWh if pack_energy_kWh > 0 else 0.0
            ),
        )
