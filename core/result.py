# battery_sim/core/result.py
from typing import Optional, Dict, List
import numpy as np
from battery_sim.types.timeseries import TimeSeries
from battery_sim.types.signal import Signal

class Result:
    def __init__(self, data: Dict[Signal, TimeSeries]):
        self._data = data

    def get(self, signal: Signal) -> TimeSeries:
        """Get raw TimeSeries data for a signal."""
        return self._data[signal]

    def final(self, signal: Signal) -> float:
        """Get final value of a signal."""
        return self._data[signal].values[-1]

    def available_signals(self) -> list[Signal]:
        """List all available signals in result."""
        return list(self._data.keys())
    
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
        return np.max(np.abs(power_ts.values))
    
    def average_power(self) -> Optional[float]:
        """Get average power (W)."""
        power_ts = self.power()
        if power_ts is None:
            return None
        return np.mean(power_ts.values)
    
    def min_voltage(self) -> Optional[float]:
        """Get minimum voltage (V)."""
        voltage_ts = self.voltage()
        if voltage_ts is None:
            return None
        return np.min(voltage_ts.values)
    
    def max_voltage(self) -> Optional[float]:
        """Get maximum voltage (V)."""
        voltage_ts = self.voltage()
        if voltage_ts is None:
            return None
        return np.max(voltage_ts.values)
    
    def final_soc(self) -> Optional[float]:
        """Get final state of charge (%)."""
        return self.final(Signal.SOC) if Signal.SOC in self._data else None
    
    def min_temperature(self) -> Optional[float]:
        """Get minimum temperature (°C or K)."""
        temp_ts = self.temperature()
        if temp_ts is None:
            return None
        return np.min(temp_ts.values)
    
    def max_temperature(self) -> Optional[float]:
        """Get maximum temperature (°C or K)."""
        temp_ts = self.temperature()
        if temp_ts is None:
            return None
        return np.max(temp_ts.values)
    
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
        valid_values = ir_ts.values[~np.isnan(ir_ts.values)]
        if len(valid_values) == 0:
            return None
        return np.mean(valid_values)
    
    def round_trip_efficiency(self) -> Optional[float]:
        """
        Estimate round-trip efficiency (%).
        Calculated from energy dissipation if available.
        
        Returns None if data insufficient.
        """
        if Signal.ENERGY not in self._data or Signal.POWER not in self._data:
            return None
        
        energy_ts = self.energy()
        power_ts = self.power()
        voltage_ts = self.voltage()
        
        if not all([energy_ts, power_ts, voltage_ts]):
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
    
    def state_variables_summary(self) -> Dict[Signal, Dict[str, float]]:
        """
        Get summary of all available state variables.
        Returns dict of Signal -> (min, mean, max, final) values.
        """
        summary = {}
        for signal, ts in self._data.items():
            if ts.values.size > 0:
                valid = ts.values[~np.isnan(ts.values)]
                if valid.size > 0:
                    summary[signal] = {
                        'min': float(np.min(valid)),
                        'mean': float(np.mean(valid)),
                        'max': float(np.max(valid)),
                        'final': float(ts.values[-1])
                    }
        return summary
    
    # ============ Plotting ============
    
    def plot(self, names: Optional[List[Signal]] = None):
        """Plot selected or all signals."""
        import matplotlib.pyplot as plt

        if names is None:
            names = self.available_signals()

        for name in names:
            if name not in self._data:
                raise KeyError(f"Signal '{name}' not found")
            
            ts = self._data[name]
            plt.plot(ts.time_s, ts.values, label=f"{name.value} ({ts.unit})")
        
        plt.xlabel("Time [s]")
        plt.ylabel("Value")
        plt.grid(True)
        plt.tight_layout()
        plt.legend()
        plt.savefig("fig.jpeg")
        
    def __repr__(self) -> str:
        """String representation with summary stats."""
        lines = ["Result Summary:"]
        for signal in self.available_signals():
            ts = self._data[signal]
            lines.append(f"  {signal.value:20s}: final={ts.values[-1]:10.3f} {ts.unit}")
        return "\n".join(lines)