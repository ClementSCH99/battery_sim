"""Atomic protocol steps."""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from battery_sim.core.exceptions import ProtocolValidationError

if TYPE_CHECKING:
    from battery_sim.core.experiment.protocol import Protocol


@dataclass(frozen=True)
class Step:
    def duration_s(self) -> Optional[float]:
        return None


@dataclass(frozen=True)
class ConstantCurrent(Step):
    current_A: float
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s


@dataclass(frozen=True)
class Rest(Step):
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s


@dataclass(frozen=True)
class PowerStep(Step):
    """Constant cell power; positive currently means discharge."""

    power_W: float
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s


@dataclass(frozen=True)
class DriveProfile(Step):
    segments: list[tuple[float, float]]
    cycle_name: str = "custom"

    def duration_s(self) -> float:
        return sum(duration for _, duration in self.segments)

    def __post_init__(self) -> None:
        if not self.segments:
            raise ProtocolValidationError(
                "DriveProfile must have at least one segment"
            )


@dataclass(frozen=True)
class CC_CV(Step):
    charge_current_A: float
    cutoff_voltage_V: float
    taper_current_A: float


@dataclass(frozen=True)
class CycleDefinition:
    charge: "Protocol"
    discharge: "Protocol"
    rest_after_charge_s: float = 600.0
    rest_after_discharge_s: float = 600.0
