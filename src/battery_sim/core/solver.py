# battery_sim/core/solver.py
from dataclasses import dataclass
from battery_sim.core.exceptions import SolverValidationError
from typing import Optional
from enum import Enum

from battery_sim.core.protocol import Protocol

import numpy as np



class Solver(Enum):
    CASADI = "casadi"
    SCIPY = "scipy"

@dataclass(frozen=True)
class SolverConfig:
    solver: Solver = Solver.CASADI
    rtol: float = 1e-6
    atol: float = 1e-9
    time_step_s: Optional[float] = None
    initial_soc: float = 1.0  # Initial state of charge [0, 1]

    def build_t_eval(self, protocol: Protocol) -> Optional[np.ndarray]:
        if self.time_step_s is None:
            return None
        
        final_time = protocol.total_duration_s()
        return np.arange(0, final_time + self.time_step_s, self.time_step_s)
    
    def validate(self) -> None:
        if self.rtol < 0.0 or self.atol < 0.0:
            raise SolverValidationError(
                "rtol and atol must be striclty positive - SolverConfig is not valide."
            )
        elif self.time_step_s is not None and self.time_step_s < 0.0:
            raise SolverValidationError(
                "time_step_s must be strictly positive - SolverConfig is not valide."
            )
        elif not (0.0 <= self.initial_soc <= 1.0):
            raise SolverValidationError(
                "initial_soc must be between 0.0 and 1.0 - SolverConfig is not valide."
            )