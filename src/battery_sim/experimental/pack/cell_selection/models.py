"""Immutable values used by this capability."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer

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
