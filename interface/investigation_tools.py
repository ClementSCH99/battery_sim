"""Agent-facing comparison and sensitivity investigation handlers."""

import time
from typing import Any, Optional

from battery_sim.core.services import ComparisonService, SensitivityService
from battery_sim.core.cell import Cell
from battery_sim.core.cell_presets import CellPresets
from battery_sim.core.environment import Environment
from battery_sim.core.investigation_tools import BatchSimulationConfig
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.result_formatter import (
    ComparisonFormatter,
    DualFormatResult,
    SensitivityFormatter,
)
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.solver import SolverConfig


class EVAssumptions:
    """Derived packaging heuristics kept separate from PyBaMM outputs."""

    @staticmethod
    def compute(preset_names: list[str]) -> dict[str, dict[str, Any]]:
        metrics: dict[str, dict[str, Any]] = {}
        for preset_name in preset_names:
            preset = CellPresets.get(preset_name)
            packaging_complete = (
                preset.weight_kg > 0
                and preset.volume_L > 0
                and preset.cost_usd > 0
            )
            metrics[preset_name] = {
                "energy_density_Wh_per_kg": (
                    preset.energy_density_Wh_per_kg if packaging_complete else None
                ),
                "energy_density_Wh_per_L": (
                    preset.energy_density_Wh_per_L if packaging_complete else None
                ),
                "cost_per_kWh": preset.cost_per_kWh if packaging_complete else None,
                "max_charge_c_rate": preset.max_charge_c_rate,
                "max_discharge_c_rate": preset.max_discharge_c_rate,
                "cycle_life_cycles": preset.cycle_life_cycles or None,
                "nominal_energy_Wh": preset.nominal_energy_Wh,
                "data_quality": (
                    "illustrative_packaging_assumptions"
                    if packaging_complete
                    else "missing_packaging_data"
                ),
            }
        return metrics

    @staticmethod
    def ragone(preset_names: list[str]) -> dict[str, dict[str, float]]:
        """Return heuristic Ragone coordinates only when mass data exist."""
        ragone_data: dict[str, dict[str, float]] = {}
        for preset_name in preset_names:
            preset = CellPresets.get(preset_name)
            energy_Wh = preset.nominal_energy_Wh
            if preset.weight_kg <= 0 or energy_Wh <= 0:
                continue
            peak_power_W = energy_Wh * preset.max_discharge_c_rate
            ragone_data[preset_name] = {
                "energy_density_Wh_per_kg": preset.energy_density_Wh_per_kg,
                "power_density_W_per_kg": peak_power_W / preset.weight_kg,
            }
        return ragone_data


