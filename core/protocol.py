# battery_sim/core/protocol.py
from dataclasses import dataclass
from battery_sim.core.exceptions import ProtocolValidationError
from typing import List, Optional


@dataclass(frozen=True)
class Step:

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


@dataclass(frozen=True)
class Rest(Step):
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s


@dataclass(frozen=True)
class CC_CV(Step):
    charge_current_A: float
    cutoff_voltage_V: float
    taper_current_A: float


@dataclass(frozen=True)
class CycleDefinition:
    """One charge-discharge cycle definition."""
    charge: "Protocol"
    discharge: "Protocol"
    rest_after_charge_s: float = 600.0
    rest_after_discharge_s: float = 600.0


@dataclass(frozen=True)
class Protocol:
    """Ordered sequence of electrochemical steps to apply to a cell.

    Factories: ``cc()``, ``rest()``, ``cccv()``, ``cycle()``, ``experiment()``.
    Protocols can be combined with ``+`` to create multi-step sequences.
    """

    steps: List[Step]
    n_cycles: Optional[int] = None
    cycle_definition: Optional[CycleDefinition] = None

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
                if step.current_A == 0:
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

    @classmethod
    def cycle(
        cls,
        charge: "Protocol",
        discharge: "Protocol",
        n_cycles: int = 1,
        rest_s: float = 600.0,
    ) -> "Protocol":
        """Create a cycling protocol: (charge + rest + discharge + rest) x n_cycles.

        The cycle structure is preserved as metadata so the backend can use
        native cycle support (e.g. PyBaMM experiment repetition).
        """
        if n_cycles < 1:
            raise ProtocolValidationError("n_cycles must be >= 1")
        cycle_def = CycleDefinition(
            charge=charge,
            discharge=discharge,
            rest_after_charge_s=rest_s,
            rest_after_discharge_s=rest_s,
        )
        # Build flat steps for one cycle (used as fallback / duration estimation)
        one_cycle_steps: List[Step] = list(charge.steps)
        if rest_s > 0:
            one_cycle_steps.append(Rest(rest_s))
        one_cycle_steps.extend(discharge.steps)
        if rest_s > 0:
            one_cycle_steps.append(Rest(rest_s))
        return cls(
            steps=one_cycle_steps,
            n_cycles=n_cycles,
            cycle_definition=cycle_def,
        )
