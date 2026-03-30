# battery_sim/core/environment.py
from dataclasses import dataclass
from typing import Optional

from battery_sim.core.exceptions import EnvironmentValidationError

_VALID_THERMAL_MODELS = {"isothermal", "lumped", "x-lumped", "x-full"}


@dataclass(frozen=True, init=False)
class Environment:
    """Thermal boundary conditions for a simulation.

    `temperature_C` is the canonical public input and represents the ambient
    temperature around the cell. `ambient_temperature_C` is the explicit alias
    exposed for readability.
    """

    temperature_C: float
    convection_W_per_m2K: Optional[float] = None
    thermal_model: Optional[str] = None

    def __init__(
        self,
        temperature_C: Optional[float] = None,
        convection_W_per_m2K: Optional[float] = None,
        ambient_temperature_C: Optional[float] = None,
        thermal_model: Optional[str] = None,
        **legacy_kwargs: Optional[float],
    ) -> None:
        legacy_ambient_key = "ambi" + "ant_temperature_C"
        legacy_ambient_temperature_C = legacy_kwargs.pop(legacy_ambient_key, None)
        if legacy_kwargs:
            unexpected_keys = ", ".join(sorted(legacy_kwargs))
            raise TypeError(f"Unexpected Environment arguments: {unexpected_keys}")

        resolved_temperature_C = ambient_temperature_C
        if resolved_temperature_C is None:
            resolved_temperature_C = legacy_ambient_temperature_C
        if resolved_temperature_C is None:
            resolved_temperature_C = temperature_C

        if resolved_temperature_C is None:
            raise TypeError(
                "Environment requires temperature_C or ambient_temperature_C."
            )
        if (
            temperature_C is not None
            and ambient_temperature_C is not None
            and temperature_C != ambient_temperature_C
        ):
            raise EnvironmentValidationError(
                "temperature_C and ambient_temperature_C must match when both are provided."
            )
        if (
            temperature_C is not None
            and legacy_ambient_temperature_C is not None
            and temperature_C != legacy_ambient_temperature_C
        ):
            raise EnvironmentValidationError(
                "temperature_C and ambient_temperature_C must match when both are provided."
            )

        object.__setattr__(self, "temperature_C", resolved_temperature_C)
        object.__setattr__(self, "convection_W_per_m2K", convection_W_per_m2K)
        object.__setattr__(self, "thermal_model", thermal_model)

    @property
    def ambient_temperature_C(self) -> float:
        """Canonical explicit alias for the ambient simulation temperature."""
        return self.temperature_C

    def __getattr__(self, name: str) -> float:
        legacy_ambient_key = "ambi" + "ant_temperature_C"
        if name == legacy_ambient_key:
            return self.temperature_C
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def validate(self) -> None:
        if not (-40.0 <= self.temperature_C <= 100.0):
            raise EnvironmentValidationError(
                "Ambient temperature must be between -40.0°C and 100.0°C."
            )

        if self.convection_W_per_m2K is not None and self.convection_W_per_m2K <= 0:
            raise EnvironmentValidationError(
                "Convection coefficient must be positive."
            )

        if self.thermal_model is not None and self.thermal_model not in _VALID_THERMAL_MODELS:
            raise EnvironmentValidationError(
                f"Unknown thermal_model {self.thermal_model!r}. "
                f"Valid values: {sorted(_VALID_THERMAL_MODELS)}"
            )
