"""Agent-facing handler for the single-simulation use case."""

from dataclasses import replace
import time
from typing import Optional

from battery_sim.application.services import (
    ComparisonService,
    SimulationExecutionService,
)
from battery_sim.core.cell import Cell
from battery_sim.core.cell.capabilities import describe_parameter_capability
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import ConstantCurrent, Protocol
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.core.simulation import Simulation
from battery_sim.core.result import Signal
from battery_sim.core.simulation import SimulationBackend
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import SolverConfig


class SimulationToolHandler:
    """Build, execute, present, and record one cell simulation.

    This class belongs to the interface layer: it turns simple agent inputs
    into a domain ``Simulation`` and turns the resulting ``SimulationRun`` into
    a dual JSON/Markdown response. The PyBaMM adapter remains injected through
    the stable ``SimulationBackend`` port.
    """

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_protocol: Protocol,
        default_model: Model,
        default_solver_config: SolverConfig,
    ) -> None:
        self._execution_service = SimulationExecutionService(backend=backend)
        self._session = session
        self._default_protocol = default_protocol
        self._default_model = default_model
        self._default_solver_config = default_solver_config

    def run(
        self,
        preset_name: str,
        current_A: Optional[float] = None,
        duration_s: Optional[float] = None,
        temperature_C: float = 25.0,
        model: Optional[str] = None,
        initial_soc: Optional[float] = None,
        thermal_mode: Optional[str] = None,
        requested_signals: Optional[list[str]] = None,
    ) -> DualFormatResult:
        """Execute the single-simulation agent use case."""
        start_time = time.perf_counter()
        cell = Cell.preset(preset_name)
        protocol = self._resolve_protocol(current_A=current_A, duration_s=duration_s)
        selected_model = self._default_model if model is None else Model.from_value(model)
        solver_config = self._default_solver_config
        if initial_soc is not None:
            solver_config = replace(solver_config, initial_soc=initial_soc)
        simulation = Simulation(
            cell=cell,
            model=selected_model,
            protocol=protocol,
            environment=Environment(
                ambient_temperature_C=temperature_C,
                thermal_model=thermal_mode,
            ),
            solver_config=solver_config,
        )

        run = self._execution_service.execute(simulation)
        metrics = ComparisonService.extract_metrics(run)
        preset_capability = describe_parameter_capability(cell)
        if preset_capability["simulation_fidelity"] != "reference_parameterization":
            metrics["decision_ready"] = False
            metrics["validation_status"] = "exploratory_proxy"
        provenance = {
            "backend": run.metadata.backend_name,
            "backend_version": run.metadata.backend_version,
            "model": run.metadata.model,
            "parameter_set": run.metadata.parameter_set,
            "cell_chemistry": run.metadata.cell_chemistry,
        }
        requested_duration_s = protocol.total_duration_s()
        simulated_duration_s = max(
            (float(series.time_s[-1]) for series in run.result._data.values()),
            default=0.0,
        )
        execution = {
            "requested_duration_s": requested_duration_s,
            "simulated_duration_s": simulated_duration_s,
            "coverage_fraction": (
                min(simulated_duration_s / requested_duration_s, 1.0)
                if requested_duration_s > 0 else None
            ),
            "termination_reason": run.metadata.convergence_reason,
            "solver_success": run.metadata.success,
            "validation_status": metrics["validation_status"],
        }
        signals = self._serialize_signals(run.result, requested_signals)
        json_data = {
            "type": "simulation_result",
            "simulation_id": run.metadata.simulation_id,
            "preset": preset_name,
            "temperature_C": temperature_C,
            "preset_capability": preset_capability,
            "provenance": provenance,
            "execution": execution,
            "signals": signals,
            "metrics": metrics,
        }

        markdown = self._format_markdown(
            preset_name=preset_name,
            temperature_C=temperature_C,
            provenance=provenance,
            metrics=metrics,
        )
        self._session.record_investigation(
            investigation_type="run_simulation",
            parameters={
                "preset": preset_name,
                "current_A": current_A,
                "duration_s": duration_s,
                "temperature_C": temperature_C,
                "model": selected_model.value,
                "initial_soc": solver_config.initial_soc,
                "thermal_mode": thermal_mode,
                "requested_signals": requested_signals,
            },
            result_summary=json_data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - start_time,
            key_findings=[],
        )

        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown,
            interpretation_hints=[
                "Review provenance before interpreting the simulated metrics",
                "Review peak_power_W and efficiency_percent for overall performance",
                "Compare with other presets using compare_presets for context",
            ],
        )

    @staticmethod
    def _serialize_signals(result, requested_signals: Optional[list[str]]) -> dict:
        if requested_signals is None:
            return {}
        output = {}
        missing = []
        available = set(result.available_signals())
        for signal_name in requested_signals:
            signal = Signal(signal_name)
            if signal not in available:
                missing.append(signal_name)
                continue
            series = result.get(signal)
            output[signal_name] = {
                "time_s": list(series.time_s),
                "values": list(series.values),
                "unit": series.unit,
            }
        if missing:
            output["_missing"] = missing
        return output

    def _resolve_protocol(
        self,
        *,
        current_A: Optional[float],
        duration_s: Optional[float],
    ) -> Protocol:
        if current_A is None and duration_s is None:
            return self._default_protocol
        if not self._default_protocol.steps:
            raise ValueError("Default protocol has no step to override")

        default_step = self._default_protocol.steps[0]
        if not isinstance(default_step, ConstantCurrent):
            raise ValueError(
                "current_A/duration_s overrides require a ConstantCurrent default step"
            )
        return Protocol.cc(
            current_A=default_step.current_A if current_A is None else current_A,
            duration_s=default_step.duration_s() if duration_s is None else duration_s,
        )

    @staticmethod
    def _format_markdown(
        *,
        preset_name: str,
        temperature_C: float,
        provenance: dict,
        metrics: dict,
    ) -> str:
        lines = [
            f"# Simulation Result: {preset_name}",
            "",
            f"**Ambient temperature**: {temperature_C}°C",
            (
                "**Provenance**: "
                f"{provenance['backend']} {provenance['backend_version'] or ''}; "
                f"model={provenance['model']}; "
                f"parameters={provenance['parameter_set']}"
            ).rstrip(),
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        for key, value in metrics.items():
            rendered_value = f"{value:.4f}" if isinstance(value, float) else value
            lines.append(f"| {key} | {rendered_value} |")
        return "\n".join(lines)
