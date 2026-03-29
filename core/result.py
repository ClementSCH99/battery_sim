# battery_sim/core/result.py
from typing import Optional, Dict, List, Any
import numpy as np
from battery_sim.types.timeseries import TimeSeries
from battery_sim.types.signal import Signal

class Result:
    """Signal payload for a completed simulation.

    Access time-series data via convenience methods (``voltage()``, ``soc()``, …)
    or generically via ``get(Signal.VOLTAGE)``.  Derived scalar metrics are
    available through ``total_energy()``, ``peak_power()``, ``min_voltage()``, etc.
    """

    def __init__(self, data: Dict[Signal, TimeSeries], parameter_override: Optional["Any"] = None):
        self._data = data
        # parameter_override is of type ParameterOverride from core.parameter_sweep
        # Using Any to avoid circular imports. Result is payload data, not the
        # canonical public return type of simulation execution.
        self.parameter_override = parameter_override

    def get(self, signal: Signal) -> TimeSeries:
        """Get raw TimeSeries data for a signal."""
        return self._data[signal]

    def final(self, signal: Signal) -> float:
        """Get final value of a signal."""
        return self._data[signal].values[-1]

    def available_signals(self) -> list[Signal]:
        """List all available signals in result."""
        return list(self._data.keys())
    
    def get_parameter_override(self) -> Optional["Any"]:
        """
        Get parameter override information (if any).
        
        Returns ParameterOverride object that tracks which parameters were modified,
        or None if simulation used default parameters.
        """
        return self.parameter_override
    
    def has_parameter_overrides(self) -> bool:
        """Check if result has any parameter overrides."""
        if self.parameter_override is None:
            return False
        return (bool(self.parameter_override.cell_parameters) or 
                bool(self.parameter_override.environment_parameters))
    
    # ============ Convenience accessors ============
    
    def soc(self) -> Optional[TimeSeries]:
        """Get State of Charge timeseries (%)."""
        return self._data.get(Signal.SOC)
    
    def voltage(self) -> Optional[TimeSeries]:
        """Get voltage timeseries (V)."""
        return self._data.get(Signal.VOLTAGE)
    
    def current(self) -> Optional[TimeSeries]:
        """Get current timeseries (A)."""
        return self._data.get(Signal.CURRENT)
    
    def temperature(self) -> Optional[TimeSeries]:
        """Get temperature timeseries (°C or K)."""
        return self._data.get(Signal.TEMPERATURE)
    
    def power(self) -> Optional[TimeSeries]:
        """Get power timeseries (W)."""
        return self._data.get(Signal.POWER)
    
    def energy(self) -> Optional[TimeSeries]:
        """Get energy timeseries (Wh)."""
        return self._data.get(Signal.ENERGY)
    
    def capacity(self) -> Optional[TimeSeries]:
        """Get capacity timeseries (Ah) - cumulative charge."""
        return self._data.get(Signal.CAPACITY)
    
    # ============ Analysis methods ============
    
    def total_energy(self) -> Optional[float]:
        """
        Calculate total energy delivered/stored (Wh).
        Returns the final value of the energy integral.
        """
        energy_ts = self.energy()
        if energy_ts is None:
            return None
        return energy_ts.values[-1]
    
    def total_energy_Wh(self) -> Optional[float]:
        """
        Calculate total energy delivered/stored (Wh).
        Alias for total_energy() for backward compatibility.
        """
        return self.total_energy()
    
    def total_capacity_delivered(self) -> Optional[float]:
        """
        Calculate total charge delivered (Ah).
        Returns the final value of the capacity integral.
        """
        capacity_ts = self.capacity()
        if capacity_ts is None:
            return None
        return capacity_ts.values[-1]
    
    def peak_power(self) -> Optional[float]:
        """Get maximum absolute power (W)."""
        power_ts = self.power()
        if power_ts is None:
            return None
        return float(np.max(np.abs(power_ts.values)))
    
    def average_power(self) -> Optional[float]:
        """Get average power (W)."""
        power_ts = self.power()
        if power_ts is None:
            return None
        return float(np.mean(power_ts.values))
    
    def min_voltage(self) -> Optional[float]:
        """Get minimum voltage (V)."""
        voltage_ts = self.voltage()
        if voltage_ts is None:
            return None
        return float(np.min(voltage_ts.values))
    
    def max_voltage(self) -> Optional[float]:
        """Get maximum voltage (V)."""
        voltage_ts = self.voltage()
        if voltage_ts is None:
            return None
        return float(np.max(voltage_ts.values))
    
    def peak_voltage(self) -> Optional[float]:
        """Get peak voltage during simulation (V). Alias for max_voltage()."""
        return self.max_voltage()
    
    def peak_current(self) -> Optional[float]:
        """Get maximum absolute current (A)."""
        current_ts = self.current()
        if current_ts is None:
            return None
        return float(np.max(np.abs(current_ts.values)))
    
    def final_soc(self) -> Optional[float]:
        """Get final state of charge (%)."""
        return self.final(Signal.SOC) if Signal.SOC in self._data else None
    
    def min_temperature(self) -> Optional[float]:
        """Get minimum temperature (°C or K)."""
        temp_ts = self.temperature()
        if temp_ts is None:
            return None
        return float(np.min(temp_ts.values))
    
    def max_temperature(self) -> Optional[float]:
        """Get maximum temperature (°C or K)."""
        temp_ts = self.temperature()
        if temp_ts is None:
            return None
        return float(np.max(temp_ts.values))
    
    def internal_resistance(self) -> Optional[TimeSeries]:
        """Get approximate internal resistance over time (Ω)."""
        return self._data.get(Signal.INTERNAL_RESISTANCE)
    
    def average_internal_resistance(self) -> Optional[float]:
        """
        Get average internal resistance during current flow.
        Excludes near-zero current points to avoid noise.
        """
        ir_ts = self.internal_resistance()
        if ir_ts is None:
            return None
        # Filter out NaN values
        values_array = np.array(ir_ts.values)
        valid_values = values_array[~np.isnan(values_array)]
        if len(valid_values) == 0:
            return None
        return float(np.mean(valid_values))
    
    def round_trip_efficiency(self) -> Optional[float]:
        """
        Estimate round-trip efficiency (%).
        Calculated from energy dissipation if available.
        
        Returns None if data insufficient.
        """
        energy_ts = self.energy()
        power_ts = self.power()
        voltage_ts = self.voltage()
        
        if energy_ts is None or power_ts is None or voltage_ts is None:
            return None
        
        # Separates charge and discharge phases based on current/power
        charge_energy = 0.0
        discharge_energy = 0.0
        
        for i, power in enumerate(power_ts.values):
            if power < 0:  # Charging (negative power)
                charge_energy += abs(power) * (power_ts.time_s[i] if i > 0 else 0)
            else:  # Discharging
                discharge_energy += power * (power_ts.time_s[i] if i > 0 else 0)
        
        if charge_energy > 0:
            return (discharge_energy / charge_energy) * 100.0
        return None
    
    def charged_capacity(self) -> Optional[float]:
        """
        Get total charge capacity delivered into battery (Ah).
        Integrates negative current (charging phases).
        """
        current_ts = self.current()
        if current_ts is None:
            return None
        
        current = np.array(current_ts.values)
        time = np.array(current_ts.time_s)
        dt = np.diff(time)
        
        # Sum negative currents (charging): I < 0
        charged_increments = np.where(current[:-1] < 0, np.abs(current[:-1]) * dt / 3600.0, 0)
        return float(np.sum(charged_increments))
    
    def discharged_capacity(self) -> Optional[float]:
        """
        Get total discharge capacity delivered from battery (Ah).
        Integrates positive current (discharging phases).
        """
        current_ts = self.current()
        if current_ts is None:
            return None
        
        current = np.array(current_ts.values)
        time = np.array(current_ts.time_s)
        dt = np.diff(time)
        
        # Sum positive currents (discharging): I > 0
        discharged_increments = np.where(current[:-1] > 0, current[:-1] * dt / 3600.0, 0)
        return float(np.sum(discharged_increments))
    
    def net_capacity(self) -> Optional[float]:
        """
        Get net capacity (discharged - charged) (Ah).
        Positive means more discharged than charged (net discharge).
        """
        discharged = self.discharged_capacity()
        charged = self.charged_capacity()
        
        if discharged is None or charged is None:
            return None
        return discharged - charged
    
    def charged_energy(self) -> Optional[float]:
        """
        Get total energy charged into battery (Wh).
        Integrates power during charging phases (negative current).
        """
        current_ts = self.current()
        voltage_ts = self.voltage()
        
        if current_ts is None or voltage_ts is None:
            return None
        
        current = np.array(current_ts.values)
        voltage = np.array(voltage_ts.values)
        time = np.array(current_ts.time_s)
        dt = np.diff(time)
        
        # Sum energy during charging (I < 0): E_in = |V * I * dt|
        power = voltage[:-1] * current[:-1]
        charged_increments = np.where(current[:-1] < 0, np.abs(power) * dt / 3600.0, 0)
        return float(np.sum(charged_increments))
    
    def discharged_energy(self) -> Optional[float]:
        """
        Get total energy discharged from battery (Wh).
        Integrates power during discharging phases (positive current).
        """
        current_ts = self.current()
        voltage_ts = self.voltage()
        
        if current_ts is None or voltage_ts is None:
            return None
        
        current = np.array(current_ts.values)
        voltage = np.array(voltage_ts.values)
        time = np.array(current_ts.time_s)
        dt = np.diff(time)
        
        # Sum energy during discharging (I > 0): E_out = V * I * dt
        power = voltage[:-1] * current[:-1]
        discharged_increments = np.where(current[:-1] > 0, power * dt / 3600.0, 0)
        return float(np.sum(discharged_increments))
    
    def net_energy(self) -> Optional[float]:
        """
        Get net energy (discharged - charged) (Wh).
        Positive means more energy was output than input (net discharge).
        """
        discharged = self.discharged_energy()
        charged = self.charged_energy()
        
        if discharged is None or charged is None:
            return None
        return discharged - charged
    
    def charge_discharge_efficiency(self) -> Optional[float]:
        """
        Get charge-discharge round-trip efficiency (%).
        Calculated as: (energy_discharged / energy_charged) * 100
        For discharge-only scenarios, returns 100 (no charging losses).
        """
        charged_e = self.charged_energy()
        discharged_e = self.discharged_energy()
        
        if charged_e is None or discharged_e is None:
            return None
        
        if charged_e <= 0:
            # Discharge-only: assume 100% efficiency (no charging losses to account for)
            if discharged_e > 0:
                return 100.0
            return None
        
        return (discharged_e / charged_e) * 100.0
    
    def efficiency(self) -> Optional[float]:
        """
        Get average efficiency during simulation (%).
        Uses the EFFICIENCY signal if available, falls back to charge_discharge_efficiency.
        """
        efficiency_ts = self._data.get(Signal.EFFICIENCY)
        if efficiency_ts is not None:
            # Get average efficiency, excluding any remaining NaN values
            values = np.array(efficiency_ts.values)
            valid_values = values[~np.isnan(values)]
            if len(valid_values) > 0:
                return float(np.mean(valid_values))
        
        # Fall back to charge-discharge efficiency calculation
        return self.charge_discharge_efficiency()
    
    def state_variables_summary(self) -> Dict[Signal, Dict[str, float]]:
        """
        Get summary of all available state variables.
        Returns dict of Signal -> (min, mean, max, final) values.
        """
        summary = {}
        for signal, ts in self._data.items():
            values_array = np.array(ts.values)
            if len(values_array) > 0:
                valid = values_array[~np.isnan(values_array)]
                if len(valid) > 0:
                    summary[signal] = {
                        'min': float(np.min(valid)),
                        'mean': float(np.mean(valid)),
                        'max': float(np.max(valid)),
                        'final': float(ts.values[-1])
                    }
        return summary
    
    def __repr__(self) -> str:
        """String representation with summary stats."""
        lines = ["Result Summary:"]
        for signal in self.available_signals():
            ts = self._data[signal]
            lines.append(f"  {signal.value:20s}: final={ts.values[-1]:10.3f} {ts.unit}")
        return "\n".join(lines)
