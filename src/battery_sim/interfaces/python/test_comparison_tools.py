"""Agent-facing model-to-test comparison for constant-current discharge."""

import time
import math
from typing import Optional

from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.application.services import (
    ModelTestEvidenceService,
    SimulationExecutionService,
    TraceComparisonService,
)
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import SolverConfig
from battery_sim.validation.test_trace import CellTestTrace


class ModelTestComparisonToolHandler:
    """Execute one CC discharge and compare it with supplied test samples."""

    MAX_SAMPLES = CellTestTrace.MAX_SAMPLES

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_model: Model,
        default_solver_config: SolverConfig,
    ) -> None:
        self._execution = SimulationExecutionService(backend=backend)
        self._comparison = TraceComparisonService()
        self._evidence = ModelTestEvidenceService()
        self._session = session
        self._default_model = default_model
        self._default_solver_config = default_solver_config

    def compare_cc_discharge(
        self,
        *,
        preset_name: str,
        source: str,
        time_s: list[float],
        voltage_V: list[float],
        applied_current_A: float,
        measured_current_A: Optional[list[float]] = None,
        current_sign_convention: str = "discharge_positive",
        temperature_C: float = 25.0,
        test_id: Optional[str] = None,
        voltage_rmse_limit_V: Optional[float] = None,
    ) -> DualFormatResult:
        start = time.perf_counter()
        if not math.isfinite(applied_current_A) or applied_current_A <= 0:
            raise ValueError(
                "applied_current_A must be > 0 for a discharge-positive CC test"
            )
        if len(time_s) > self.MAX_SAMPLES:
            raise ValueError(f"test trace is limited to {self.MAX_SAMPLES} samples")

        trace = CellTestTrace.from_raw(
            source=source,
            test_id=test_id,
            time_s=time_s,
            voltage_V=voltage_V,
            current_A=measured_current_A,
            current_sign_convention=current_sign_convention,
        )
        simulation = Simulation(
            cell=Cell.preset(preset_name),
            model=self._default_model,
            protocol=Protocol.cc(
                current_A=applied_current_A,
                duration_s=trace.duration_s,
            ),
            environment=Environment(ambient_temperature_C=temperature_C),
            solver_config=self._default_solver_config,
        )
        run = self._execution.execute(simulation)
        comparison = self._comparison.compare(run, trace)
        assessment = self._evidence.assess(
            comparison=comparison,
            simulation_successful=run.is_successful(),
            measured_current_supplied=trace.current_A is not None,
            voltage_rmse_limit_V=voltage_rmse_limit_V,
        )
        comparison_data = comparison.to_dict()
        assumptions = [
            "The test is a constant-current cell discharge and positive current means discharge after normalization.",
            "Measured time is shifted so its first sample is t=0 s.",
            "The test initial electrochemical state is assumed to match the parameter set initial state; this is not verified.",
            "Ambient and initial simulated cell temperature are both set to temperature_C.",
            "No parameter fitting or calibration is performed.",
        ]
        json_data = {
            "type": "test_comparison",
            "preset": preset_name,
            "simulation_id": run.metadata.simulation_id,
            "simulation_successful": run.is_successful(),
            "simulation_errors": [error.to_dict() for error in run.errors],
            "simulation_provenance": {
                "backend": run.metadata.backend_name,
                "backend_version": run.metadata.backend_version,
                "model": run.metadata.model,
                "parameter_set": run.metadata.parameter_set,
                "cell_chemistry": run.metadata.cell_chemistry,
            },
            "configuration": {
                "model": self._default_model.value,
                "protocol": "cc_discharge",
                "applied_current_A": applied_current_A,
                "ambient_temperature_C": temperature_C,
                "duration_s": trace.duration_s,
            },
            "test_provenance": trace.provenance(),
            **comparison_data,
            "residual_convention": "simulation_minus_measurement",
            "assumptions": assumptions,
            "evidence": {
                "validation_status": "direct residual comparison; not a calibrated or validated cell model",
                "parameter_fitting_performed": False,
                "initial_state_alignment": "assumed_unverified",
            },
            "assessment": assessment.to_dict(),
        }
        markdown = self._format_markdown(json_data)
        self._session.record_investigation(
            investigation_type="compare_test_data",
            parameters={
                "preset_name": preset_name,
                "source": source,
                "test_id": test_id,
                "sample_count": len(time_s),
                "applied_current_A": applied_current_A,
                "temperature_C": temperature_C,
            },
            result_summary={
                key: json_data[key]
                for key in (
                    "type",
                    "preset",
                    "simulation_id",
                    "simulation_successful",
                    "metrics",
                    "coverage",
                    "evidence",
                    "assessment",
                )
            },
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - start,
            key_findings=[],
        )
        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown,
            interpretation_hints=[
                "Check coverage before interpreting residual metrics",
                "Voltage bias is simulation minus measurement",
                "Do not treat low residuals as validation without independent datasets and initial-state control",
            ],
        )

    @staticmethod
    def _format_markdown(data: dict) -> str:
        metrics = data["metrics"]
        coverage = data["coverage"]
        lines = [
            f"# Model-to-Test Comparison: {data['preset']}",
            "",
            f"**Test source:** {data['test_provenance']['source']}",
            f"**Simulation ID:** {data['simulation_id']}",
            f"**Coverage:** {coverage['status']} ({coverage['test_duration_fraction']:.1%} of test duration)",
            "**Residual convention:** simulation − measurement",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
        for name, value in metrics.items():
            rendered = "N/A" if value is None else f"{value:.6g}"
            lines.append(f"| {name} | {rendered} |")
        if data["warnings"]:
            lines.extend(["", "## Warnings", *[f"- {item}" for item in data["warnings"]]])
        lines.extend(["", "## Scientific limits", *[f"- {item}" for item in data["assumptions"]]])
        lines.extend(
            [
                "",
                "## Evidence assessment",
                f"**Confidence:** {data['assessment']['confidence']}",
                f"**Decision ready:** {data['assessment']['decision_ready']}",
                data["assessment"]["conclusion"],
                "",
                "### Next experiments",
                *[f"- {item}" for item in data["assessment"]["next_experiments"]],
            ]
        )
        return "\n".join(lines)
