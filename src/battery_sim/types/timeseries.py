# battery_sim/types/timeseries.py
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class TimeSeries:
    time_s: List[float]
    values: List[float]
    unit: str
