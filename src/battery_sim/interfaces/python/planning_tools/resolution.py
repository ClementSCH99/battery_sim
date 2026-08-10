"""Focused resolution behavior."""

from typing import Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment_plan import ExperimentPlan
from battery_sim.core.experiment import Model
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.interfaces.python.question_interpreter import QuestionInterpreter
from battery_sim.core.result import Signal


class ResolutionMixin:
    @staticmethod
    def _resolve_input(
        field_name: str,
        explicit_value,
        interpretation,
        resolved_sources: dict[str, dict],
        conflicts: list[dict],
    ):
        evidence = interpretation.fields.get(field_name)
        if explicit_value is not None:
            resolved_sources[field_name] = {
                "source": "explicit_argument",
                "value": explicit_value,
            }
            if evidence and not ResolutionMixin._values_match(
                explicit_value, evidence.value
            ):
                conflicts.append(
                    {
                        "field": field_name,
                        "explicit_value": explicit_value,
                        "question_value": evidence.value,
                        "question_evidence": evidence.text,
                    }
                )
            return explicit_value
        if evidence:
            resolved_sources[field_name] = {
                "source": "question_exact_match",
                **evidence.to_dict(),
            }
            return evidence.value
        return None
    @staticmethod
    def _values_match(first, second) -> bool:
        if isinstance(first, list) and isinstance(second, list):
            return set(first) == set(second)
        if isinstance(first, str) and isinstance(second, str):
            return first.casefold() == second.casefold()
        return first == second
    def _resolve_signals(self, requested: Optional[list[str]]) -> tuple[Signal, ...]:
        if requested is None:
            return self.DEFAULT_SIGNALS
        if not requested:
            raise ValueError("requested_signals must contain at least one signal")
        try:
            return tuple(Signal(value) for value in requested)
        except ValueError as exc:
            available = ", ".join(signal.value for signal in Signal)
            raise ValueError(f"Unknown requested signal. Available signals: {available}") from exc
    def _select_model(
        self,
        requested_model: Optional[str],
        signals: tuple[Signal, ...],
    ) -> tuple[Model, str, bool]:
        if requested_model is not None:
            selected = Model.from_value(requested_model)
            signal_set = set(signals)
            if signal_set & self.ELECTRODE_SIGNALS and selected is not Model.DFN:
                raise ValueError("Electrode-resolved signals require the DFN model")
            if signal_set & self.ELECTROLYTE_SIGNALS and selected is Model.SPM:
                raise ValueError("Electrolyte-state signals require SPMe or DFN")
            return selected, "Model explicitly selected by the requester.", False
        signal_set = set(signals)
        if signal_set & self.ELECTRODE_SIGNALS:
            return Model.DFN, "DFN proposed because electrode-resolved signals were requested.", True
        if signal_set & self.ELECTROLYTE_SIGNALS:
            return Model.SPMe, "SPMe proposed because electrolyte-state signals were requested.", True
        return Model.SPM, "SPM proposed as the least complex model supporting bulk electrical outputs.", True
    @staticmethod
    def _protocol_proposal(
        investigation_type: str,
        cell: Optional[Cell],
        *,
        c_rate: Optional[float] = None,
    ) -> dict:
        resolved_c_rate = 1.0 if c_rate is None else c_rate
        capacity = cell.nominal_capacity_Ah if cell else None
        if investigation_type == "rest":
            return {"kind": "rest", "duration_s": 600.0}
        if investigation_type == "cccv_charge":
            max_voltage = float(cell.metadata["max_voltage_v"]) if cell and "max_voltage_v" in cell.metadata else None
            return {
                "kind": "cccv_charge",
                "initial_soc": 0.2,
                "charge_current_A": capacity,
                "cutoff_voltage_V": max_voltage,
                "taper_current_A": None if capacity is None else 0.05 * capacity,
            }
        return {
            "kind": "cc_discharge",
            "initial_soc": 1.0,
            "current_A": None if capacity is None else capacity * resolved_c_rate,
            "c_rate": resolved_c_rate,
            "duration_s": 3600.0 / resolved_c_rate,
        }
    @staticmethod
    def _format_markdown(data: dict) -> str:
        config = data["configuration"]
        lines = [
            "# Proposed Electrochemical Experiment",
            "",
            f"**Question:** {data['question']}",
            f"**Status:** {data['status']}",
            f"**Preset:** {config['preset_name'] or 'MISSING'}",
            f"**Model:** {config['model']} — {data['model_rationale']}",
            f"**Investigation:** {config['investigation_type']}",
            f"**Ambient temperature:** {config['ambient_temperature_C']} °C",
            f"**Signals:** {', '.join(config['requested_signals'])}",
        ]
        if data["missing_inputs"]:
            lines.extend(["", "## Missing inputs", *[f"- {item}" for item in data["missing_inputs"]]])
        if data["proposed_defaults"]:
            lines.extend(["", "## Defaults requiring confirmation"])
            lines.extend(
                f"- {item['field']} = {item['value']}: {item['reason']}"
                for item in data["proposed_defaults"]
            )
        if data["traceability"]["conflicts"]:
            lines.extend(["", "## Interpretation conflicts"])
            lines.extend(
                f"- {item['field']}: argument={item['explicit_value']}; "
                f"question={item['question_value']} ({item['question_evidence']!r})"
                for item in data["traceability"]["conflicts"]
            )
        return "\n".join(lines)
