"""Comparison of metrics extracted from canonical SimulationRun objects."""

from typing import Any, Optional

from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation import SimulationRun
from battery_sim.application.services.execution import BatchExecutionService


class ComparisonService:
    def __init__(
        self,
        batch_service: Optional[BatchExecutionService] = None,
        backend: Optional[SimulationBackend] = None,
    ) -> None:
        if batch_service is not None:
            self.batch_service = batch_service
        elif backend is not None:
            self.batch_service = BatchExecutionService(backend=backend)
        else:
            raise ValueError("ComparisonService requires either batch_service or backend")

    def compare_presets(
        self,
        preset_names: list[str],
        config: Any,
        metric_filters: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        results = self.batch_service.run_presets(preset_names, config)
        return self.compare_batch_results(results, metric_filters=metric_filters)

    @staticmethod
    def extract_metrics(simulation_run: Optional[SimulationRun]) -> dict[str, Any]:
        if not simulation_run:
            return {"status": "failed", "errors": ["Simulation did not produce a run"]}

        result = simulation_run.result
        metrics: dict[str, Any] = {}
        extractors = {
            "peak_voltage_V": result.peak_voltage,
            "peak_current_A": result.peak_current,
            "peak_power_W": result.peak_power,
            "total_energy_Wh": result.total_energy_Wh,
            "efficiency_percent": result.efficiency,
        }
        for name, extractor in extractors.items():
            try:
                metrics[name] = extractor()
            except Exception:
                metrics[name] = None

        if simulation_run.metadata:
            metrics["solver_time_s"] = simulation_run.metadata.duration_s
            metrics["solver_success"] = simulation_run.metadata.success
        if simulation_run.diagnostics:
            metrics["stiffness"] = (
                "stiff" if simulation_run.diagnostics.is_stiff() else "well-behaved"
            )
            metrics["avg_iterations"] = simulation_run.diagnostics.avg_newton_iterations

        succeeded = simulation_run.is_successful()
        # ``success`` is retained as a compatibility alias, but now has the
        # same meaning as the terminal status. Solver convergence is exposed
        # separately through ``solver_success``.
        metrics["success"] = succeeded
        metrics["status"] = "succeeded" if succeeded else "failed"
        metrics["validation_status"] = "passed" if succeeded else "failed"
        metrics["decision_ready"] = succeeded
        error_messages: list[str] = []
        if simulation_run.errors:
            error_messages = [error.summary() for error in simulation_run.errors]
            metrics["critical_errors"] = sum(
                error.severity == "critical" for error in simulation_run.errors
            )
            metrics["warnings"] = sum(
                error.severity == "warning" for error in simulation_run.errors
            )
        elif not succeeded:
            reason = (
                simulation_run.metadata.convergence_reason
                if simulation_run.metadata
                else "Unknown failure"
            )
            error_messages = [reason]

        if error_messages:
            metrics["errors"] = error_messages
        elif succeeded:
            metrics["critical_errors"] = metrics.get("critical_errors", 0)
            metrics["warnings"] = metrics.get("warnings", 0)
        return metrics

    @classmethod
    def compare_batch_results(
        cls,
        results: list[tuple[str, Optional[SimulationRun]]],
        metric_filters: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        all_metrics = {label: cls.extract_metrics(run) for label, run in results}
        metric_names = set().union(*(metrics.keys() for metrics in all_metrics.values()))
        if metric_filters:
            metric_names.intersection_update(metric_filters)

        comparison: dict[str, Any] = {
            "scenarios": list(all_metrics),
            "metrics": {},
            "n_succeeded": sum(
                metrics.get("status") == "succeeded" for metrics in all_metrics.values()
            ),
            "n_failed": sum(
                metrics.get("status") != "succeeded" for metrics in all_metrics.values()
            ),
        }
        for metric_name in sorted(metric_names):
            values = {label: metrics.get(metric_name) for label, metrics in all_metrics.items()}
            numbers = [
                (label, float(value))
                for label, value in values.items()
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value is not None
            ]
            metric_data: dict[str, Any] = {
                "values": values,
                "type": "numeric" if numbers else "categorical",
            }
            if numbers:
                numeric_values = [value for _, value in numbers]
                metric_data.update(
                    min=min(numeric_values),
                    max=max(numeric_values),
                    range=max(numeric_values) - min(numeric_values),
                )
                baseline = numeric_values[0]
                if baseline != 0:
                    metric_data["relative_to_first"] = {
                        label: (value - baseline) / baseline * 100
                        for label, value in numbers
                    }
            comparison["metrics"][metric_name] = metric_data
        return comparison
