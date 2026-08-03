"""Composed OperatingWindowAnalyzer facade."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import ConstantCurrent, Protocol, Rest
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig
from battery_sim.experimental.limits.operating_window.models import (
    OperatingWindowPoint,
)
from battery_sim.experimental.limits.operating_window.analysis import AnalysisMixin
from battery_sim.experimental.limits.operating_window.evaluation import EvaluationMixin
from battery_sim.experimental.limits.operating_window.classification import ClassificationMixin

class OperatingWindowAnalyzer(
    AnalysisMixin,
    EvaluationMixin,
    ClassificationMixin,
):
    """
    Screen voltage response across SOC, ambient temperature and discharge C-rate.

    The labels produced here are exploratory voltage-pulse classifications. They
    are not safety qualification results or calibrated BMS limits.

    The safe operating window defines regions:
    - **SAFE**: Normal operation, minimal aging risk
    - **CAUTION**: Acceptable but degradation increases, monitor conditions
    - **AVOID**: Dangerous - high risk of damage, should not happen in production

    Classification criteria:
    - safe: voltage bounds maintained, temp rise < 10°C, simulation stable
    - caution: voltage near limits OR temp rise 10-20°C
    - avoid: voltage violation, temp rise > 20°C, or simulation failure

    Grid resolution:
    - coarse: 3×3×3 = 27 scenarios (fast, for testing)
    - fine: 5×5×5 = 125 scenarios (more detailed screening)
    """
