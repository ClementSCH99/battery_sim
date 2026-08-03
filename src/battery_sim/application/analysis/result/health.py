"""Focused health behavior."""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from battery_sim.core.result import Result
from battery_sim.core.result import Signal

from battery_sim.application.analysis.result.models import (
    CycleInfo,
)

class HealthMixin:
    def __init__(self, result: Result):
        self.result = result
    def capacity_fade(self, reference_capacity_Ah: float) -> Optional[float]:
        """
        Estimate capacity fade as percentage of reference.

        Args:
            reference_capacity_Ah: Initial/nominal capacity for comparison

        Returns:
            Capacity fade in % (0 = no fade, 100 = complete fade)
        """
        capacity_ts = self.result.capacity()
        if capacity_ts is None or reference_capacity_Ah <= 0:
            return None

        delivered_Ah = capacity_ts.values[-1]
        fade_percent = (1.0 - delivered_Ah / reference_capacity_Ah) * 100.0
        return max(0.0, fade_percent)  # Clamp to 0-100
    def state_of_health(self, reference_capacity_Ah: float) -> Optional[float]:
        """
        Estimate State of Health (SOH) as percentage of reference.
        Inverse of capacity fade: SOH = 100 - fade%

        Args:
            reference_capacity_Ah: Initial/nominal capacity

        Returns:
            SOH in % (100% = new battery, <80% = end of life typical)
        """
        fade = self.capacity_fade(reference_capacity_Ah)
        if fade is None:
            return None
        return 100.0 - fade
