"""Immutable values used by this capability."""

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
