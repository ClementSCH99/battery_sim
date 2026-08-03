"""Structured errors attached to a simulation run."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorType(str, Enum):
    VOLTAGE_OUT_OF_BOUNDS = "voltage_out_of_bounds"
    CONCENTRATION_OUT_OF_BOUNDS = "concentration_out_of_bounds"
    TEMPERATURE_OUT_OF_BOUNDS = "temperature_out_of_bounds"
    RESISTANCE_NEGATIVE = "resistance_negative"
    NAN_DETECTED = "nan_detected"
    INF_DETECTED = "inf_detected"
    DIVERGENCE = "divergence"
    CONVERGENCE_FAILURE = "convergence_failure"
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    SINGULAR_JACOBIAN = "singular_jacobian"
    CURRENT_LIMIT_EXCEEDED = "current_limit_exceeded"
    PROTOCOL_INFEASIBLE = "protocol_infeasible"
    INCOMPATIBLE_MODEL = "incompatible_model"
    UNRECOGNIZED = "unrecognized"


@dataclass(frozen=True)
class SimulationError:
    """One physical, numerical or constraint problem."""

    error_type: ErrorType
    severity: str
    message: str
    location: str = ""
    value: Optional[float] = None
    bounds: str = ""

    def is_critical(self) -> bool:
        return self.severity == "critical"

    def is_warning(self) -> bool:
        return self.severity == "warning"

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type.value,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "value": self.value,
            "bounds": self.bounds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationError":
        values = data.copy()
        values["error_type"] = ErrorType(values["error_type"])
        return cls(**values)

    def summary(self) -> str:
        message = f"{self.severity.upper()}: {self.message}"
        if self.value is not None and self.bounds:
            message += f" (value={self.value}, bounds={self.bounds})"
        elif self.value is not None:
            message += f" (value={self.value})"
        if self.location:
            message += f" @ {self.location}"
        return message
