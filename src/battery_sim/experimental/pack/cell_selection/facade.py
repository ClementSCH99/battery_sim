"""Composed CellSelectionScorer facade."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.experimental.pack.model import PackConfiguration, PackSizer
from battery_sim.experimental.pack.cell_selection.models import (
    CellScoringResult,
)
from battery_sim.experimental.pack.cell_selection.score import ScoreMixin
from battery_sim.experimental.pack.cell_selection.dimensions import DimensionsMixin
from battery_sim.experimental.pack.cell_selection.priorities import PrioritiesMixin

class CellSelectionScorer(
    ScoreMixin,
    DimensionsMixin,
    PrioritiesMixin,
):
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
    MIN_ENERGY_DENSITY_Wh_per_kg = 100.0  # Below this is uncompetitive
    TARGET_ENERGY_DENSITY_Wh_per_kg = 150.0  # Realistic EV target
    MIN_C_RATE = 1.0  # Can maintain 1C minimum for any use case
    HIGH_C_RATE = 3.0  # High-performance threshold
    MIN_CYCLE_LIFE = 1000  # Absolute minimum for automotive
    TARGET_CYCLE_LIFE = 3000  # Competitive 8-year warranty (250k km @ 25k km/year)
