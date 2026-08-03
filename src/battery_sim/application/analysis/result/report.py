"""Focused report behavior."""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from battery_sim.core.result import Result
from battery_sim.core.result import Signal

from battery_sim.application.analysis.result.models import (
    CycleInfo,
)

class ReportMixin:
    def summary_report(self, nominal_capacity_Ah: Optional[float] = None) -> str:
        """
        Generate a comprehensive text report of results.

        Args:
            nominal_capacity_Ah: For capacity fade and DoD calculations

        Returns:
            Formatted text report
        """
        lines = ["=" * 70]
        lines.append("BATTERY SIMULATION RESULT ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Basic metrics
        lines.append("BASIC METRICS")
        lines.append("-" * 70)
        total_energy = self.result.total_energy()
        if total_energy:
            lines.append(f"  Total Energy:              {total_energy:10.3f} Wh")

        total_capacity = self.result.total_capacity_delivered()
        if total_capacity:
            lines.append(f"  Total Capacity:            {total_capacity:10.3f} Ah")

        peak_power = self.result.peak_power()
        if peak_power:
            lines.append(f"  Peak Power:                {peak_power:10.3f} W")

        avg_power = self.result.average_power()
        if avg_power:
            lines.append(f"  Average Power:             {avg_power:10.3f} W")

        min_v = self.result.min_voltage()
        max_v = self.result.max_voltage()
        if min_v and max_v:
            lines.append(f"  Voltage Range:             {min_v:6.2f} - {max_v:6.2f} V")

        min_t = self.result.min_temperature()
        max_t = self.result.max_temperature()
        if min_t and max_t:
            lines.append(f"  Temperature Range:         {min_t:6.2f} - {max_t:6.2f} °C")

        lines.append("")

        # Capacity and health
        if nominal_capacity_Ah:
            lines.append("CAPACITY & HEALTH")
            lines.append("-" * 70)
            soh = self.state_of_health(nominal_capacity_Ah)
            if soh:
                lines.append(f"  State of Health (SOH):     {soh:6.2f} %")
            fade = self.capacity_fade(nominal_capacity_Ah)
            if fade:
                lines.append(f"  Capacity Fade:             {fade:6.2f} %")
            lines.append("")

        # Cycle analysis
        cycles = self.detect_cycles(nominal_capacity_Ah=nominal_capacity_Ah)
        if cycles:
            lines.append("CYCLE ANALYSIS")
            lines.append("-" * 70)
            lines.append(f"  Total Cycles Detected:     {len(cycles):d}")
            if len(cycles) > 0:
                avg_efficiency = np.mean([c.efficiency for c in cycles])
                lines.append(f"  Average Efficiency:        {avg_efficiency:6.2f} %")
            lines.append("")

        # Temperature excursions
        temp_exc = self.temperature_excursions()
        if temp_exc:
            lines.append("TEMPERATURE ANALYSIS")
            lines.append("-" * 70)
            lines.append(f"  Min/Max:                   {temp_exc['min_temperature']:6.2f} / {temp_exc['max_temperature']:6.2f} °C")
            lines.append(f"  Mean:                      {temp_exc['mean_temperature']:6.2f} °C")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)
