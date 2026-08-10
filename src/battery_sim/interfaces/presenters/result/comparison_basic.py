"""Basic comparison formatting."""

from typing import Any, Dict, List, Optional

from battery_sim.interfaces.presenters.result.model import DualFormatResult
from battery_sim.interfaces.presenters.result.comparison_helpers import ComparisonHelpersMixin

class ComparisonBasicMixin:
    @staticmethod
    def format_comparison(
        scenarios: List[str],
        metrics_dict: Dict[str, Any],
    ) -> DualFormatResult:
        """
        Format a comparison in dual output.

        Args:
            scenarios: List of scenario names
            metrics_dict: Dict of metrics (from ComparisonService)

        Returns:
            DualFormatResult with JSON + Markdown
        """

        # Build JSON structure (clean, queryable)
        json_data = {
            'type': 'comparison',
            'scenarios': scenarios,
            'metrics': {},
        }

        # Analyze each metric
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                # Extract best/worst for numeric metrics
                values = metric_data['values']
                numeric_values = [v for v in values.values() if v is not None]

                if numeric_values:
                    higher_is_better = ComparisonHelpersMixin._higher_is_better(metric_name)
                    best_val = max(numeric_values) if higher_is_better else min(numeric_values)
                    best_scenario = [s for s, v in values.items() if v == best_val][0]

                    worst_val = min(numeric_values) if higher_is_better else max(numeric_values)
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

        # Build Markdown (readable tables)
        md_lines = [
            "## Comparison Results",
            "",
            f"Scenarios compared: {', '.join(f'**{s}**' for s in scenarios)}",
            "",
        ]

        # Create comparison table
        md_lines.append("### Metrics Comparison")
        md_lines.append("")

        # Table header
        header = "| Metric |" + "".join(f" {s} |" for s in scenarios)
        separator = "|" + "-" * (10 + len(scenarios) * 20) + "|"

        md_lines.append(header)
        md_lines.append(separator)

        # Table rows
        for metric_name, metric_data in metrics_dict.items():
            if metric_data['type'] == 'numeric':
                values = metric_data['values']
                row = f"| {metric_name} |"
                for scenario in scenarios:
                    val = values.get(scenario)
                    if val is not None:
                        # Format number nicely
                        if isinstance(val, float):
                            formatted = f"{val:.2f}"
                        else:
                            formatted = str(val)
                        row += f" {formatted} |"
                    else:
                        row += " - |"
                md_lines.append(row)

        # Add categorical/error-focused context when available
        categorical_metrics = [
            (metric_name, metric_data)
            for metric_name, metric_data in metrics_dict.items()
            if metric_data.get('type') != 'numeric'
        ]
        if categorical_metrics:
            md_lines.append("")
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

        # Key findings  
        md_lines.append("### Key Findings")
        md_lines.append("")

        # Extract top insights
        insights = ComparisonHelpersMixin._extract_insights(json_data)
        for insight in insights[:5]:  # Top 5 insights
            md_lines.append(f"- {insight}")

        markdown_text = "\n".join(md_lines)

        # Generate interpretation hints
        hints = ComparisonHelpersMixin._generate_hints(json_data)

        return DualFormatResult(
            json_data=json_data,
            markdown_text=markdown_text,
            interpretation_hints=hints,
        )
