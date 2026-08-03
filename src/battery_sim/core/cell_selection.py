"""Legacy cell-selection scoring kept separate from investigation primitives."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from battery_sim.core.pack import PackConfiguration, PackSizer


@dataclass(frozen=True)
class CellScoringResult:
    """
    Scored cell preset with breakdown and recommendation.
    
    TEACHING: A single cell gets evaluated across multiple dimensions.
    Each dimension scores 0-100, indicating how well it meets the requirement.
    Total score is a weighted average.
    
    meets_requirements: boolean indicating if ALL hard constraints are satisfied
    recommendation: one-sentence summary ("Best for power" or "Fails on cost")
    """
    
    preset_name: str
    """Name of the cell preset (e.g., 'LFP_5AH')"""
    
    chemistry: str
    """Chemistry type (e.g., 'LFP', 'NMC', 'NCA')"""
    
    total_score: float
    """Overall score 0-100 (equal weight on all dimensions)"""
    
    energy_score: float
    """Can target range be achieved within weight/volume budget? (0-100)"""
    
    power_score: float
    """Does C-rate meet peak power requirement? (0-100)"""
    
    cost_score: float
    """Does pack cost fit within budget? (0-100)"""
    
    lifetime_score: float
    """Does cycle life meet required lifetime? (0-100)"""
    
    charge_score: float
    """Can achieve target charge time? (0-100)"""
    
    meets_requirements: bool
    """True if all hard constraints (weight, volume, cost) are satisfied"""
    
    recommendation: str
    """One-sentence summary ("Best for..." or "Fails on...")"""
    
    pack_config: Optional[PackConfiguration] = None
    """Computed pack configuration for standard 60 kWh scenario"""


class CellSelectionScorer:
    """
    Score and rank cell presets against application requirements.
    
    TEACHING: When choosing a cell chemistry, engineers evaluate many dimensions:
    - Energy density: can we fit enough capacity in the allowed volume?
    - Power: can we deliver peak power without overheating?
    - Cost: is the pack affordable?
    - Lifetime: will it last the warranty period?
    - Charge speed: does it support fast charging if needed?
    
    This tool scores each cell 0-100 on each dimension, computes a total,
    and explains WHY each cell scores the way it does.
    
    Reality check: No single "best" cell exists. The choice depends on priorities.
    An EV prioritizing range wants high energy density.
    A performance EV prioritizes power (high discharge C-rate).
    An economy EV prioritizes cost.
    """
    
    # Thresholds (industry standards, adjustable)
    MIN_ENERGY_DENSITY_Wh_per_kg = 100.0  # Below this is uncompetitive
    TARGET_ENERGY_DENSITY_Wh_per_kg = 150.0  # Realistic EV target
    
    MIN_C_RATE = 1.0  # Can maintain 1C minimum for any use case
    HIGH_C_RATE = 3.0  # High-performance threshold
    
    MIN_CYCLE_LIFE = 1000  # Absolute minimum for automotive
    TARGET_CYCLE_LIFE = 3000  # Competitive 8-year warranty (250k km @ 25k km/year)
    
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
                energy_score = CellSelectionScorer._score_energy_dimension(
                    preset, pack_config, requirements
                )
                
                power_score = CellSelectionScorer._score_power_dimension(
                    preset, requirements
                )
                
                cost_score = CellSelectionScorer._score_cost_dimension(
                    preset, pack_config, requirements
                )

                # A zero value means unknown for reference/research presets,
                # not zero mass, zero volume, or free cells. Missing packaging
                # data cannot support pack-level energy or cost claims.
                if not has_packaging_data:
                    energy_score = 0.0
                    cost_score = 0.0
                
                lifetime_score = CellSelectionScorer._score_lifetime_dimension(
                    preset, requirements
                )
                
                charge_score = CellSelectionScorer._score_charge_dimension(
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
                recommendation = CellSelectionScorer._generate_recommendation(
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
        if energy_density >= CellSelectionScorer.TARGET_ENERGY_DENSITY_Wh_per_kg:
            density_bonus = 20
        elif energy_density >= CellSelectionScorer.MIN_ENERGY_DENSITY_Wh_per_kg:
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
        min_acceptable_c_rate = CellSelectionScorer.MIN_C_RATE
        
        if effective_pack_c_rate >= CellSelectionScorer.HIGH_C_RATE:
            # Can provide high power
            power_score = 100
        elif effective_pack_c_rate >= min_acceptable_c_rate:
            # Can provide adequate power
            power_score = 50 + 50 * (effective_pack_c_rate - min_acceptable_c_rate) / (CellSelectionScorer.HIGH_C_RATE - min_acceptable_c_rate)
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
