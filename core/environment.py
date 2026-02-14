# battery_sim/core/environment.py
from dataclasses import dataclass
from battery_sim.core.exceptions import EnvironmentValidationError
from typing import Optional

@dataclass(frozen=True)
class Environment:
    temperature_C: float
    convection_W_per_m2K: Optional[float] = None
    ambiant_temperature_C: Optional[float] = None

    def validate(self) -> None:
        if not (-40.0 <= self.temperature_C <= 100.0):
            raise EnvironmentValidationError(
                "Temperature outside of boundaries - Environment not valide"
            )
        if self.ambiant_temperature_C is not None:
            if not (-50.0 <= self.ambiant_temperature_C <= 80.0):
                raise EnvironmentValidationError(
                    "Temperature outside of boundaries - Environment not valide"
                )
        
        if self.convection_W_per_m2K is not None and self.convection_W_per_m2K <= 0:
            raise EnvironmentValidationError(
                "Convection coefficient must be positive - Environment not valide"
            )
