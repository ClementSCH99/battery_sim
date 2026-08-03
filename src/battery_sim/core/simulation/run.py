"""Complete evidence returned by one simulation execution."""

from dataclasses import dataclass
import json

from battery_sim.core.result import Result
from battery_sim.core.simulation.diagnostics import ConvergenceDiagnostics
from battery_sim.core.simulation.errors import SimulationError
from battery_sim.core.simulation.metadata import SimulationMetadata


@dataclass
class SimulationRun:
    """Result payload plus provenance, diagnostics and structured errors."""

    result: Result
    metadata: SimulationMetadata
    errors: list[SimulationError]
    diagnostics: ConvergenceDiagnostics

    def is_successful(self) -> bool:
        return self.metadata.success and not self.has_critical_errors()

    def has_warnings(self) -> bool:
        return any(error.is_warning() for error in self.errors)

    def has_critical_errors(self) -> bool:
        return any(error.is_critical() for error in self.errors)

    def get_critical_errors(self) -> list[SimulationError]:
        return [error for error in self.errors if error.is_critical()]

    def get_warnings(self) -> list[SimulationError]:
        return [error for error in self.errors if error.is_warning()]

    def summary(self) -> str:
        error_lines = (
            [f"  {error.summary()}" for error in self.errors]
            if self.errors
            else ["  No errors detected"]
        )
        return "\n".join(
            [
                "=" * 66,
                "SIMULATION RUN SUMMARY",
                "=" * 66,
                "",
                self.metadata.summary(),
                "",
                self.diagnostics.summary(),
                "",
                "Errors/Warnings:",
                *error_lines,
                "",
                "=" * 66,
            ]
        )

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "errors": [error.to_dict() for error in self.errors],
            "diagnostics": self.diagnostics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, result: Result) -> "SimulationRun":
        return cls(
            result=result,
            metadata=SimulationMetadata.from_dict(data["metadata"]),
            errors=[
                SimulationError.from_dict(error)
                for error in data.get("errors", [])
            ],
            diagnostics=ConvergenceDiagnostics.from_dict(data["diagnostics"]),
        )

    def plot(self, *args, **kwargs):
        from battery_sim.core.result_plotting import plot_result

        return plot_result(self.result, *args, **kwargs)

    def to_file(self, filepath: str, include_metadata: bool = True) -> None:
        with open(filepath, "w") as output:
            json.dump(self.to_dict(), output, indent=2)

    def __getattr__(self, name):
        """Temporary compatibility delegation to the embedded Result."""
        result = object.__getattribute__(self, "result")
        try:
            return getattr(result, name)
        except AttributeError as exc:
            raise AttributeError(
                f"{type(self).__name__!s} has no attribute {name!r}"
            ) from exc


def ensure_simulation_run(obj) -> SimulationRun:
    """Adapt a legacy bare Result while callers migrate to SimulationRun."""
    if isinstance(obj, SimulationRun):
        return obj
    if not isinstance(obj, Result):
        raise TypeError(f"Expected Result or SimulationRun, got {type(obj)}")

    from battery_sim.core.solver import SolverConfig

    return SimulationRun(
        result=obj,
        metadata=SimulationMetadata.create(
            solver_config=SolverConfig(),
            success=True,
            convergence_reason="Unknown (legacy Result)",
        ),
        errors=[],
        diagnostics=ConvergenceDiagnostics(),
    )