class InvestigationToolHandler:
    """Run comparison and local sensitivity studies for the agent facade."""

    _TEMPERATURE_VALUES_C = [0.0, 15.0, 25.0, 40.0, 55.0]
    _SUPPORTED_SENSITIVITY_PARAMETERS = {
        "temperature_C",
        "nominal_capacity_Ah",
    }

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_protocol: Protocol,
        default_model: Model,
        default_solver_config: SolverConfig,
        comparison_service: Optional[ComparisonService] = None,
        sensitivity_service: Optional[SensitivityService] = None,
    ) -> None:
        self._backend = backend
        self._session = session
        self._default_protocol = default_protocol
        self._default_model = default_model
        self._default_solver_config = default_solver_config
        self._comparison_service = comparison_service or ComparisonService(backend=backend)
        self._sensitivity_service = sensitivity_service or SensitivityService(backend=backend)

    def compare_presets(
        self,
        preset_names: list[str],
        environment_temp_C: Optional[float] = None,
    ) -> DualFormatResult:
        """Compare simulation outputs and label non-simulated EV assumptions."""
        start_time = time.perf_counter()
        temperature_C = 25.0 if environment_temp_C is None else environment_temp_C
        config = self._batch_config(temperature_C=temperature_C)
        comparison = self._comparison_service.compare_presets(preset_names, config)
        ev_metrics = EVAssumptions.compute(preset_names)
        ragone_data = EVAssumptions.ragone(preset_names) if len(preset_names) >= 2 else {}
        formatted = ComparisonFormatter.format_comparison_with_ev(
            preset_names,
            comparison["metrics"],
            ev_metrics=ev_metrics,
            ragone_data=ragone_data,
        )
        formatted = DualFormatResult(
            json_data={
                **formatted.json_data,
                "evidence": {
                    "metrics": "derived from SimulationRun values",
                    "ev_metrics": "preset packaging assumptions; not PyBaMM outputs",
                    "ragone_data": "derived heuristic; not a simulated pulse-power result",
                },
            },
            markdown_text=formatted.markdown_text + (
                "\n\n> **Evidence note:** electrical metrics come from SimulationRun. "
                "EV packaging and Ragone values are illustrative preset-derived heuristics."
            ),
            interpretation_hints=[
                "Do not treat EV packaging or Ragone heuristics as PyBaMM predictions",
                *formatted.interpretation_hints,
            ],
        )
        self._session.record_investigation(
            investigation_type="compare_presets",
            parameters={
                "presets": preset_names,
                "ambient_temperature_C": temperature_C,
            },
            result_summary=formatted.json_data,
            result_markdown=formatted.markdown_text,
            duration_seconds=time.perf_counter() - start_time,
            key_findings=formatted.interpretation_hints,
        )
        return formatted

    def sensitivity_analysis(
        self,
        preset_name: str,
        parameters: list[str],
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Measure peak-power sensitivity for supported mapped inputs."""
        start_time = time.perf_counter()
        if not parameters:
            raise ValueError("parameters must contain at least one supported parameter")
        unsupported = sorted(
            set(parameters) - self._SUPPORTED_SENSITIVITY_PARAMETERS
        )
        if unsupported:
            supported = ", ".join(sorted(self._SUPPORTED_SENSITIVITY_PARAMETERS))
            raise ValueError(
                f"Unsupported sensitivity parameters: {', '.join(unsupported)}. "
                f"Supported parameters: {supported}."
            )

        baseline_cell = Cell.preset(preset_name)
        ranges = self._parameter_ranges(baseline_cell)
        config = self._batch_config(temperature_C=temperature_C)
        results = []
        for parameter_name in parameters:
            result = self._sensitivity_service.analyze_single_parameter(
                baseline_cell,
                parameter_name,
                ranges[parameter_name],
                config,
                self._extract_peak_power,
            )
            results.append(result)

        formatted = SensitivityFormatter.format_sensitivity(results)
        formatted = DualFormatResult(
            json_data={
                **formatted.json_data,
                "metric": "peak_power_W",
                "baseline_preset": preset_name,
                "baseline_ambient_temperature_C": temperature_C,
                "evidence": (
                    "one-at-a-time local parameter variation; not a global "
                    "sensitivity study"
                ),
            },
            markdown_text=formatted.markdown_text + (
                "\n> **Method note:** one parameter is varied at a time and the "
                "reported response metric is peak power."
            ),
            interpretation_hints=list(formatted.interpretation_hints),
        )
        self._session.record_investigation(
            investigation_type="sensitivity_analysis",
            parameters={
                "preset": preset_name,
                "parameters": parameters,
                "temperature_C": temperature_C,
            },
            result_summary=formatted.json_data,
            result_markdown=formatted.markdown_text,
            duration_seconds=time.perf_counter() - start_time,
            key_findings=formatted.interpretation_hints,
        )
        return formatted

    def _batch_config(self, *, temperature_C: float) -> BatchSimulationConfig:
        return BatchSimulationConfig(
            protocol=self._default_protocol,
            environment=Environment(ambient_temperature_C=temperature_C),
            model=self._default_model,
            solver_config=self._default_solver_config,
            backend=self._backend,
        )

    @classmethod
    def _parameter_ranges(cls, cell: Cell) -> dict[str, list[float]]:
        if cell.nominal_capacity_Ah is None:
            raise ValueError("Sensitivity analysis requires nominal_capacity_Ah")
        return {
            "temperature_C": list(cls._TEMPERATURE_VALUES_C),
            "nominal_capacity_Ah": [
                cell.nominal_capacity_Ah * multiplier
                for multiplier in (0.8, 0.9, 1.0, 1.1, 1.2)
            ],
        }

    @staticmethod
    def _extract_peak_power(run) -> float:
        if run is None:
            return 0.0
        try:
            return float(run.result.peak_power() or 0.0)
        except Exception:
            return 0.0
