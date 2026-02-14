# battery_sim/core/result.py
from typing import Optional, Dict
from battery_sim.types.timeseries import TimeSeries
from battery_sim.types.signal import Signal

class Result:
    def __init__(self, data: Dict[Signal, TimeSeries]):
        self._data = data

    def get(self, signal: Signal) -> TimeSeries:
        return self._data[signal]

    def final(self, signal: Signal) -> float:
        return self._data[signal].values[-1]

    def available_signals(self) -> list[Signal]:
        return list(self._data.keys())
    
    def plot(self, names: Optional[list[Signal]]):
        import matplotlib.pyplot as plt

        if names is None:
            names = self.available_signals()

        for name in names:
            if name not in self._data:
                raise KeyError(f"Signal '{name}' not found")
            
            ts = self._data[name]
            plt.plot(ts.time_s, ts.values, label=name)
        
        plt.xlabel("Time [s]")
        plt.ylabel("Value")
        plt.grid(True)
        plt.tight_layout()
        plt.legend()
        plt.savefig("fig.jpeg")