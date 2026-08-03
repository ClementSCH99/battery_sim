"""Agent-facing handlers for cell discovery and input feasibility checks."""

from typing import Optional

from battery_sim.core.api_schema import APISchema
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.investigation_tools import ConstraintChecker
from battery_sim.core.result_formatter import DualFormatResult


class CellToolHandler:
    """Present the cell catalog and perform pre-simulation checks."""

    def __init__(self, schema: APISchema) -> None:
        self._schema = schema

    def list_presets(self, chemistry: Optional[str] = None) -> DualFormatResult:
        """Return the configured preset catalog with provenance hints."""
        preset_catalog = self._schema.get_presets()
        if chemistry:
            presets = preset_catalog.by_chemistry(chemistry)
            chemistries = [chemistry]
        else:
            presets = {preset.name: preset for preset in preset_catalog.list_presets()}
            chemistries = list(preset_catalog.list_chemistries())

        json_data = {
            "type": "preset_list",
            "chemistries": chemistries,
            "presets": [
                {
                    "name": preset.name,
                    "chemistry": preset.chemistry,
                    "description": preset.description,
                    "capacity_Ah": preset.cell.nominal_capacity_Ah,
                    "nominal_voltage_V": preset.cell.nominal_voltage_V,
                    "internal_resistance_Ohm": preset.cell.internal_resistance_Ohm,
                    "parameter_set": preset.cell.metadata.get("pybamm_parameter_set"),
                    "representation": preset.cell.metadata.get("representation"),
                    "packaging_data_complete": (
                        preset.weight_kg > 0
                        and preset.volume_L > 0
                        and preset.cost_usd > 0
                    ),
                }
                for preset in presets.values()
            ],
        }
        return DualFormatResult(
            json_data=json_data,
            markdown_text=preset_catalog.summary(chemistry=chemistry),
            interpretation_hints=[
                "Check parameter_set and representation before treating a preset as a physical cell",
                "Reference presets are reproducible benchmarks, not commercial-cell digital twins",
                "Compare metrics across consistent scenarios to identify patterns",
            ],
        )

    def check_feasibility(
        self,
        preset_name: str,
        temperature_C: float = 25.0,
    ) -> DualFormatResult:
        """Run inexpensive domain checks before constructing a simulation."""
        cell = Cell.preset(preset_name)
        environment = Environment(ambient_temperature_C=temperature_C)
        violations = ConstraintChecker.check_cell_feasibility(cell)
        violations += ConstraintChecker.check_protocol_feasibility(cell, environment)
        is_feasible = not any(
            violation.violated and violation.severity == "critical"
            for violation in violations
        )
        json_data = {
            "type": "feasibility_check",
            "preset": preset_name,
            "ambient_temperature_C": temperature_C,
            "feasible": is_feasible,
            "scope": "domain pre-check; does not prove PyBaMM convergence",
            "critical_violations": [
                violation.message
                for violation in violations
                if violation.severity == "critical"
            ],
            "warnings": [
                violation.message
                for violation in violations
                if violation.severity == "warning"
            ],
        }
        return DualFormatResult(
            json_data=json_data,
            markdown_text=ConstraintChecker.get_feasibility_report(cell, environment),
            interpretation_hints=[
                "This is a pre-check and does not guarantee solver convergence",
                "Review reported violations and model/parameter-set capabilities",
            ],
        )
