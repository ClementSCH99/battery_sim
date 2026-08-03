# battery_sim/core/result_analyzer.py
"""
ResultAnalyzer: Advanced post-processing and analysis of simulation results.

Provides:
- Cycle detection and counting
- Capacity fade over multiple cycles
- Efficiency trends
- Depth of discharge (DoD) tracking
- State of Health (SOH) estimation
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from battery_sim.core.result import Result
from battery_sim.core.result import Signal


@dataclass
class CycleInfo:
    """Information about a charge/discharge cycle."""
    cycle_number: int
    start_time_s: float
    end_time_s: float
    capacity_charged_Ah: float
    capacity_discharged_Ah: float
    energy_in_Wh: float
    energy_out_Wh: float
    efficiency: float  # %
    min_voltage_V: float
    max_voltage_V: float
    min_soc: float  # %
    max_soc: float  # %
    depth_of_discharge: float  # % of nominal capacity
    

class ResultAnalyzer:
    """
    Advanced analysis of battery simulation results.
    """
    
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
