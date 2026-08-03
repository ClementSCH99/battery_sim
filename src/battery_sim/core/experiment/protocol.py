"""Validated sequences of cell-level experiment steps."""

from dataclasses import dataclass
import math
from typing import Optional

from battery_sim.core.exceptions import ProtocolValidationError
from battery_sim.core.experiment.steps import (
    CC_CV,
    ConstantCurrent,
    CycleDefinition,
    DriveProfile,
    PowerStep,
    Rest,
    Step,
)


@dataclass(frozen=True)
class Protocol:
    steps: list[Step]
    n_cycles: Optional[int] = None
    cycle_definition: Optional[CycleDefinition] = None

    def __add__(self, other):
        if not isinstance(other, Protocol):
            return NotImplemented
        return Protocol(self.steps + other.steps)

    def total_duration_s(self) -> float:
        return sum(
            duration
            for step in self.steps
            if (duration := step.duration_s()) is not None
        )

    @staticmethod
    def _validate_duration(
        duration_s: Optional[float],
        step_name: str,
        index: int,
    ) -> None:
        if duration_s is not None and (
            not math.isfinite(duration_s) or duration_s <= 0
        ):
            raise ProtocolValidationError(
                f"{step_name} step at index {index}: "
                "duration must be > 0 s - Protocol not valide"
            )

    @staticmethod
    def _validate_finite(
        value: float,
        field_name: str,
        step_name: str,
        index: int,
    ) -> None:
        if not math.isfinite(value):
            raise ProtocolValidationError(
                f"{step_name} step at index {index}: "
                f"{field_name} must be finite - Protocol not valide"
            )

    def validate(self) -> None:
        if not self.steps:
            raise ProtocolValidationError(
                "Protocol must contain at least one step - Protocol not valide"
            )
        if self.n_cycles is not None and self.n_cycles < 1:
            raise ProtocolValidationError(
                "Protocol n_cycles must be >= 1 - Protocol not valide"
            )

        for index, step in enumerate(self.steps):
            if not isinstance(step, Step):
                raise ProtocolValidationError(
                    f"Invalid step at index {index}: {type(step)} "
                    "- Protocol not valide"
                )
            self._validate_duration(
                step.duration_s(),
                type(step).__name__,
                index,
            )
            if isinstance(step, ConstantCurrent):
                self._validate_finite(
                    step.current_A,
                    "current",
                    "ConstantCurrent",
                    index,
                )
                if step.current_A == 0:
                    raise ProtocolValidationError(
                        f"ConstantCurrent step at index {index}: "
                        "current must be different than 0A - Protocol not valide"
                    )
            elif isinstance(step, PowerStep):
                self._validate_finite(
                    step.power_W,
                    "power",
                    "PowerStep",
                    index,
                )
                if step.power_W == 0:
                    raise ProtocolValidationError(
                        f"PowerStep at index {index}: "
                        "power must be different than 0 W - Protocol not valide"
                    )
            elif isinstance(step, DriveProfile):
                self._validate_drive_profile(step, index)
            elif isinstance(step, CC_CV):
                self._validate_cccv(step, index)

        if self.cycle_definition is not None:
            self._validate_cycle(self.cycle_definition)

    @classmethod
    def _validate_drive_profile(
        cls,
        step: DriveProfile,
        index: int,
    ) -> None:
        for segment_index, (power_w, duration_s) in enumerate(step.segments):
            cls._validate_finite(
                power_w,
                "power",
                f"DriveProfile segment {segment_index}",
                index,
            )
            if not math.isfinite(duration_s) or duration_s <= 0:
                raise ProtocolValidationError(
                    f"DriveProfile at index {index}: segment {segment_index} "
                    "duration must be > 0 s - Protocol not valide"
                )

    @classmethod
    def _validate_cccv(cls, step: CC_CV, index: int) -> None:
        fields = (
            (step.charge_current_A, "charge current"),
            (step.cutoff_voltage_V, "cutoff voltage"),
            (step.taper_current_A, "taper current"),
        )
        for value, label in fields:
            cls._validate_finite(value, label, "CC_CV", index)
            if value <= 0:
                raise ProtocolValidationError(
                    f"CC_CV step at index {index}: {label} "
                    "must be greater than 0 - Protocol not valide"
                )
        if step.taper_current_A > step.charge_current_A:
            raise ProtocolValidationError(
                f"CC_CV step at index {index}: taper current must be "
                "<= charge current - Protocol not valide"
            )

    @staticmethod
    def _validate_cycle(cycle: CycleDefinition) -> None:
        cycle.charge.validate()
        cycle.discharge.validate()
        for label, rest_s in (
            ("rest_after_charge_s", cycle.rest_after_charge_s),
            ("rest_after_discharge_s", cycle.rest_after_discharge_s),
        ):
            if not math.isfinite(rest_s) or rest_s < 0:
                raise ProtocolValidationError(
                    f"CycleDefinition {label} must be >= 0 s "
                    "- Protocol not valide"
                )

    @staticmethod
    def cc(current_A: float, duration_s: float) -> "Protocol":
        return Protocol([ConstantCurrent(current_A, duration_s)])

    @staticmethod
    def power(power_W: float, duration_s: float) -> "Protocol":
        return Protocol([PowerStep(power_W, duration_s)])

    @staticmethod
    def rest(duration_s: float) -> "Protocol":
        return Protocol([Rest(duration_s)])

    @staticmethod
    def cccv(
        charge_current_A: float,
        cutoff_voltage_V: float,
        taper_current_A: float,
    ) -> "Protocol":
        return Protocol(
            [CC_CV(charge_current_A, cutoff_voltage_V, taper_current_A)]
        )

    @staticmethod
    def experiment(steps: list[Step]) -> "Protocol":
        return Protocol(steps)

    @classmethod
    def cycle(
        cls,
        charge: "Protocol",
        discharge: "Protocol",
        n_cycles: int = 1,
        rest_s: float = 600.0,
    ) -> "Protocol":
        if n_cycles < 1:
            raise ProtocolValidationError("n_cycles must be >= 1")
        definition = CycleDefinition(
            charge=charge,
            discharge=discharge,
            rest_after_charge_s=rest_s,
            rest_after_discharge_s=rest_s,
        )
        steps = list(charge.steps)
        if rest_s > 0:
            steps.append(Rest(rest_s))
        steps.extend(discharge.steps)
        if rest_s > 0:
            steps.append(Rest(rest_s))
        return cls(
            steps=steps,
            n_cycles=n_cycles,
            cycle_definition=definition,
        )

    @classmethod
    def drive_cycle(
        cls,
        cycle_name: str,
        vehicle_mass_kg: float = 1800.0,
        peak_power_kW: float = 150.0,
    ) -> "Protocol":
        from battery_sim.experimental.system.drive_cycles import (
            get_drive_cycle,
            scale_drive_cycle,
        )

        profile = get_drive_cycle(cycle_name)
        segments = scale_drive_cycle(
            profile,
            vehicle_mass_kg,
            peak_power_kW,
        )
        return cls(
            steps=[
                DriveProfile(
                    segments=segments,
                    cycle_name=cycle_name,
                )
            ]
        )
