"""Comparison ranking, insights and formatting helpers."""

from typing import Any, Dict, List, Optional

from battery_sim.interfaces.presenters.result.model import DualFormatResult

class ComparisonHelpersMixin:
    MINIMIZED_METRICS = {"solver_time_s", "critical_errors", "warnings"}

    @classmethod
    def _higher_is_better(cls, metric_name: str) -> bool:
        return metric_name not in cls.MINIMIZED_METRICS

    @staticmethod
    def _compute_best_for(
        metrics_dict: Dict[str, Any],
        ev_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """
        Compute which preset wins on each metric.

        Returns:
            Dict mapping metric name to winning preset name
        """
        best_for = {}

        # Baseline metrics
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                values = metric_data['values']
                numeric_values = [(s, v) for s, v in values.items() if v is not None]

                if numeric_values:
                    chooser = max if ComparisonHelpersMixin._higher_is_better(metric_name) else min
                    best_val = chooser(numeric_values, key=lambda item: item[1])
                    best_for[metric_name] = best_val[0]

        # EV metrics
        if ev_metrics:
            # Energy density (higher is better)
            energy_density_vals = {
                s: d['energy_density_Wh_per_kg']
                for s, d in ev_metrics.items()
                if d.get('energy_density_Wh_per_kg') is not None
            }
            if energy_density_vals:
                best_for['Gravimetric Energy Density'] = max(energy_density_vals, key=energy_density_vals.get)

            # Volumetric energy density (higher is better)
            volumetric_vals = {
                s: d['energy_density_Wh_per_L']
                for s, d in ev_metrics.items()
                if d.get('energy_density_Wh_per_L') is not None
            }
            if volumetric_vals:
                best_for['Volumetric Energy Density'] = max(volumetric_vals, key=volumetric_vals.get)

            # Cost per kWh (lower is better)
            cost_vals = {
                s: d['cost_per_kWh']
                for s, d in ev_metrics.items()
                if d.get('cost_per_kWh') is not None
            }
            if cost_vals:
                best_for['Cost per kWh'] = min(cost_vals, key=cost_vals.get)

            # Discharge power (higher is better)
            discharge_vals = {
                s: d['max_discharge_c_rate']
                for s, d in ev_metrics.items()
                if d.get('max_discharge_c_rate') is not None
            }
            if discharge_vals:
                best_for['Power Delivery'] = max(discharge_vals, key=discharge_vals.get)

            # Cycle life (higher is better)
            cycle_vals = {
                s: d['cycle_life_cycles']
                for s, d in ev_metrics.items()
                if d.get('cycle_life_cycles') is not None
            }
            if cycle_vals:
                best_for['Cycle Life'] = max(cycle_vals, key=cycle_vals.get)

        return best_for
    @staticmethod
    def _format_optional_number(value: Any, format_spec: str) -> str:
        """Render absent assumption data without turning it into a physical zero."""
        if value is None:
            return "N/A"
        return format(value, format_spec)
    @staticmethod
    def _extract_insights(json_data: Dict[str, Any]) -> List[str]:
        """
        Extract interesting patterns from comparison data.

        TEACHING: This is how we guide the LLM.
        We don't tell it what to think, but we point out patterns.
        """
        insights = []

        for metric_name, metric_data in json_data.get('metrics', {}).items():
            if 'best' in metric_data and 'range' in metric_data:
                best = metric_data['best']
                best_val = metric_data['best_value']
                range_val = metric_data['range']
                worst_val = metric_data['worst_value']

                if worst_val != 0:
                    ratio = best_val / worst_val
                    if ratio > 1.5:
                        insights.append(
                            f"**{best}** significantly outperforms on {metric_name}: "
                            f"{best_val:.1f} ({ratio:.1f}x better)"
                        )
                    elif range_val > 20:  # Arbitrary threshold for "big difference"
                        insights.append(
                            f"Significant variation in {metric_name} across scenarios "
                            f"(range: {range_val:.1f})"
                        )

        return insights
    @staticmethod
    def _format_categorical_value(value: Any) -> str:
        """Format categorical values for markdown display."""
        if value is None:
            return "-"
        if isinstance(value, list):
            if not value:
                return "[]"
            return ", ".join(str(v) for v in value)
        return str(value)
    @staticmethod
    def _generate_hints(json_data: Dict[str, Any]) -> List[str]:
        """
        Generate interpretation hints.

        TEACHING: Hints guide reasoning without prescribing.
        """
        hints = []

        metrics = json_data.get('metrics', {})

        # Hint 1: What metric shows the biggest spread?
        max_range = 0
        max_metric = None
        for metric, data in metrics.items():
            if 'range' in data and data['range']:
                if data['range'] > max_range:
                    max_range = data['range']
                    max_metric = metric

        if max_metric:
            hints.append(f"Largest variation is in {max_metric} (range: {max_range:.1f})")

        # Hint 2: Trade-offs
        if len(metrics) > 1:
            hints.append("Different scenarios excel at different metrics - consider trade-offs")

        return hints
