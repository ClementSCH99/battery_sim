"""Focused dimensions behavior."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer

from battery_sim.experimental.pack.cell_selection.models import (
    CellScoringResult,
)

class DimensionsMixin:
    @staticmethod
    def _score_energy_dimension(
        preset,  # CellPreset
        pack_config: PackConfiguration,
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score energy capacity target within constraints.

        TEACHING: Can we fit enough energy without exceeding weight/volume limits?

        Scoring:
        - 100: Pack fits comfortably in weight budget (< 80%)
        - 50: Pack hits weight limit exactly (100%)
        - 0: Pack exceeds weight budget
        """

        weight_budget = requirements.get('weight_budget_kg', 500.0)
        volume_budget = requirements.get('volume_budget_L', 1000.0)

        # Weight penalty
        weight_ratio = pack_config.system_weight_kg / weight_budget
        weight_score = max(0, 100 * (1 - weight_ratio)) if weight_ratio > 0 else 100

        # Volume penalty (if specified)
        volume_ratio = pack_config.system_volume_L / volume_budget
        volume_score = max(0, 100 * (1 - volume_ratio)) if volume_ratio > 0 else 100

        # Energy density bonus
        energy_density = pack_config.system_energy_density_Wh_per_kg
        if energy_density >= 120.0:
            density_bonus = 20
        elif energy_density >= 80.0:
            density_bonus = 10
        else:
            density_bonus = 0

        # Combine: weight is more important than volume
        base_score = 0.7 * weight_score + 0.3 * volume_score
        energy_score = min(100, base_score + density_bonus)

        return energy_score
    @staticmethod
    def _score_power_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score discharge C-rate capability vs peak power demand.

        TEACHING: Can this cell provide the peak power?

        Scoring:
        - 100: Can easily provide 2× peak power demand
        - 50: Can barely provide required power (at 1C)
        - 0: Cannot provide required power
        """

        max_discharge_c_rate = preset.max_discharge_c_rate

        # Assume a reasonable pack would use ~100 parallel cells
        # That allows lower cell rates to achieve pack-level power
        # For simplicity, assume pack can achieve 1.5× cell C-rate through parallelization
        effective_pack_c_rate = max_discharge_c_rate * 1.5

        # Minimum acceptable C-rate
        min_acceptable_c_rate = 1.0

        if effective_pack_c_rate >= 3.0:
            # Can provide high power
            power_score = 100
        elif effective_pack_c_rate >= min_acceptable_c_rate:
            # Can provide adequate power
            power_score = 50 + 50 * (effective_pack_c_rate - min_acceptable_c_rate) / (3.0 - min_acceptable_c_rate)
        else:
            # Cannot provide required power
            power_score = 0

        return power_score
    @staticmethod
    def _score_cost_dimension(
        preset,  # CellPreset
        pack_config: PackConfiguration,
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score total pack cost vs budget.

        TEACHING: Is it affordable?

        Scoring:
        - 100: Cost is < 50% of budget (great value)
        - 50: Cost equals budget exactly
        - 0: Cost exceeds budget
        """

        cost_budget = requirements.get('cost_budget_usd', float('inf'))

        if cost_budget == float('inf'):
            # No cost constraint specified
            cost_score = 50 + 50 * (1 - preset.cost_per_kWh / 300)  # Normalize to $300/kWh max
            return min(100, max(0, cost_score))

        actual_cost = pack_config.cost_per_kWh * pack_config.pack_energy_kWh
        cost_ratio = actual_cost / cost_budget

        if cost_ratio <= 0.5:
            # Great value
            cost_score = 100
        elif cost_ratio <= 1.0:
            # Acceptable cost
            cost_score = 100 * (1 - cost_ratio)
        else:
            # Over budget
            cost_score = 0

        return cost_score
