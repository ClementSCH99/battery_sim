"""Composed ExperimentPlanningToolHandler facade."""

from typing import Optional
from battery_sim.core.cell import Cell
from battery_sim.core.experiment_plan import ExperimentPlan
from battery_sim.core.experiment import Model
from battery_sim.interfaces.presenters.result import DualFormatResult
from battery_sim.interfaces.python.question_interpreter import QuestionInterpreter
from battery_sim.core.result import Signal
from battery_sim.interfaces.python.planning_tools.creation import CreationMixin
from battery_sim.interfaces.python.planning_tools.resolution import ResolutionMixin

class ExperimentPlanningToolHandler(
    CreationMixin,
    ResolutionMixin,
):
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
