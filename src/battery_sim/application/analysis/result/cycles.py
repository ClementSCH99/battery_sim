"""Focused cycles behavior."""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from battery_sim.core.result import Result
from battery_sim.core.result import Signal

from battery_sim.application.analysis.result.models import (
    CycleInfo,
)

class CyclesMixin:
    def detect_cycles(self, 
                     soc_threshold_percent: float = 10.0,
                     nominal_capacity_Ah: Optional[float] = None
                     ) -> List[CycleInfo]:
        """
        Detect and analyze charge/discharge cycles.

        A cycle is detected when:
        - SOC crosses threshold (charge detected)
        - SOC drops back below threshold (discharge complete)

        Args:
            soc_threshold_percent: Minimum SOC change to count as cycle
            nominal_capacity_Ah: For DoD calculation (if None, uses delivered capacity)

        Returns:
            List of CycleInfo objects
        """
        soc_ts = self.result.soc()
        if soc_ts is None:
            return []

        soc = np.array(soc_ts.values)
        time = np.array(soc_ts.time_s)

        # Detect charging phases (SOC increasing)
        is_charging = np.diff(soc) > 0.0
        charge_indices = np.where(is_charging)[0]

        cycles = []
        cycle_num = 0

        i = 0
        while i < len(soc) - 1:
            # Find start of charging
            while i < len(soc) - 1 and not is_charging[i]:
                i += 1

            if i >= len(soc) - 1:
                break

            charge_start_idx = i
            charge_start_time = time[charge_start_idx]

            # Find end of charging
            while i < len(soc) - 1 and is_charging[i]:
                i += 1

            charge_end_idx = i
            charge_end_time = time[charge_end_idx]

            # Detect associated discharge
            discharge_start_idx = charge_end_idx
            discharge_start_time = charge_end_time

            # Find end of discharge (SOC drops significantly)
            while i < len(soc) - 1 and (is_charging[i] or (soc[i] - soc[discharge_start_idx] > -soc_threshold_percent)):
                i += 1

            if i >= len(soc) - 1:
                i = len(soc) - 1

            discharge_end_idx = i
            discharge_end_time = time[discharge_end_idx]

            # Calculate cycle metrics
            soc_charged = soc[charge_end_idx] - soc[charge_start_idx]
            soc_discharged = soc[charge_start_idx] - soc[discharge_end_idx]

            if soc_charged > soc_threshold_percent:  # Only count if significant
                cycle_num += 1

                # Energy and capacity in this cycle
                current_ts = self.result.current()
                voltage_ts = self.result.voltage()

                charge_Ah = 0.0
                discharge_Ah = 0.0
                energy_in_Wh = 0.0
                energy_out_Wh = 0.0
                min_v = float('inf')
                max_v = float('-inf')

                if current_ts and voltage_ts:
                    for j in range(charge_start_idx, charge_end_idx):
                        dt = time[j + 1] - time[j] if j + 1 < len(time) else 0
                        if current_ts.values[j] < 0:  # Charging
                            charge_Ah += abs(current_ts.values[j]) * dt / 3600.0
                            energy_in_Wh += abs(voltage_ts.values[j] * current_ts.values[j]) * dt / 3600.0
                        min_v = min(min_v, voltage_ts.values[j])
                        max_v = max(max_v, voltage_ts.values[j])

                    for j in range(discharge_start_idx, discharge_end_idx):
                        dt = time[j + 1] - time[j] if j + 1 < len(time) else 0
                        if current_ts.values[j] > 0:  # Discharging
                            discharge_Ah += abs(current_ts.values[j]) * dt / 3600.0
                            energy_out_Wh += abs(voltage_ts.values[j] * current_ts.values[j]) * dt / 3600.0
                        min_v = min(min_v, voltage_ts.values[j])
                        max_v = max(max_v, voltage_ts.values[j])

                efficiency = 0.0
                if energy_in_Wh > 0:
                    efficiency = (energy_out_Wh / energy_in_Wh) * 100.0

                dod = 0.0
                if nominal_capacity_Ah and nominal_capacity_Ah > 0:
                    dod = (discharge_Ah / nominal_capacity_Ah) * 100.0

                cycle_info = CycleInfo(
                    cycle_number=cycle_num,
                    start_time_s=charge_start_time,
                    end_time_s=discharge_end_time,
                    capacity_charged_Ah=charge_Ah,
                    capacity_discharged_Ah=discharge_Ah,
                    energy_in_Wh=energy_in_Wh,
                    energy_out_Wh=energy_out_Wh,
                    efficiency=efficiency,
                    min_voltage_V=min_v if min_v != float('inf') else 0.0,
                    max_voltage_V=max_v if max_v != float('-inf') else 0.0,
                    min_soc=min(soc[charge_start_idx], soc[discharge_end_idx]),
                    max_soc=soc[charge_end_idx],
                    depth_of_discharge=dod
                )

                cycles.append(cycle_info)

        return cycles
