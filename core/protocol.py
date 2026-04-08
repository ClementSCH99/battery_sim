# battery_sim/core/protocol.py
import math
from dataclasses import dataclass
from battery_sim.core.exceptions import ProtocolValidationError
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from battery_sim.core.drive_cycles import DriveCycleProfile


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
class PowerStep(Step):
    """Step that drives a cell at constant power (watts) for a given duration.
    
    Convention:
    - Positive power (watts) = discharge
    - Negative power (watts) = charge
    """
    power_W: float
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s


@dataclass(frozen=True)
class DriveProfile(Step):
    """Drive profile step: sequence of constant-power segments from a drive cycle.
    
    A drive profile discretizes an EV drive cycle (e.g., WLTP) into a sequence
    of constant-power segments suitable for battery simulation.
    
    Attributes:
        segments: List of (power_W, duration_s) tuples
        cycle_name: Name of the original drive cycle (for logging/traceability)
    """
    segments: list[tuple[float, float]]
    cycle_name: str = "custom"

    def duration_s(self) -> float:
        """Total duration of all segments."""
        return sum(duration for _, duration in self.segments)

    def __post_init__(self):
        """Validate segments."""
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

        if self.n_cycles is not None and self.n_cycles < 1:
            raise ProtocolValidationError("Protocol n_cycles must be >= 1 - Protocol not valide")

        def _validate_duration(duration_s: Optional[float], step_name: str, index: int) -> None:
            if duration_s is None:
                return
            if not math.isfinite(duration_s) or duration_s <= 0:
                raise ProtocolValidationError(
                    f"{step_name} step at index {index}: duration must be > 0 s - Protocol not valide"
                )

        def _validate_finite(value: float, field_name: str, step_name: str, index: int) -> None:
            if not math.isfinite(value):
                raise ProtocolValidationError(
                    f"{step_name} step at index {index}: {field_name} must be finite - Protocol not valide"
                )
        
        for i, step in enumerate(self.steps):
            if not isinstance(step, Step):
                raise ProtocolValidationError(
                    f"Invalid step at index {i}: {type(step)} - Protocol not valide"
                )

            _validate_duration(step.duration_s(), type(step).__name__, i)
        
            if isinstance(step, ConstantCurrent):
                _validate_finite(step.current_A, "current", "ConstantCurrent", i)
                if step.current_A == 0:
                    raise ProtocolValidationError(
                        f"ConstantCurrent step at index {i}: current must be different than 0A - Protocol not valide"
                    )
                
            if isinstance(step, PowerStep):
                _validate_finite(step.power_W, "power", "PowerStep", i)
                if step.power_W == 0:
                    raise ProtocolValidationError(
                        f"PowerStep at index {i}: power must be different than 0 W - Protocol not valide"
                    )
            
            if isinstance(step, DriveProfile):
                if not step.segments:
                    raise ProtocolValidationError(
                        f"DriveProfile at index {i}: must have at least one segment - Protocol not valide"
                    )
                for segment_index, (power_W, duration_s) in enumerate(step.segments):
                    _validate_finite(power_W, "power", f"DriveProfile segment {segment_index}", i)
                    if not math.isfinite(duration_s) or duration_s <= 0:
                        raise ProtocolValidationError(
                            f"DriveProfile at index {i}: segment {segment_index} duration must be > 0 s - Protocol not valide"
                        )
            
            if isinstance(step, CC_CV):
                _validate_finite(step.charge_current_A, "charge current", "CC_CV", i)
                _validate_finite(step.cutoff_voltage_V, "cutoff voltage", "CC_CV", i)
                _validate_finite(step.taper_current_A, "taper current", "CC_CV", i)
                if not step.charge_current_A > 0:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: charge current must be greater than 0A - Protocol not valide"
                    )
                if not step.cutoff_voltage_V > 0:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: cutoff voltage must be greater than 0V - Protocol not valide"
                    )
                if not step.taper_current_A > 0:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: taper current must be greater than 0A - Protocol not valide"
                    )
                if step.taper_current_A > step.charge_current_A:
                    raise ProtocolValidationError(
                        f"CC_CV step at index {i}: taper current must be <= charge current - Protocol not valide"
                    )

        if self.cycle_definition is not None:
            self.cycle_definition.charge.validate()
            self.cycle_definition.discharge.validate()
            for label, rest_s in (
                ("rest_after_charge_s", self.cycle_definition.rest_after_charge_s),
                ("rest_after_discharge_s", self.cycle_definition.rest_after_discharge_s),
            ):
                if not math.isfinite(rest_s) or rest_s < 0:
                    raise ProtocolValidationError(
                        f"CycleDefinition {label} must be >= 0 s - Protocol not valide"
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

    @classmethod
    def drive_cycle(
        cls,
        cycle_name: str,
        vehicle_mass_kg: float = 1800.0,
        peak_power_kW: float = 150.0,
    ) -> "Protocol":
        """Create a drive cycle protocol from a standard EV profile.
        
        Loads a named drive cycle (e.g., "WLTP", "US06"), scales it by vehicle
        parameters, and discretizes into constant-power segments.
        
        Args:
            cycle_name: Drive cycle name (e.g., "WLTP", "US06", "UDDS")
            vehicle_mass_kg: Vehicle mass in kg (default 1800 kg, typical compact car)
            peak_power_kW: Peak available power in kW (default 150 kW, typical EV)
        
        Returns:
            Protocol with DriveProfile step containing power-duration segments
        
        Raises:
            KeyError: If cycle_name not found in drive cycle library
        """
        from battery_sim.core.drive_cycles import get_drive_cycle, scale_drive_cycle
        
        # Load the normalized profile
        profile = get_drive_cycle(cycle_name)
        
        # Scale to vehicle parameters
        segments = scale_drive_cycle(profile, vehicle_mass_kg, peak_power_kW)
        
        # Create DriveProfile step with all segments
        drive_profile = DriveProfile(segments=segments, cycle_name=cycle_name)
        
        return cls(steps=[drive_profile])

