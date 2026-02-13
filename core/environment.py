# battery_sim/core/environment.py
from dataclasses import dataclass
from battery_sim.core.exceptions import EnvironmentValidationError
from typing import Optional

@dataclass(frozen=True)
class Environment:
    temperature_C: float
    convection_W_per_m2K: Optional[float] = None

    def validate(self) -> None:
        if self.temperature_C > 100.0 or self.temperature_C < -40.0:
            raise EnvironmentValidationError(
                "Temperature outside of boundaries - Environment not valide"
            )
        
        if self.convection_W_per_m2K is not None and self.convection_W_per_m2K <= 0:
            raise EnvironmentValidationError(
                "Convection coefficient must be positive - Environment not valide"
            )
