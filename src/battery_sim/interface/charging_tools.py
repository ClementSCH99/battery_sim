"""Experimental charging screens with explicit evidence boundaries."""

import time
from typing import Callable, Optional

import numpy as np

from battery_sim.core.cell import CellPresets
from battery_sim.core.charging_strategies import (
    ChargingStrategyComparison,
    ChargingStrategyEvaluator,
)
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.core.services import SimulationExecutionService
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.core.experiment import SolverConfig


class ChargingToolHandler:
    """Screen charging choices without presenting them as validated optimization."""

    def __init__(
        self,
        *,
        backend: SimulationBackend,
        session: SimulationSession,
        default_model: Model,
        evaluator_factory: Optional[Callable[..., ChargingStrategyEvaluator]] = None,
    ) -> None:
        self._backend = backend
        self._execution = SimulationExecutionService(backend)
        self._session = session
        self._default_model = default_model
        self._evaluator_factory = evaluator_factory or ChargingStrategyEvaluator

    def optimize_charging(
        self,
        preset_name: str,
        charge_current_range_A: tuple[float, float] = (1.0, 10.0),
        n_sweep_points: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Screen single-charge CC-CV duration over an explicit current grid."""
        started = time.perf_counter()
        lower_A, upper_A = charge_current_range_A
        if lower_A <= 0 or upper_A <= 0 or lower_A > upper_A:
            raise ValueError("charge_current_range_A must contain positive min <= max")
        if n_sweep_points < 1:
            raise ValueError("n_sweep_points must be >= 1")

        preset = CellPresets.get(preset_name)
        cell = preset.cell
        capacity_Ah = cell.nominal_capacity_Ah
        if capacity_Ah is None or capacity_Ah <= 0:
            raise ValueError("Charging screening requires nominal cell capacity")
        max_voltage_V = float(cell.metadata.get("max_voltage_v", 4.2))
        max_charge_current_A = preset.max_charge_c_rate * capacity_Ah
        currents = np.linspace(lower_A, upper_A, n_sweep_points)
        rows = []
        for index, current_A in enumerate(currents):
            current_A = float(current_A)
            row = {
                "charge_current_A": current_A,
                "c_rate": current_A / capacity_Ah,
                "charge_time_s": None,
                "capacity_fade_per_cycle": None,
                "score": 1000.0 + index,
                "peak_voltage_V": None,
                "efficiency": None,
                "status": "outside_preset_limit",
                "error": None,
                "diagnostics": [],
            }
            if current_A <= max_charge_current_A + 1e-12:
                simulation = Simulation(
                    cell=cell,
                    model=self._default_model,
                    protocol=Protocol.cccv(
                        charge_current_A=current_A,
                        cutoff_voltage_V=max_voltage_V,
                        taper_current_A=max(current_A * 0.1, 0.01),
                    ),
                    environment=Environment(temperature_C=temperature_C),
                    solver_config=SolverConfig(initial_soc=0.2),
                )
                try:
                    run = self._execution.execute(simulation)
                    errors = [error.summary() for error in run.errors]
                    if not run.is_successful():
                        row["status"] = "failed"
                        row["error"] = "; ".join(errors) or "Simulation unsuccessful"
                    else:
                        voltage = run.result.voltage()
                        if voltage is None or not voltage.time_s:
                            row["status"] = "failed"
                            row["error"] = "No voltage time series returned"
                        else:
                            row["status"] = "ok"
                            row["charge_time_s"] = float(voltage.time_s[-1])
                            row["peak_voltage_V"] = run.result.max_voltage()
                            row["diagnostics"] = errors
                except Exception as exc:
                    row["status"] = "failed"
                    row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)

        successful = [row for row in rows if row["status"] == "ok"]
        if successful:
            longest_s = max(float(row["charge_time_s"]) for row in successful)
            for row in successful:
                row["score"] = float(row["charge_time_s"]) / longest_s if longest_s else 0.0
        rows.sort(key=lambda row: row["score"])
        best = successful and min(successful, key=lambda row: float(row["charge_time_s"]))
        optimal = {
            "charge_current_A": best["charge_current_A"] if best else None,
            "charge_time_min": best["charge_time_s"] / 60.0 if best else None,
            "capacity_fade_per_cycle": None,
            "score": best["score"] if best else None,
        }
        json_data = {
            "type": "charging_optimization",
            "maturity": "experimental",
            "screening_name": "single_charge_cccv_rate_screen",
            "preset": preset_name,
            "temperature_C": temperature_C,
            "optimal_params": optimal,
            "all_results": rows,
            "max_voltage_V": max_voltage_V,
            "preset_max_charge_c_rate": preset.max_charge_c_rate,
            "preset_max_charge_current_A": max_charge_current_A,
            "evidence": {
                "observed": "single simulated CC-CV charge duration and peak cell voltage",
                "not_observed": ["capacity fade", "round-trip efficiency", "lithium plating"],
                "initial_soc": 0.2,
                "thermal_scope": "ambient boundary only; no validated pack thermal model",
                "validation_status": "not validated against cell test data",
            },
        }
        best_text = (
            f"{best['charge_current_A']:.2f} A ({best['charge_time_s'] / 60:.1f} min)"
            if best
            else "aucun point simulé avec succès"
        )
        markdown = "\n".join(
            [
                f"# Charging Optimization / Rate Screen: {preset_name}",
                "",
                "> **Portée :** criblage d'une charge CC-CV unique. Le mot « optimal » "
                "signifie uniquement le point simulé le plus rapide dans la grille admissible.",
                "",
                f"- Température ambiante : {temperature_C:g} °C",
                f"- SOC initial : 20 %",
                f"- Limite du preset : {preset.max_charge_c_rate:g} C ({max_charge_current_A:g} A)",
                f"- Point le plus rapide : {best_text}",
                "",
                "## Comparison Table",
                "",
                "| Courant | C-rate | Durée | V crête | Statut |",
                "|---:|---:|---:|---:|---|",
                *[
                    "| {current:.2f} A | {crate:.2f} C | {duration} | {voltage} | {status} |".format(
                        current=row["charge_current_A"],
                        crate=row["c_rate"],
                        duration=(f"{row['charge_time_s'] / 60:.1f} min" if row["charge_time_s"] is not None else "—"),
                        voltage=(f"{row['peak_voltage_V']:.3f} V" if row["peak_voltage_V"] is not None else "—"),
                        status=row["status"],
                    )
                    for row in rows
                ],
                "",
                "La dégradation, l'efficacité aller-retour et le lithium plating ne sont pas calculés ici.",
            ]
        )
        hints = [
            "Comparer uniquement les lignes status=ok",
            "La limite C-rate provient du preset et doit être remplacée par la fiche cellule qualifiée",
            "Une décision de charge exige des essais cellule, un modèle thermique et des critères de vieillissement validés",
        ]
        self._record("optimize_charging", preset_name, json_data, markdown, started, hints)
        return DualFormatResult(json_data, markdown, hints)

    def compare_strategies(
        self,
        preset_name: str,
        strategies: Optional[list[str]] = None,
        n_cycles: int = 5,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Compare exploratory protocols and exclude failed runs from rankings."""
        started = time.perf_counter()
        if n_cycles < 1:
            raise ValueError("n_cycles must be >= 1")
        cell = CellPresets.get(preset_name).cell
        evaluator = self._evaluator_factory(backend=self._backend, model=self._default_model)
        comparison = evaluator.compare(cell, strategies, n_cycles, temperature_C)
        strategy_rows = [self._strategy_row(metric) for metric in comparison.strategies]
        fastest = comparison.rank_by_speed()
        recommendation = fastest[0].strategy_name if fastest else None
        json_data = {
            "type": "charging_strategy_comparison",
            "maturity": "experimental",
            "preset": preset_name,
            "chemistry": comparison.chemistry,
            "nominal_capacity_Ah": comparison.nominal_capacity_Ah,
            "temperature_C": temperature_C,
            "n_cycles": n_cycles,
            "strategies": strategy_rows,
            "recommended_strategy": recommendation,
            "reason": (
                "Fastest successful simulated protocol; no longevity ranking is supported"
                if recommendation
                else "No successful strategy produced an observed charge duration"
            ),
            "evidence": {
                "timing": "total simulation time split equally between charge and discharge (approximation)",
                "aging": "reported only when a capacity-fade signal is available",
                "failed_runs_excluded_from_rankings": True,
                "validation_status": "not validated against charging test data",
            },
        }
        markdown_lines = [
            f"# Charging Strategy Comparison: {preset_name}",
            "",
            "> **Expérimental :** les échecs sont exclus du classement et aucune conclusion "
            "de longévité n'est tirée sans signal de perte de capacité.",
            "",
            "## Performance Comparison",
            "",
            "| Strategy | Status | Charge Time | Efficiency | Fade/Cycle |",
            "|---|---|---:|---:|---:|",
        ]
        for row in strategy_rows:
            markdown_lines.append(
                f"| {row['strategy_name']} | {row['status']} | "
                f"{self._format(row['charge_time_min'], ' min')} | "
                f"{self._format(row['energy_efficiency'])} | "
                f"{self._format(row['capacity_fade_per_cycle'], ' %')} |"
            )
        markdown_lines.extend(
            [
                "",
                "## Recommendation",
                "",
                recommendation
                if recommendation
                else "Aucune recommandation : aucune durée de charge exploitable n'a été observée.",
                "",
                "Cette comparaison ne constitue ni une calibration BMS ni une validation de durée de vie.",
            ]
        )
        markdown = "\n".join(markdown_lines)
        hints = [
            "Inspect status and error before comparing metrics",
            "Missing metrics are null rather than fabricated zeros",
            "Validate protocols and degradation mechanisms against the intended chemistry",
        ]
        self._record("compare_charging_strategies", preset_name, json_data, markdown, started, hints)
        return DualFormatResult(json_data, markdown, hints)

    @staticmethod
    def _strategy_row(metric) -> dict:
        return {
            "strategy_name": metric.strategy_name,
            "status": metric.status,
            "error": metric.error or None,
            "charge_time_min": metric.charge_time_min if metric.timing_observed else None,
            "discharge_time_min": metric.discharge_time_min if metric.timing_observed else None,
            "total_cycle_time_min": metric.total_cycle_time_min if metric.timing_observed else None,
            "charge_energy_Wh": metric.charge_energy_Wh if metric.energy_observed else None,
            "discharge_energy_Wh": metric.discharge_energy_Wh if metric.energy_observed else None,
            "energy_efficiency": metric.energy_efficiency if metric.energy_observed else None,
            "capacity_fade_per_cycle": metric.capacity_fade_per_cycle if metric.capacity_fade_observed else None,
            "final_soh": metric.final_soh if metric.capacity_fade_observed else None,
            "final_temperature_C": metric.final_temperature_C,
            "notes": metric.notes,
        }

    @staticmethod
    def _format(value, suffix: str = "") -> str:
        return "—" if value is None else f"{value:.2f}{suffix}"

    def _record(self, kind, preset, data, markdown, started, hints) -> None:
        self._session.record_investigation(
            investigation_type=kind,
            parameters={"preset": preset},
            result_summary=data,
            result_markdown=markdown,
            duration_seconds=time.perf_counter() - started,
            key_findings=hints,
        )
