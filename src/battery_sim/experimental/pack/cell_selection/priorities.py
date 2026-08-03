"""Focused priorities behavior."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer

from battery_sim.experimental.pack.cell_selection.models import (
    CellScoringResult,
)

class PrioritiesMixin:
    @staticmethod
    def _score_lifetime_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score cycle life vs warranty requirement.

        TEACHING: Will it last long enough?

        Scoring:
        - 100: Cycle life 3× warranty requirement
        - 50: Cycle life meets warranty requirement exactly
        - 0: Cycle life insufficient
        """

        lifetime_years = requirements.get('lifetime_years', 8.0)

        # Estimate cycles from lifetime
        # Assume 250 km range, driven 25k km/year = 100 cycles/year
        # (simplification: ignores calendar aging, assumes cycle-dominated)
        cycles_needed = int(lifetime_years * 100)

        cycle_life = preset.cycle_life_cycles

        # If no cycle life data, assume 3000 (LFP typical)
        if cycle_life == 0:
            cycle_life = 3000

        if cycle_life >= cycles_needed * 3:
            # Excellent cycle life
            lifetime_score = 100
        elif cycle_life >= cycles_needed:
            # Meets requirement
            lifetime_score = 50 + 50 * min(1.0, (cycle_life - cycles_needed) / (cycles_needed * 2))
        else:
            # Insufficient
            lifetime_score = 0

        return lifetime_score
    @staticmethod
    def _score_charge_dimension(
        preset,  # CellPreset
        requirements: Dict[str, Any],
    ) -> float:
        """
        Score charging speed capability.

        TEACHING: Can it support fast charging if needed?

        Scoring:
        - 100: Supports 2C+ charging (very fast)
        - 50: Supports 1C charging
        - 0: Cannot support target charge time
        """

        charge_time_min = requirements.get('charge_time_min', None)

        if charge_time_min is None:
            # No charge time constraint; assume 1C is acceptable
            charge_score = 50
        else:
            # Estimate required C-rate from charge time
            # Assume 10-80% charge = 70% capacity × C-rate, time in hours
            # time_mins = (0.7 * 60 * cell_capacity) / (c_rate * cell_capacity)
            # time_mins = 42 / c_rate (in minutes)
            # c_rate = 42 / time_mins

            required_c_rate = 42 / charge_time_min  # Per cell

            max_charge_c_rate = preset.max_charge_c_rate

            if max_charge_c_rate >= required_c_rate:
                # Can support required charge time
                # Bonus if can do it comfortably (at lower thermal stress)
                overhead_ratio = required_c_rate / max_charge_c_rate
                charge_score = 70 + 30 * overhead_ratio
            else:
                # Cannot support charge time
                charge_score = max(0, 70 * max_charge_c_rate / required_c_rate)

        return charge_score
    @staticmethod
    def _generate_recommendation(
        preset,  # CellPreset
        energy_score: float,
        power_score: float,
        cost_score: float,
        lifetime_score: float,
        charge_score: float,
        meets_requirements: bool,
    ) -> str:
        """
        Generate one-sentence recommendation.

        TEACHING: Explain why each cell is matched (or not) to the application.
        """

        if not meets_requirements:
            # Identify which constraint is most violated
            if energy_score < 30:
                return f"{preset.name}: Fails on energy (weight/volume too high)"
            elif cost_score < 30:
                return f"{preset.name}: Exceeds cost budget"
            elif lifetime_score < 30:
                return f"{preset.name}: Insufficient cycle life for warranty"
            else:
                return f"{preset.name}: Does not meet one or more hard constraints"

        # Find strongest dimensions
        strengths = []
        if energy_score >= 80:
            strengths.append("excellent energy density")
        if power_score >= 80:
            strengths.append("high power capability")
        if cost_score >= 80:
            strengths.append("competitive cost")
        if lifetime_score >= 80:
            strengths.append("long cycle life")

        if strengths:
            return f"{preset.name}: Best for {' and '.join(strengths)}"
        else:
            return f"{preset.name}: Balanced option with {preset.chemistry} chemistry"
