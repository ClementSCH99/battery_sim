# battery_sim/core/result.py
from typing import Optional, Dict
from battery_sim.types.timeseries import TimeSeries

class Result:
    def __init__(self, data: Dict[str, TimeSeries]):
        self._data = data

    def get(self, name: str) -> TimeSeries:
        return self._data[name]

    def final(self, name: str) -> float:
        return self._data[name].values[-1]

    def available_signals(self):
        return list(self._data.keys())
    
    def plot(self, names: Optional[list[str]]):
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