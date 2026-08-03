"""Focused excursions behavior."""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from battery_sim.core.result import Result
from battery_sim.core.result import Signal

from battery_sim.application.analysis.result.models import (
    CycleInfo,
)

class ExcursionsMixin:
    def temperature_excursions(self, 
                              min_temp_C: float = 0.0,
                              max_temp_C: float = 60.0
                              ) -> Dict[str, Any]:
        """
        Analyze temperature excursions outside safe bounds.

        Args:
            min_temp_C: Minimum safe temperature
            max_temp_C: Maximum safe temperature

        Returns:
            Dict with excursion statistics
        """
        temp_ts = self.result.temperature()
        if temp_ts is None:
            return {}

        temp = np.array(temp_ts.values)

        below_min = temp < min_temp_C
        above_max = temp > max_temp_C

        below_count = np.sum(below_min)
        above_count = np.sum(above_max)

        excursions = {
            'below_min_count': int(below_count),
            'above_max_count': int(above_count),
            'min_temperature': float(np.min(temp)),
            'max_temperature': float(np.max(temp)),
            'mean_temperature': float(np.mean(temp)),
        }

        if below_count > 0:
            excursions['min_below_threshold'] = float(np.min(temp[below_min]))
        if above_count > 0:
            excursions['max_above_threshold'] = float(np.max(temp[above_max]))

        return excursions
    def voltage_excursions(self,
                          min_voltage_V: float = 2.5,
                          max_voltage_V: float = 4.2
                          ) -> Dict[str, Any]:
        """
        Analyze voltage excursions outside safe bounds.

        Args:
            min_voltage_V: Minimum safe voltage
            max_voltage_V: Maximum safe voltage

        Returns:
            Dict with excursion statistics
        """
        voltage_ts = self.result.voltage()
        if voltage_ts is None:
            return {}

        voltage = np.array(voltage_ts.values)

        below_min = voltage < min_voltage_V
        above_max = voltage > max_voltage_V

        below_count = np.sum(below_min)
        above_count = np.sum(above_max)

        excursions = {
            'below_min_count': int(below_count),
            'above_max_count': int(above_count),
            'min_voltage': float(np.min(voltage)),
            'max_voltage': float(np.max(voltage)),
            'mean_voltage': float(np.mean(voltage)),
        }

        if below_count > 0:
            excursions['min_below_threshold'] = float(np.min(voltage[below_min]))
        if above_count > 0:
            excursions['max_above_threshold'] = float(np.max(voltage[above_max]))

        return excursions
