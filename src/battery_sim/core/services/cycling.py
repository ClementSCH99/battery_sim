"""Pure analysis helpers for multi-cycle SimulationRun signals."""

from typing import Any, Optional

import numpy as np

from battery_sim.core.simulation_run import SimulationRun
from battery_sim.types.signal import Signal


class CyclingAnalyzer:
    @staticmethod
    def capacity_fade_rate(run: SimulationRun) -> Optional[float]:
        ts = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        if ts is None or len(ts.values) < 2:
            return None
        slope, _ = np.polyfit(np.array(ts.time_s), np.array(ts.values), 1)
        return float(slope)

    @staticmethod
    def end_of_life_prediction(
        run: SimulationRun, eol_threshold: float = 0.8
    ) -> Optional[int]:
        ts = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        if ts is None or len(ts.values) < 2:
            return None
        slope, intercept = np.polyfit(np.array(ts.time_s), np.array(ts.values), 1)
        if slope >= 0:
            return None
        threshold_capacity = ts.values[0] * eol_threshold
        return max(int(np.ceil((threshold_capacity - intercept) / slope)), 1)

    @staticmethod
    def cycling_summary(run: SimulationRun) -> dict[str, Any]:
        summary = {}
        for signal, key in (
            (Signal.CYCLE_DISCHARGE_CAPACITY, "discharge_capacity_Ah"),
            (Signal.CYCLE_CHARGE_CAPACITY, "charge_capacity_Ah"),
            (Signal.CYCLE_COULOMBIC_EFFICIENCY, "coulombic_efficiency_pct"),
            (Signal.CYCLE_CAPACITY_RETENTION, "capacity_retention_pct"),
        ):
            timeseries = run.result._data.get(signal)
            if timeseries is not None:
                summary[key] = timeseries.values
        return summary
