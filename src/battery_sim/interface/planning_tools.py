"""Agent-facing construction of explicit, non-executing experiment plans."""

from typing import Optional

from battery_sim.core.cell import Cell
from battery_sim.core.experiment_plan import ExperimentPlan
from battery_sim.core.model import Model
from battery_sim.core.result_formatter import DualFormatResult
from battery_sim.interface.question_interpreter import QuestionInterpreter
from battery_sim.types.signal import Signal


class ExperimentPlanningToolHandler:
    """Turn structured engineering intent into a plan an engineer can review."""

    SUPPORTED_INVESTIGATIONS = {"cc_discharge", "rest", "cccv_charge"}
    DEFAULT_SIGNALS = (Signal.VOLTAGE, Signal.CURRENT, Signal.SOC)
    ELECTROLYTE_SIGNALS = {
        Signal.ELECTROLYTE_CONCENTRATION,
        Signal.ELECTROLYTE_POTENTIAL,
    }
    ELECTRODE_SIGNALS = {
        Signal.ANODE_POTENTIAL,
        Signal.CATHODE_POTENTIAL,
        Signal.NEGATIVE_SOLID_POTENTIAL,
        Signal.POSITIVE_SOLID_POTENTIAL,
        Signal.NEGATIVE_REACTION_OVERPOTENTIAL,
        Signal.POSITIVE_REACTION_OVERPOTENTIAL,
    }
    THERMAL_SIGNALS = {
        Signal.TEMPERATURE,
        Signal.CELL_TEMPERATURE,
        Signal.HEAT_GENERATION,
        Signal.IRREVERSIBLE_HEAT,
        Signal.REVERSIBLE_HEAT,
        Signal.OHMIC_HEAT,
    }

    def __init__(self, execution_model: Model = Model.SPM) -> None:
        self._execution_model = execution_model
        self._question_interpreter = QuestionInterpreter()

    def create(
        self,
        *,
        question: str,
        preset_name: Optional[str] = None,
        investigation_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature_C: Optional[float] = None,
        requested_signals: Optional[list[str]] = None,
    ) -> DualFormatResult:
        question = question.strip()
        if not question:
            raise ValueError("question must be a non-empty string")
        interpretation = self._question_interpreter.interpret(question)
        resolved_sources: dict[str, dict] = {
            "question": {"source": "user_question", "value": question}
        }
        conflicts: list[dict] = []

        preset_name = self._resolve_input(
            "preset_name", preset_name, interpretation, resolved_sources, conflicts
        )
        investigation_type = self._resolve_input(
            "investigation_type",
            investigation_type,
            interpretation,
            resolved_sources,
            conflicts,
        )
        model = self._resolve_input(
            "model", model, interpretation, resolved_sources, conflicts
        )
        temperature_C = self._resolve_input(
            "temperature_C",
            temperature_C,
            interpretation,
            resolved_sources,
            conflicts,
        )
        requested_signals = self._resolve_input(
            "requested_signals",
            requested_signals,
            interpretation,
            resolved_sources,
            conflicts,
        )

        proposed_defaults: list[dict] = []
        if investigation_type is None:
            investigation_type = "cc_discharge"
            proposed_defaults.append(
                {
                    "field": "investigation_type",
                    "value": investigation_type,
                    "reason": "reference investigation used when the question contains no supported test type",
                }
            )
            resolved_sources["investigation_type"] = {
                "source": "proposed_default",
                "value": investigation_type,
            }
        if investigation_type not in self.SUPPORTED_INVESTIGATIONS:
            choices = ", ".join(sorted(self.SUPPORTED_INVESTIGATIONS))
            raise ValueError(f"investigation_type must be one of: {choices}")
        if temperature_C is not None and not -40.0 <= temperature_C <= 100.0:
            raise ValueError("temperature_C must be between -40 and 100")

        signals = self._resolve_signals(requested_signals)
        if requested_signals is None:
            proposed_defaults.append(
                {
                    "field": "requested_signals",
                    "value": [signal.value for signal in signals],
                    "reason": "minimal bulk electrical outputs",
                }
            )
            resolved_sources["requested_signals"] = {
                "source": "proposed_default",
                "value": [signal.value for signal in signals],
            }
        selected_model, rationale, model_was_proposed = self._select_model(model, signals)
        missing_inputs: list[str] = []

        cell = None
        if preset_name is None:
            missing_inputs.append("preset_name")
            resolved_sources["preset_name"] = {"source": "missing", "value": None}
        else:
            cell = Cell.preset(preset_name)

        if temperature_C is None:
            temperature_C = 25.0
            proposed_defaults.append(
                {"field": "temperature_C", "value": 25.0, "reason": "standard reference condition"}
            )
            resolved_sources["temperature_C"] = {
                "source": "proposed_default",
                "value": 25.0,
            }
        if model_was_proposed:
            proposed_defaults.append(
                {"field": "model", "value": selected_model.value, "reason": rationale}
            )
            resolved_sources["model"] = {
                "source": "proposed_default",
                "value": selected_model.value,
            }

        for conflict in conflicts:
            proposed_defaults.append(
                {
                    "field": conflict["field"],
                    "value": conflict["explicit_value"],
                    "reason": "explicit argument conflicts with exact evidence in the question",
                }
            )

        thermal_requested = bool(set(signals) & self.THERMAL_SIGNALS)
        thermal_mode = "lumped" if thermal_requested else "isothermal"
        if thermal_requested:
            proposed_defaults.append(
                {"field": "thermal_mode", "value": "lumped", "reason": "thermal signal requested"}
            )

        protocol = self._protocol_proposal(investigation_type, cell)
        proposed_defaults.append(
            {
                "field": "protocol",
                "value": protocol,
                "reason": "reference protocol proposed for the selected investigation type",
            }
        )
        execution_supported = (
            investigation_type == "cc_discharge"
            and selected_model is self._execution_model
            and not thermal_requested
            and cell is not None
        )
        execution_arguments = None
        if execution_supported:
            execution_arguments = {
                "preset_name": preset_name,
                "current_A": protocol["current_A"],
                "duration_s": protocol["duration_s"],
                "temperature_C": temperature_C,
            }
        if conflicts:
            status = "conflict"
        else:
            status = "needs_input" if missing_inputs else "draft_ready"
        plan = ExperimentPlan(
            question=question,
            status=status,
            missing_inputs=tuple(missing_inputs),
            proposed_defaults=tuple(proposed_defaults),
            configuration={
                "preset_name": preset_name,
                "model": selected_model.value,
                "ambient_temperature_C": temperature_C,
                "thermal_mode": thermal_mode,
                "investigation_type": investigation_type,
                "protocol": protocol,
                "requested_signals": [signal.value for signal in signals],
            },
            model_rationale=rationale,
            assumptions=(
                "Current and power use the battery_sim convention: positive is discharge, negative is charge.",
                "Preset parameterisation represents a reference model, not a validated commercial-cell digital twin.",
            ),
            limitations=(
                "This plan does not execute a simulation.",
                "A ready draft still requires confirmation of every proposed default.",
            ),
            execution={
                "direct_core_tool_supported": execution_supported,
                "tool": "run_simulation" if execution_supported else None,
                "arguments": execution_arguments,
                "reason": (
                    "The core MCP run_simulation contract can express this plan."
                    if execution_supported
                    else "The current core MCP execution contract cannot express every planned setting."
                ),
            },
            traceability={
                "question_interpretation": interpretation.to_dict(),
                "resolved_fields": resolved_sources,
                "conflicts": conflicts,
                "policy": "explicit arguments override exact question matches, but conflicts require confirmation",
            },
        )
        data = plan.to_dict()
        return DualFormatResult(
            json_data=data,
            markdown_text=self._format_markdown(data),
            interpretation_hints=[
                "Resolve missing_inputs before execution",
                "Confirm or replace every proposed default",
                "Review model_rationale and requested signal support",
            ],
        )

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
            if evidence and not ExperimentPlanningToolHandler._values_match(
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
    def _protocol_proposal(investigation_type: str, cell: Optional[Cell]) -> dict:
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
            "current_A": capacity,
            "c_rate": 1.0,
            "duration_s": 3600.0,
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
