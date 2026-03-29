from dataclasses import dataclass
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from battery_sim.core.cell import Cell
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.types.signal import Signal


class SimulationExecutionService:
    def __init__(self, backend: SimulationBackend) -> None:
        self.backend = backend

    def execute(self, simulation: Simulation) -> SimulationRun:
        return simulation.run(self.backend)


class BatchExecutionService:
    def __init__(
        self,
        execution_service: Optional[SimulationExecutionService] = None,
        backend: Optional[SimulationBackend] = None,
    ) -> None:
        if execution_service is not None:
            self.execution_service = execution_service
        elif backend is not None:
            self.execution_service = SimulationExecutionService(backend)
        else:
            raise ValueError("BatchExecutionService requires either execution_service or backend")

    def run_presets(
        self,
        preset_names: List[str],
        config: Any,
    ) -> List[Tuple[str, Optional[SimulationRun]]]:
        results: List[Tuple[str, Optional[SimulationRun]]] = []

        for preset_name in preset_names:
            cell = Cell.preset(preset_name)
            simulation = Simulation(
                cell=cell,
                model=config.model,
                protocol=config.protocol,
                environment=config.environment,
                solver_config=config.solver_config,
            )

            try:
                run = self.execution_service.execute(simulation)
                results.append((preset_name, run))
            except Exception:
                results.append((preset_name, None))

        return results

    def run_parameter_variations(
        self,
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: List[Any],
        config: Any,
    ) -> List[Tuple[Any, Optional[SimulationRun]]]:
        sweep_service = ParameterSweepService(self.execution_service)
        baseline_simulation = Simulation(
            cell=baseline_cell,
            model=config.model,
            protocol=config.protocol,
            environment=config.environment,
            solver_config=config.solver_config,
        )
        target = "environment" if parameter_name == "temperature_C" else "cell"
        results = sweep_service.sweep_parameter(
            baseline_simulation,
            target,
            parameter_name,
            parameter_values,
            continue_on_error=True,
        )
        return [(value, run) for value, run, _, _ in results]


