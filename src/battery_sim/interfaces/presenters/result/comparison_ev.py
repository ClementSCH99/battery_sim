"""EV-oriented comparison formatting."""

from typing import Any, Dict, List, Optional

from battery_sim.interfaces.presenters.result.model import DualFormatResult
from battery_sim.interfaces.presenters.result.comparison_helpers import ComparisonHelpersMixin

class ComparisonEVMixin:
    @staticmethod
    def format_comparison_with_ev(
        scenarios: List[str],
        metrics_dict: Dict[str, Any],
        ev_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
        ragone_data: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> DualFormatResult:
        """
        Format comparison with EV-specific metrics and Ragone data.

        TEACHING: This enhanced formatter adds:
        1. EV-relevant metrics (energy density, cost/kWh, C-rates)
        2. Ragone plot data (power vs energy trade-off)
        3. Best-for analysis: which preset wins on which metric

        Args:
            scenarios: List of scenario/preset names
            metrics_dict: Dict of simulation metrics
            ev_metrics: EV-specific metrics (gravimetric, volumetric density, cost, C-rates)
            ragone_data: Power-energy trade-off data

        Returns:
            DualFormatResult with comprehensive comparison
        """

        # Build JSON structure
        json_data = {
            'type': 'comparison_with_ev_metrics',
            'scenarios': scenarios,
            'metrics': {},
            'ev_metrics': ev_metrics or {},
            'ragone_data': ragone_data or {},
        }

        # Analyze baseline metrics
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                values = metric_data['values']
                numeric_values = [v for v in values.values() if v is not None]

                if numeric_values:
                    best_val = max(numeric_values) if metric_name not in ['solver_time_s'] else min(numeric_values)
                    best_scenario = [s for s, v in values.items() if v == best_val][0]

                    worst_val = min(numeric_values) if metric_name not in ['solver_time_s'] else max(numeric_values)
                    worst_scenario = [s for s, v in values.items() if v == worst_val][0]

                    json_data['metrics'][metric_name] = {
                        'type': 'numeric',
                        'values': values,
                        'best': best_scenario,
                        'best_value': best_val,
                        'worst': worst_scenario,
                        'worst_value': worst_val,
                        'range': metric_data.get('range'),
                    }
            else:
                json_data['metrics'][metric_name] = {
                    'type': metric_data.get('type', 'categorical'),
                    'values': metric_data.get('values', {}),
                    'categories': metric_data.get('categories', {}),
                }

        # Compute "best_for" winners across all metrics
        best_for = ComparisonHelpersMixin._compute_best_for(metrics_dict, ev_metrics)
        json_data['best_for'] = best_for

        # Build Markdown output
        md_lines = [
            "## Comparison Results: Cell Presets with EV Metrics",
            "",
            f"Scenarios compared: {', '.join(f'**{s}**' for s in scenarios)}",
            "",
        ]

        # EV Metrics Table
        if ev_metrics:
            md_lines.extend([
                "### EV-Specific Metrics",
                "",
                "| Metric | " + " | ".join(scenarios) + " |",
                "|" + "|".join(["-" * 30] * (len(scenarios) + 1)) + "|",
            ])

            # Gravimetric energy density
            row = "| Gravimetric Energy Density (Wh/kg) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('energy_density_Wh_per_kg')
                row += f" {ComparisonHelpersMixin._format_optional_number(val, '.1f')} |"
            md_lines.append(row)

            # Volumetric energy density
            row = "| Volumetric Energy Density (Wh/L) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('energy_density_Wh_per_L')
                row += f" {ComparisonHelpersMixin._format_optional_number(val, '.1f')} |"
            md_lines.append(row)

            # Cost per kWh
            row = "| Cost per kWh ($/kWh) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('cost_per_kWh')
                formatted = ComparisonHelpersMixin._format_optional_number(val, '.2f')
                row += f" {'$' + formatted if val is not None else formatted} |"
            md_lines.append(row)

            # Max charge C-rate
            row = "| Max Charge C-Rate |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('max_charge_c_rate')
                formatted = ComparisonHelpersMixin._format_optional_number(val, '.1f')
                row += f" {formatted + 'C' if val is not None else formatted} |"
            md_lines.append(row)

            # Max discharge C-rate
            row = "| Max Discharge C-Rate |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('max_discharge_c_rate')
                formatted = ComparisonHelpersMixin._format_optional_number(val, '.1f')
                row += f" {formatted + 'C' if val is not None else formatted} |"
            md_lines.append(row)

            # Cycle life
            row = "| Cycle Life (cycles) |"
            for scenario in scenarios:
                val = ev_metrics.get(scenario, {}).get('cycle_life_cycles')
                row += f" {ComparisonHelpersMixin._format_optional_number(val, '.0f')} |"
            md_lines.append(row)

            md_lines.append("")

        # Ragone Data (Power vs Energy)
        if ragone_data and len(ragone_data) >= 2:
            md_lines.extend([
                "### Ragone Plot Data (Power Density vs Energy Density)",
                "",
                "| Cell | Energy Density (Wh/kg) | Power Density (W/kg) |",
                "|---|---|---|",
            ])

            for scenario in scenarios:
                if scenario not in ragone_data:
                    continue
                data = ragone_data[scenario]
                energy = data['energy_density_Wh_per_kg']
                power = data['power_density_W_per_kg']
                md_lines.append(f"| {scenario} | {energy:.1f} | {power:.0f} |")

            md_lines.extend([
                "",
                "**Ragone Plot Interpretation**:",
                "- Cells to the right have higher energy density (more Wh per kg)",
                "- Cells higher up have higher power density (more W per kg)",
                "- Ideal EV cells push both corners; real cells show power-energy trade-off",
                "",
            ])

        # Best-For Summary
        if best_for:
            md_lines.extend([
                "### Best-For Summary",
                "",
            ])
            for metric, winner in best_for.items():
                md_lines.append(f"- **{metric}**: {winner}")
            md_lines.append("")

        # Key findings
        md_lines.extend([
            "### Key Findings",
            "",
        ])

        categorical_metrics = [
            (metric_name, metric_data)
            for metric_name, metric_data in metrics_dict.items()
            if metric_data.get('type') != 'numeric'
        ]
        if categorical_metrics:
            md_lines.append("### Status and Error Context")
            md_lines.append("")
            for metric_name, metric_data in categorical_metrics:
                values = metric_data.get('values', {})
                formatted_values = [
                    f"{scenario}: {ComparisonHelpersMixin._format_categorical_value(values.get(scenario))}"
                    for scenario in scenarios
                ]
                md_lines.append(f"- **{metric_name}**: {'; '.join(formatted_values)}")
            md_lines.append("")

        insights = ComparisonHelpersMixin._extract_insights(json_data)
        for insight in insights[:8]:
            md_lines.append(f"- {insight}")

        markdown_text = "\n".join(md_lines)

        # Generate interpretation hints
        hints = ComparisonHelpersMixin._generate_hints(json_data)

        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown_text,
            interpretation_hints=hints,
        )
