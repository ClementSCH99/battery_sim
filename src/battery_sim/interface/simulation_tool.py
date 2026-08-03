"""Agent-facing handler for the single-simulation use case."""

import time
from typing import Optional

from battery_sim.core.services import (
    ComparisonService,
    SimulationExecutionService,
)
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.protocol import ConstantCurrent, Protocol
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.solver import SolverConfig


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
    ) -> DualFormatResult:
        """Execute the single-simulation agent use case."""
        start_time = time.perf_counter()
        cell = Cell.preset(preset_name)
        protocol = self._resolve_protocol(current_A=current_A, duration_s=duration_s)
        simulation = Simulation(
            cell=cell,
            model=self._default_model,
            protocol=protocol,
            environment=Environment(ambient_temperature_C=temperature_C),
            solver_config=self._default_solver_config,
        )

        run = self._execution_service.execute(simulation)
        metrics = ComparisonService.extract_metrics(run)
        provenance = {
            "backend": run.metadata.backend_name,
            "backend_version": run.metadata.backend_version,
            "model": run.metadata.model,
            "parameter_set": run.metadata.parameter_set,
            "cell_chemistry": run.metadata.cell_chemistry,
        }
        json_data = {
            "type": "simulation_result",
            "simulation_id": run.metadata.simulation_id,
            "preset": preset_name,
            "temperature_C": temperature_C,
            "provenance": provenance,
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
