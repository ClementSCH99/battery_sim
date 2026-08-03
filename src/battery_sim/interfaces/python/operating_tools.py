"""Exploratory cell operating-point screens and candidate derating samples."""

import time
from dataclasses import asdict
from typing import Callable, Optional

from battery_sim.core.cell import Cell
from battery_sim.core.operating_window import OperatingWindowAnalyzer
from battery_sim.core.experiment import Model
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession


class OperatingToolHandler:
    """Present voltage-pulse results without claiming safety qualification."""

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_model: Model,
        analyzer_factory: Optional[Callable[..., OperatingWindowAnalyzer]] = None,
    ) -> None:
        self._backend = backend
        self._session = session
        self._default_model = default_model
        self._analyzer_factory = analyzer_factory or OperatingWindowAnalyzer

    def operating_window(self, preset_name: str, grid_size: str = "coarse") -> DualFormatResult:
        started = time.perf_counter()
        cell = Cell.preset(preset_name)
        analyzer = self._analyzer_factory(backend=self._backend, model=self._default_model)
        result = analyzer.analyze(cell=cell, grid_size=grid_size)
        summary = result["summary"]
        points = [asdict(point) for point in result["grid_points"]]
        successful_count = sum(point["simulation_completed"] for point in points)
        json_data = {
            "type": "operating_window",
            "maturity": "experimental",
            "preset": preset_name,
            "grid_size": grid_size,
            "total_points": result["total_points"],
            "successful_points": successful_count,
            "failed_points": result["total_points"] - successful_count,
            "summary": {
                "safe_count": summary.get("safe", 0),
                "caution_count": summary.get("caution", 0),
                "avoid_count": summary.get("avoid", 0),
                "percent_safe": round(summary.get("percent_safe", 0), 1),
                "percent_caution": round(summary.get("percent_caution", 0), 1),
                "percent_avoid": round(summary.get("percent_avoid", 0), 1),
                "max_safe_crate": round(summary.get("max_safe_crate", 0), 2),
                "safe_temperature_range_C": summary.get("safe_temperature_range_C"),
            },
            "grid_points": points,
            "evidence": self._evidence(),
        }
        markdown_lines = [
            f"# Operating Window Screen: {preset_name}",
            "",
            "> **Ce n'est pas une enveloppe de sécurité qualifiée.** Les classes safe/caution/avoid "
            "sont des étiquettes de criblage fondées sur de courtes impulsions de décharge.",
            "",
            "## Summary",
            "",
            "| Classe | Points | Part |",
            "|---|---:|---:|",
            f"| safe | {json_data['summary']['safe_count']} | {json_data['summary']['percent_safe']:.1f} % |",
            f"| caution | {json_data['summary']['caution_count']} | {json_data['summary']['percent_caution']:.1f} % |",
            f"| avoid | {json_data['summary']['avoid_count']} | {json_data['summary']['percent_avoid']:.1f} % |",
            "",
            f"Simulations réussies : {successful_count}/{result['total_points']}.",
            "",
            "## Operating Points",
            "",
            "| SOC | Temp. | C-rate | Zone | V min | V max | Statut |",
            "|---:|---:|---:|---|---:|---:|---|",
        ]
        for point in sorted(points, key=lambda p: (p["c_rate"], p["temperature_C"], p["soc_level"])):
            markdown_lines.append(
                f"| {point['soc_level']:.2f} | {point['temperature_C']:.0f} °C | "
                f"{point['c_rate']:.2f} C | {point['zone']} | "
                f"{self._number(point['voltage_min_V'])} | {self._number(point['voltage_max_V'])} | "
                f"{'ok' if point['simulation_completed'] else 'failed'} |"
            )
        markdown_lines.extend(
            [
                "",
                "Modèle thermique isotherme : la hausse de température, l'emballement thermique, "
                "le placage lithium et les dispersions cellule ne sont pas validés par ce calcul.",
            ]
        )
        markdown = "\n".join(markdown_lines)
        hints = [
            "Treat safe/caution/avoid as screening labels, not certified safety states",
            "Failed simulations are classified avoid and must be investigated",
            "Use measured HPPC/OCV/thermal data before deriving BMS limits",
        ]
        self._record("operating_window", preset_name, json_data, markdown, started, hints)
        return DualFormatResult(json_data, markdown, hints)

    def derating_curves(self, preset_name: str, grid_size: str = "coarse") -> DualFormatResult:
        started = time.perf_counter()
        cell = Cell.preset(preset_name)
        analyzer = self._analyzer_factory(backend=self._backend, model=self._default_model)
        analysis = analyzer.analyze(cell=cell, grid_size=grid_size)
        curves = analyzer.get_derating_curves()
        capacity_Ah = cell.nominal_capacity_Ah
        voltage_V = cell.nominal_voltage_V

        def enrich(points: list[dict]) -> list[dict]:
            enriched = []
            for point in points:
                item = dict(point)
                item["cell_power_W"] = (
                    item["max_c_rate"] * capacity_Ah * voltage_V
                    if capacity_Ah is not None and voltage_V is not None
                    else None
                )
                enriched.append(item)
            return enriched

        temp_curve = enrich(curves["max_crate_vs_temperature"])
        soc_curve = enrich(curves["max_crate_vs_soc"])
        json_data = {
            "type": "derating_curves",
            "maturity": "experimental",
            "preset": preset_name,
            "chemistry": cell.chemistry,
            "nominal_voltage_V": voltage_V,
            "nominal_capacity_Ah": capacity_Ah,
            "grid_size": grid_size,
            "max_crate_vs_temperature": temp_curve,
            "max_crate_vs_soc": soc_curve,
            "source_point_count": analysis["total_points"],
            "evidence": self._evidence(),
        }
        lines = [
            f"# Derating Curves Screen: {preset_name}",
            "",
            "> **Échantillons candidats uniquement :** ces valeurs ne sont pas des tables BMS "
            "prêtes pour la production.",
            "",
            "## Maximum C-rate vs Temperature (SOC 50%)",
            "",
            "| Température | C-rate | Puissance cellule |",
            "|---:|---:|---:|",
        ]
        for point in temp_curve:
            lines.append(
                f"| {point['temperature_C']:.0f} °C | {point['max_c_rate']:.2f} C | "
                f"{self._power(point['cell_power_W'])} |"
            )
        lines.extend(
            [
                "",
                "## Maximum C-rate vs SOC (25 °C)",
                "",
                "| SOC | C-rate | Puissance cellule |",
                "|---:|---:|---:|",
            ]
        )
        for point in soc_curve:
            lines.append(
                f"| {point['soc_level']:.2f} | {point['max_c_rate']:.2f} C | "
                f"{self._power(point['cell_power_W'])} |"
            )
        lines.extend(
            [
                "",
                "La puissance est celle d'une cellule aux valeurs nominales, en watts. "
                "Les pertes, la thermique, les tolérances et la topologie pack ne sont pas modélisées.",
            ]
        )
        markdown = "\n".join(lines)
        hints = [
            "Curves include only grid points classified safe by this voltage-pulse screen",
            "Empty curve regions mean no qualifying simulated point, not zero capability",
            "Validate and interpolate limits using qualified cell and pack test data",
        ]
        self._record("derating_curves", preset_name, json_data, markdown, started, hints)
        return DualFormatResult(json_data, markdown, hints)

    @staticmethod
    def _evidence() -> dict:
        return {
            "observed": "cell voltage response during short discharge pulses",
            "soc_initialization": "SolverConfig.initial_soc set for each grid point",
            "thermal_model": "isothermal; temperature is an ambient boundary condition",
            "not_evaluated": [
                "thermal runaway",
                "lithium plating",
                "cell dispersion",
                "contactor/fuse limits",
                "pack cooling and electrical losses",
            ],
            "validation_status": "not a safety qualification or BMS calibration",
        }

    @staticmethod
    def _number(value) -> str:
        return "—" if value is None else f"{value:.3f} V"

    @staticmethod
    def _power(value) -> str:
        return "—" if value is None else f"{value:.1f} W"

    def _record(self, kind, preset, data, markdown, started, hints) -> None:
        self._session.record_investigation(
            investigation_type=kind,
            parameters={"preset": preset},
            result_summary=data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - started,
            key_findings=hints,
        )
