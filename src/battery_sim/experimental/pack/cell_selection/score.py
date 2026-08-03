"""Focused score behavior."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer

from battery_sim.experimental.pack.cell_selection.models import (
    CellScoringResult,
)

from battery_sim.experimental.pack.cell_selection.dimensions import DimensionsMixin
from battery_sim.experimental.pack.cell_selection.priorities import PrioritiesMixin

class ScoreMixin:
    @staticmethod
    def score(
        requirements: Dict[str, Any],
        presets: List,  # List of CellPreset objects
    ) -> List[CellScoringResult]:
        """
        Score all presets against requirements.

        Args:
            requirements: Dict with keys:
                - range_km (float): Target range in km (e.g., 400)
                - power_kW (float): Peak power requirement (e.g., 150 kW)
                - weight_budget_kg (float): Max pack weight (e.g., 500 kg)
                - volume_budget_L (float): Max pack volume (optional)
                - cost_budget_usd (float): Max pack cost (optional)
                - lifetime_years (float): Warranty period (e.g., 8 years)
                - charge_time_min (float): Target 10-80% charge time in minutes (optional)

            presets: List of CellPreset objects to score

        Returns:
            List of CellScoringResult, sorted by total_score (best first)
        """

        # Assume standard 60 kWh pack for energy density calculation
        # Real scenarios would adjust based on actual pack size
        standard_energy_kWh = 60.0

        results = []

        for preset in presets:
            try:
                # Calculate pack configuration (standard 60 kWh)
                pack_config = PackSizer.size_pack(
                    cell_preset=preset,
                    target_energy_kWh=standard_energy_kWh,
                    voltage_range=(300.0, 400.0),
                )

                has_packaging_data = (
                    preset.weight_kg > 0
                    and preset.volume_L > 0
                    and preset.cost_usd > 0
                )

                # Score each dimension
                energy_score = DimensionsMixin._score_energy_dimension(
                    preset, pack_config, requirements
                )

                power_score = DimensionsMixin._score_power_dimension(
                    preset, requirements
                )

                cost_score = DimensionsMixin._score_cost_dimension(
                    preset, pack_config, requirements
                )

                # A zero value means unknown for reference/research presets,
                # not zero mass, zero volume, or free cells. Missing packaging
                # data cannot support pack-level energy or cost claims.
                if not has_packaging_data:
                    energy_score = 0.0
                    cost_score = 0.0

                lifetime_score = PrioritiesMixin._score_lifetime_dimension(
                    preset, requirements
                )

                charge_score = PrioritiesMixin._score_charge_dimension(
                    preset, requirements
                )

                # Total score = equal weight on all dimensions
                total_score = (
                    energy_score + power_score + cost_score +
                    lifetime_score + charge_score
                ) / 5.0

                # Check if hard constraints are met
                meets_requirements = has_packaging_data and (
                    pack_config.system_weight_kg <= requirements.get('weight_budget_kg', float('inf')) and
                    pack_config.system_volume_L <= requirements.get('volume_budget_L', float('inf')) and
                    pack_config.cost_per_kWh * pack_config.pack_energy_kWh <= requirements.get('cost_budget_usd', float('inf'))
                )

                # Generate recommendation
                recommendation = PrioritiesMixin._generate_recommendation(
                    preset, energy_score, power_score, cost_score,
                    lifetime_score, charge_score, meets_requirements
                )

                result = CellScoringResult(
                    preset_name=preset.name,
                    chemistry=preset.chemistry,
                    total_score=total_score,
                    energy_score=energy_score,
                    power_score=power_score,
                    cost_score=cost_score,
                    lifetime_score=lifetime_score,
                    charge_score=charge_score,
                    meets_requirements=meets_requirements,
                    recommendation=recommendation,
                    pack_config=pack_config,
                )
                results.append(result)

            except Exception as e:
                # Skip presets that fail to configure
                continue

        # Sort by total_score (best first)
        results.sort(key=lambda r: r.total_score, reverse=True)

        return results
