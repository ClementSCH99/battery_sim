"""Canonical cell-test trace used for model-to-measurement comparison."""

from dataclasses import dataclass, field
import math
from typing import Any, ClassVar, Optional


@dataclass(frozen=True)
class CellTestTrace:
    """Validated electrical trace with canonical discharge-positive current."""

    MAX_SAMPLES: ClassVar[int] = 2000

    source: str
    time_s: tuple[float, ...]
    voltage_V: tuple[float, ...]
    current_A: Optional[tuple[float, ...]] = None
    test_id: Optional[str] = None
    supplied_current_sign_convention: str = "discharge_positive"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(
        cls,
        *,
        source: str,
        time_s: list[float],
        voltage_V: list[float],
        current_A: Optional[list[float]] = None,
        current_sign_convention: str = "discharge_positive",
        test_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "CellTestTrace":
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must identify the origin of the test data")
        if current_sign_convention not in {"discharge_positive", "discharge_negative"}:
            raise ValueError(
                "current_sign_convention must be discharge_positive or discharge_negative"
            )
        normalized_current = None
        if current_A is not None:
            sign = 1.0 if current_sign_convention == "discharge_positive" else -1.0
            normalized_current = tuple(sign * float(value) for value in current_A)
        trace = cls(
            source=source.strip(),
            test_id=test_id,
            time_s=tuple(float(value) for value in time_s),
            voltage_V=tuple(float(value) for value in voltage_V),
            current_A=normalized_current,
            supplied_current_sign_convention=current_sign_convention,
            metadata=dict(metadata or {}),
        )
        trace.validate()
        return trace

    def validate(self) -> None:
        if len(self.time_s) < 2:
            raise ValueError("test trace must contain at least two samples")
        if len(self.time_s) > self.MAX_SAMPLES:
            raise ValueError(f"test trace is limited to {self.MAX_SAMPLES} samples")
        if len(self.voltage_V) != len(self.time_s):
            raise ValueError("time_s and voltage_V must have the same length")
        if self.current_A is not None and len(self.current_A) != len(self.time_s):
            raise ValueError("current_A and time_s must have the same length")
        arrays = [self.time_s, self.voltage_V]
        if self.current_A is not None:
            arrays.append(self.current_A)
        if any(not math.isfinite(value) for values in arrays for value in values):
            raise ValueError("test trace values must all be finite")
        if self.time_s[0] < 0:
            raise ValueError("time_s must be non-negative")
        if any(later <= earlier for earlier, later in zip(self.time_s, self.time_s[1:])):
            raise ValueError("time_s must be strictly increasing")
        if any(voltage <= 0 for voltage in self.voltage_V):
            raise ValueError("voltage_V values must be > 0")

    @property
    def elapsed_time_s(self) -> tuple[float, ...]:
        start = self.time_s[0]
        return tuple(value - start for value in self.time_s)

    @property
    def duration_s(self) -> float:
        return self.time_s[-1] - self.time_s[0]

    def provenance(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "test_id": self.test_id,
            "sample_count": len(self.time_s),
            "time_unit": "s",
            "voltage_unit": "V",
            "current_unit": "A" if self.current_A is not None else None,
            "canonical_current_sign": "positive=discharge",
            "supplied_current_sign_convention": self.supplied_current_sign_convention,
            "time_origin_normalized": self.time_s[0] != 0.0,
            "metadata": self.metadata,
        }