class ParameterSweepService:
    def __init__(
        self,
        execution_service: Optional[SimulationExecutionService] = None,
    ) -> None:
        self.execution_service = execution_service or SimulationExecutionService()

    def sweep_parameter(
        self,
        baseline_simulation: Simulation,
        target: str,
        parameter_name: str,
        values: List[Any],
        continue_on_error: bool = False,
    ) -> List[Tuple[Any, Optional[SimulationRun], Dict[str, Any], Dict[str, Any]]]:
        results: List[Tuple[Any, Optional[SimulationRun], Dict[str, Any], Dict[str, Any]]] = []

        for value in values:
            modified_cell = baseline_simulation.cell
            modified_env = baseline_simulation.environment

            if target == "cell":
                modified_cell = replace(baseline_simulation.cell, **{parameter_name: value})
                cell_overrides = {parameter_name: value}
                env_overrides: Dict[str, Any] = {}
            elif target == "environment":
                modified_env = replace(baseline_simulation.environment, **{parameter_name: value})
                cell_overrides = {}
                env_overrides = {parameter_name: value}
            else:
                raise ValueError(f"Unsupported sweep target: {target}")

            modified_simulation = replace(
                baseline_simulation,
                cell=modified_cell,
                environment=modified_env,
            )

            try:
                run = self.execution_service.execute(modified_simulation)
            except Exception:
                if not continue_on_error:
                    raise
                run = None

            results.append((value, run, cell_overrides, env_overrides))

        return results

    def multi_parameter_sweep(
        self,
        baseline_simulation: Simulation,
        parameters: Dict[str, List[Any]],
    ) -> List[Tuple[Dict[str, Any], SimulationRun, Dict[str, Any], Dict[str, Any]]]:
        cell_params: Dict[str, List[Any]] = {}
        env_params: Dict[str, List[Any]] = {}

        for param_name, values in parameters.items():
            if param_name.startswith("cell::"):
                cell_params[param_name[6:]] = values
            elif param_name.startswith("environment::"):
                env_params[param_name[13:]] = values
            else:
                raise ValueError(
                    f"Parameter {param_name} must start with 'cell::' or 'environment::'"
                )

        def generate_combinations(param_dict: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
            if not param_dict:
                return [{}]

            items = list(param_dict.items())
            first_name, first_values = items[0]
            rest = {key: value for key, value in items[1:]}
            rest_combos = generate_combinations(rest)

            combos = []
            for value in first_values:
                for combo in rest_combos:
                    combos.append({first_name: value, **combo})
            return combos

        results: List[Tuple[Dict[str, Any], SimulationRun, Dict[str, Any], Dict[str, Any]]] = []
        cell_combos = generate_combinations(cell_params)
        env_combos = generate_combinations(env_params)

        for cell_combo in cell_combos:
            for env_combo in env_combos:
                modified_cell = (
                    replace(baseline_simulation.cell, **cell_combo)
                    if cell_combo else baseline_simulation.cell
                )
                modified_env = (
                    replace(baseline_simulation.environment, **env_combo)
                    if env_combo else baseline_simulation.environment
                )
                modified_simulation = replace(
                    baseline_simulation,
                    cell=modified_cell,
                    environment=modified_env,
                )
                run = self.execution_service.execute(modified_simulation)
                results.append(({**cell_combo, **env_combo}, run, cell_combo, env_combo))

        return results


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
        preset_names: List[str],
        config: Any,
        metric_filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        results = self.batch_service.run_presets(preset_names, config)
        return self.compare_batch_results(results, metric_filters=metric_filters)

    @staticmethod
    def extract_metrics(
        simulation_run: Optional[SimulationRun],
    ) -> Dict[str, Any]:
        if not simulation_run:
            return {}

        result = simulation_run.result
        metrics: Dict[str, Any] = {}

        try:
            metrics["peak_voltage_V"] = result.peak_voltage()
        except Exception:
            metrics["peak_voltage_V"] = None

        try:
            metrics["peak_current_A"] = result.peak_current()
        except Exception:
            metrics["peak_current_A"] = None

        try:
            metrics["peak_power_W"] = result.peak_power()
        except Exception:
            metrics["peak_power_W"] = None

        try:
            metrics["total_energy_Wh"] = result.total_energy_Wh()
        except Exception:
            metrics["total_energy_Wh"] = None

        try:
            metrics["efficiency_percent"] = result.efficiency()
        except Exception:
            metrics["efficiency_percent"] = None

        if simulation_run.metadata:
            metrics["solver_time_s"] = simulation_run.metadata.duration_s
            metrics["success"] = simulation_run.metadata.success

        if simulation_run.diagnostics:
            metrics["stiffness"] = (
                "stiff" if simulation_run.diagnostics.is_stiff() else "well-behaved"
            )
            metrics["avg_iterations"] = simulation_run.diagnostics.avg_newton_iterations

        if simulation_run.errors:
            critical = len([e for e in simulation_run.errors if e.severity == "critical"])
            warnings = len([e for e in simulation_run.errors if e.severity == "warning"])
            metrics["critical_errors"] = critical
            metrics["warnings"] = warnings
        else:
            metrics["critical_errors"] = 0
            metrics["warnings"] = 0

        return metrics

    @classmethod
    def compare_batch_results(
        cls,
        results: List[Tuple[str, Optional[SimulationRun]]],
        metric_filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        all_metrics: Dict[str, Dict[str, Any]] = {}
        for label, run in results:
            all_metrics[label] = cls.extract_metrics(run)

        common_metrics = set()
        for metrics in all_metrics.values():
            common_metrics.update(metrics.keys())

        if metric_filters:
            common_metrics = common_metrics.intersection(set(metric_filters))

        comparison: Dict[str, Any] = {
            "scenarios": list(all_metrics.keys()),
            "metrics": {},
        }

        for metric_name in sorted(common_metrics):
            values: Dict[str, Any] = {}
            numbers: List[Tuple[str, float]] = []

            for label, metrics in all_metrics.items():
                value = metrics.get(metric_name)
                values[label] = value
                if isinstance(value, (int, float)) and value is not None:
                    numbers.append((label, float(value)))

            metric_data: Dict[str, Any] = {
                "values": values,
                "type": "numeric" if numbers else "categorical",
            }

            if numbers:
                numeric_values = [value for _, value in numbers]
                metric_data["min"] = min(numeric_values)
                metric_data["max"] = max(numeric_values)
                metric_data["range"] = metric_data["max"] - metric_data["min"]

                baseline = numeric_values[0]
                if baseline != 0:
                    metric_data["relative_to_first"] = {
                        label: ((value - baseline) / baseline * 100)
                        for label, value in numbers
                    }

            comparison["metrics"][metric_name] = metric_data

        return comparison


@dataclass(frozen=True)
class SensitivityResult:
    parameter_name: str
    parameter_values: List[float]
    metric_name: str
    metric_values: List[Optional[float]]
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    range_value: Optional[float] = None
    sensitivity_coefficient: Optional[float] = None

    def interpretation(self) -> str:
        if self.sensitivity_coefficient is None:
            return "Could not compute sensitivity (insufficient data)"
        if self.sensitivity_coefficient < 1:
            return "VERY LOW sensitivity - parameter barely affects result"
        if self.sensitivity_coefficient < 5:
            return "LOW sensitivity - small impact"
        if self.sensitivity_coefficient < 20:
            return "MODERATE sensitivity - meaningful impact"
        if self.sensitivity_coefficient < 50:
            return "HIGH sensitivity - significant impact"
        return "VERY HIGH sensitivity - dramatic impact"


class SensitivityService:
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
            raise ValueError("SensitivityService requires either batch_service or backend")

    def analyze_single_parameter(
        self,
        baseline_cell: Cell,
        parameter_name: str,
        parameter_values: List[float],
        config: Any,
        metric_extractor: Callable[[SimulationRun], float],
    ) -> SensitivityResult:
        sweep_service = ParameterSweepService(self.batch_service.execution_service)
        baseline_simulation = Simulation(
            cell=baseline_cell,
            model=config.model,
            protocol=config.protocol,
            environment=config.environment,
            solver_config=config.solver_config,
        )
        target = "environment" if parameter_name == "temperature_C" else "cell"
        results = sweep_service.sweep_parameter(
            baseline_simulation,
            target,
            parameter_name,
            parameter_values,
            continue_on_error=True,
        )

        metric_values: List[Optional[float]] = []
        valid_values: List[float] = []

        for _, run, _, _ in results:
            if run:
                try:
                    metric = metric_extractor(run)
                    metric_values.append(metric)
                    if metric is not None:
                        valid_values.append(metric)
                except Exception:
                    metric_values.append(None)
            else:
                metric_values.append(None)

        sensitivity_coeff = None
        min_val = None
        max_val = None
        range_val = None

        if valid_values:
            min_val = min(valid_values)
            max_val = max(valid_values)
            range_val = max_val - min_val
            if valid_values[0] != 0:
                sensitivity_coeff = (range_val / abs(valid_values[0])) * 100

        return SensitivityResult(
            parameter_name=parameter_name,
            parameter_values=parameter_values,
            metric_name=metric_extractor.__name__,
            metric_values=metric_values,
            min_value=min_val,
            max_value=max_val,
            range_value=range_val,
            sensitivity_coefficient=sensitivity_coeff,
        )


class CyclingAnalyzer:
    """Extract cycling performance trends from multi-cycle SimulationRuns."""

    @staticmethod
    def capacity_fade_rate(run: SimulationRun) -> Optional[float]:
        """Capacity fade per cycle (Ah/cycle) from linear fit.

        Returns None if cycling signals are unavailable or there are fewer
        than 2 data points.
        """
        ts = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        if ts is None or len(ts.values) < 2:
            return None
        import numpy as _np
        cycles = _np.array(ts.time_s)
        caps = _np.array(ts.values)
        coeffs = _np.polyfit(cycles, caps, 1)
        return float(coeffs[0])  # slope = Ah per cycle

    @staticmethod
    def end_of_life_prediction(run: SimulationRun, eol_threshold: float = 0.8) -> Optional[int]:
        """Predict cycle number where capacity drops below *eol_threshold* of initial.

        Returns None if cycling data is unavailable or capacity is not declining.
        """
        ts = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        if ts is None or len(ts.values) < 2:
            return None
        import numpy as _np
        cycles = _np.array(ts.time_s)
        caps = _np.array(ts.values)
        coeffs = _np.polyfit(cycles, caps, 1)
        slope, intercept = coeffs
        if slope >= 0:
            return None  # capacity not declining
        threshold_cap = caps[0] * eol_threshold
        # slope*n + intercept = threshold_cap  =>  n = (threshold_cap - intercept) / slope
        eol_cycle = (threshold_cap - intercept) / slope
        return max(int(_np.ceil(eol_cycle)), 1)

    @staticmethod
    def cycling_summary(run: SimulationRun) -> Dict[str, Any]:
        """Per-cycle summary: capacity, efficiency, retention.

        Returns a dict with lists keyed by metric name, or an empty dict if
        cycling signals are missing.
        """
        summary: Dict[str, Any] = {}
        for sig, key in [
            (Signal.CYCLE_DISCHARGE_CAPACITY, "discharge_capacity_Ah"),
            (Signal.CYCLE_CHARGE_CAPACITY, "charge_capacity_Ah"),
            (Signal.CYCLE_COULOMBIC_EFFICIENCY, "coulombic_efficiency_pct"),
            (Signal.CYCLE_CAPACITY_RETENTION, "capacity_retention_pct"),
        ]:
            ts = run.result._data.get(sig)
            if ts is not None:
                summary[key] = ts.values
        return summary
