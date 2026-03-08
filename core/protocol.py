# battery_sim/core/protocol.py
from dataclasses import dataclass
from battery_sim.core.exceptions import ProtocolValidationError
from typing import List, Optional


@dataclass(frozen=True)
class Step:
    def to_pybamm(self) -> list[str]:
        raise NotImplementedError
    pass

    def duration_s(self) -> Optional[float]:
        """
        Returns duration in second if fixed, None otherwise.
        """
        return None

@dataclass(frozen=True)
class ConstantCurrent(Step):
    current_A: float
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s

    def to_pybamm(self) -> List[str]:
        """
        Charge: current < 0
        Discharge: current > 0
        """
        if self.current_A > 0:
            return [f"Discharge at {self.current_A} A for {self._duration_s} seconds"]
        else:
            return [f"Charge at {abs(self.current_A)} A for {self._duration_s} seconds"]


@dataclass(frozen=True)
class Rest(Step):
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s
    
    def to_pybamm(self) -> List[str]:
        return [f"Rest for {self._duration_s} seconds"]


@dataclass(frozen=True)
class CC_CV(Step):
    charge_current_A: float
    cutoff_voltage_V: float
    taper_current_A: float

    def to_pybamm(self) -> List[str]:
        CC = f"Charge at {self.charge_current_A} A until {self.cutoff_voltage_V} V"
        CV = f"Hold at {self.cutoff_voltage_V} V until {self.taper_current_A} A"
        return [CC,CV]


@dataclass(frozen=True)
class Protocol:
    steps: List[Step]

    def __add__(self, other):
        if not isinstance(other, Protocol):
            return NotImplemented
        return Protocol(self.steps + other.steps)
    
    def total_duration_s(self) -> float:
        total: float = 0.0

        for step in self.steps:
            duration = step.duration_s()
            if duration is None:
                continue
            total += duration
        
        return total
    
    def validate(self) -> None:
        if not self.steps:
            raise ProtocolValidationError(
                "Protocol must contain at least one step - Protocol not valide"
            )
        
        for i, step in enumerate(self.steps):
            if not isinstance(step, Step):
                raise ProtocolValidationError(
                    f"Invalid step at index {i}: {type(step)} - Protocol not valide"
                )
        
            if isinstance(step, ConstantCurrent):
                if not step.current_A != 0:
                    raise ProtocolValidationError(
                        f"ConstantCurrent step at index {i}: current must be different than 0A - Protocol not valide"
                    )
                
            if isinstance(step, CC_CV):
                if not step.charge_current_A > 0:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: charge current must be greater than 0A - Protocol not valide"
                    )
                if not step.cutoff_voltage_V:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: cutoff voltage must exist - Protocol not valide"
                    )
                if not step.taper_current_A > 0:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: taper current must be greater than 0A - Protocol not valide"
                    )

        # TO-DO: check for nul current, negative tension, CC_CV order ...
        else:
            pass


    @staticmethod
    def cc(current_A: float, duration_s: float) -> "Protocol":
        return Protocol([ConstantCurrent(current_A, duration_s)])

    @staticmethod
    def rest(duration_s: float) -> "Protocol":
        return Protocol([Rest(duration_s)])

    @staticmethod
    def cccv(charge_current_A: float, cutoff_voltage_V: float, taper_current_A: float) -> "Protocol":
        return Protocol([CC_CV(charge_current_A, cutoff_voltage_V, taper_current_A)])

    @staticmethod
    def experiment(steps: List[Step]) -> "Protocol":
        return Protocol(steps)
