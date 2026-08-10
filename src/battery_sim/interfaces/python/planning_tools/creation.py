"""Focused creation behavior."""

from typing import Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment_plan import ExperimentPlan
from battery_sim.core.experiment import Model
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.interfaces.python.question_interpreter import QuestionInterpreter
from battery_sim.core.result import Signal


class CreationMixin:
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
        c_rate: Optional[float] = None,
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
        c_rate = self._resolve_input(
            "c_rate", c_rate, interpretation, resolved_sources, conflicts
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
        if c_rate is not None and c_rate <= 0:
            raise ValueError("c_rate must be > 0")

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

        protocol = self._protocol_proposal(investigation_type, cell, c_rate=c_rate)
        proposed_defaults.append(
            {
                "field": "protocol",
                "value": protocol,
                "reason": "reference protocol proposed for the selected investigation type",
            }
        )
        execution_supported = (
            investigation_type == "cc_discharge"
            and cell is not None
        )
        execution_arguments = None
        if execution_supported:
            execution_arguments = {
                "preset_name": preset_name,
                "current_A": protocol["current_A"],
                "duration_s": protocol["duration_s"],
                "temperature_C": temperature_C,
                "model": selected_model.value,
                "initial_soc": protocol["initial_soc"],
                "thermal_mode": thermal_mode,
                "requested_signals": [signal.value for signal in signals],
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
