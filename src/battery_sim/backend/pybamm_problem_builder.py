"""Build PyBaMM-native model, experiment, solver and parameter objects."""

from dataclasses import dataclass
from typing import Any, Type

import pybamm

from battery_sim.backend.parameter_mapper import resolve_parameter_mapping
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.protocol import (
    CC_CV,
    ConstantCurrent,
    DriveProfile,
    PowerStep,
    Protocol,
    Rest,
)
from battery_sim.core.simulation import Simulation
from battery_sim.core.solver import Solver, SolverConfig


_SOLVER_REGISTRY: dict[Solver, Type[pybamm.BaseSolver]] = {
    Solver.CASADI: pybamm.CasadiSolver,
    Solver.SCIPY: pybamm.ScipySolver,
}


@dataclass(frozen=True)
class PyBaMMProblem:
    """Native objects required to instantiate ``pybamm.Simulation``."""

    model: pybamm.lithium_ion.BaseModel
    experiment: pybamm.Experiment
    solver: pybamm.BaseSolver
    parameters: pybamm.ParameterValues


def _translate_steps_to_pybamm(steps) -> list[str]:
    strings: list[str] = []
    for step in steps:
        if isinstance(step, ConstantCurrent):
            action = "Discharge" if step.current_A > 0 else "Charge"
            strings.append(
                f"{action} at {abs(step.current_A)} A for {step._duration_s} seconds"
            )
        elif isinstance(step, PowerStep):
            action = "Discharge" if step.power_W > 0 else "Charge"
            strings.append(
                f"{action} at {abs(step.power_W)} W for {step._duration_s} seconds"
            )
        elif isinstance(step, DriveProfile):
            for power_W, duration_s in step.segments:
                action = "Discharge" if power_W > 0 else "Charge"
                strings.append(
                    f"{action} at {abs(power_W)} W for {duration_s} seconds"
                )
        elif isinstance(step, Rest):
            strings.append(f"Rest for {step._duration_s} seconds")
        elif isinstance(step, CC_CV):
            strings.append(
                f"Charge at {step.charge_current_A} A until {step.cutoff_voltage_V} V"
            )
            strings.append(
                f"Hold at {step.cutoff_voltage_V} V until {step.taper_current_A} A"
            )
        else:
            raise TypeError(f"Unsupported protocol step: {type(step).__name__}")
    return strings


def translate_protocol_to_pybamm(protocol: Protocol) -> list[str]:
    """Translate domain steps while preserving explicit cycle boundaries."""
    if protocol.cycle_definition is not None and protocol.n_cycles is not None:
        cycle = protocol.cycle_definition
        one_cycle: list[str] = []
        one_cycle.extend(_translate_steps_to_pybamm(cycle.charge.steps))
        if cycle.rest_after_charge_s > 0:
            one_cycle.append(f"Rest for {cycle.rest_after_charge_s} seconds")
        one_cycle.extend(_translate_steps_to_pybamm(cycle.discharge.steps))
        if cycle.rest_after_discharge_s > 0:
            one_cycle.append(f"Rest for {cycle.rest_after_discharge_s} seconds")
        return one_cycle * protocol.n_cycles
    return _translate_steps_to_pybamm(protocol.steps)


class PyBaMMProblemBuilder:
    """Translate one validated domain ``Simulation`` into PyBaMM objects."""

    def build(self, simulation: Simulation) -> PyBaMMProblem:
        self.validate_capabilities(simulation)
        return PyBaMMProblem(
            model=self.build_model(
                simulation.model,
                simulation.environment,
                simulation.degradation,
            ),
            experiment=self.build_experiment(simulation),
            solver=self.build_solver(simulation.solver_config),
            parameters=self.build_parameters(
                simulation.cell,
                simulation.environment,
            ),
        )

    @staticmethod
    def validate_capabilities(simulation: Simulation) -> None:
        mapping = resolve_parameter_mapping(simulation.cell)
        thermal_model = simulation.environment.thermal_model
        if thermal_model is None and simulation.environment.convection_W_per_m2K is not None:
            thermal_model = "lumped"
        thermal_model = thermal_model or "isothermal"
        if mapping.parameter_set == "Prada2013" and thermal_model != "isothermal":
            raise ValueError(
                "Prada2013 supports isothermal simulations only in battery_sim; "
                f"thermal_model={thermal_model!r} requires thermal parameters "
                "that are absent from the source parameter set."
            )
        if mapping.parameter_set == "Prada2013" and simulation.degradation is not None:
            raise ValueError(
                "Prada2013 does not provide the SEI/plating/degradation "
                "parameters required by the requested degradation model."
            )

    @staticmethod
    def build_model(
        model: Model,
        environment: Environment,
        degradation: Any = None,
    ) -> pybamm.lithium_ion.BaseModel:
        thermal = environment.thermal_model
        if thermal is None and environment.convection_W_per_m2K is not None:
            thermal = "lumped"
        options: dict[str, str] = {"thermal": thermal or "isothermal"}
        if degradation is not None:
            resolved = degradation.resolve()
            if resolved.sei:
                options["SEI"] = resolved.sei
            if resolved.lithium_plating:
                options["lithium plating"] = resolved.lithium_plating
            if resolved.am_loss:
                options["loss of active material"] = resolved.am_loss
            if resolved.sei_on_cracks:
                options["SEI on cracks"] = "true"
            if resolved.particle_mechanics:
                options["particle mechanics"] = resolved.particle_mechanics

        model_types = {
            Model.SPM: pybamm.lithium_ion.SPM,
            Model.SPMe: pybamm.lithium_ion.SPMe,
            Model.DFN: pybamm.lithium_ion.DFN,
        }
        try:
            model_type = model_types[model]
        except KeyError as exc:
            raise ValueError(f"Unsupported model: {model}") from exc
        return model_type(options=options)

    @staticmethod
    def build_experiment(simulation: Simulation) -> pybamm.Experiment:
        steps = translate_protocol_to_pybamm(simulation.protocol)
        operating_conditions: Any = steps
        if (
            simulation.protocol.cycle_definition is not None
            and simulation.protocol.n_cycles is not None
        ):
            n_cycles = simulation.protocol.n_cycles
            if len(steps) % n_cycles != 0:
                raise ValueError(
                    "Translated protocol steps cannot be grouped into complete cycles."
                )
            steps_per_cycle = len(steps) // n_cycles
            operating_conditions = [
                tuple(steps[index:index + steps_per_cycle])
                for index in range(0, len(steps), steps_per_cycle)
            ]
        period = (
            f"{simulation.solver_config.time_step_s} seconds"
            if simulation.solver_config.time_step_s is not None
            else None
        )
        return pybamm.Experiment(operating_conditions, period)

    @staticmethod
    def build_solver(solver_config: SolverConfig) -> pybamm.BaseSolver:
        try:
            solver_type = _SOLVER_REGISTRY[solver_config.solver]
        except KeyError as exc:
            raise ValueError(f"Unsupported solver: {solver_config.solver}") from exc
        return solver_type(rtol=solver_config.rtol, atol=solver_config.atol)

    @staticmethod
    def build_parameters(
        cell: Cell,
        environment: Environment,
    ) -> pybamm.ParameterValues:
        mapping = resolve_parameter_mapping(cell)
        parameters = pybamm.ParameterValues(mapping.parameter_set)
        updates: dict[str, float] = {}
        if cell.nominal_capacity_Ah is not None:
            updates["Nominal cell capacity [A.h]"] = cell.nominal_capacity_Ah
        if cell.nominal_voltage_V is not None:
            updates["Nominal voltage [V]"] = cell.nominal_voltage_V
        if "min_voltage_v" in cell.metadata:
            updates["Lower voltage cut-off [V]"] = float(cell.metadata["min_voltage_v"])
        if "max_voltage_v" in cell.metadata:
            updates["Upper voltage cut-off [V]"] = float(cell.metadata["max_voltage_v"])
        if cell.electrode_area_m2 is not None:
            updates["Electrode area [m^2]"] = cell.electrode_area_m2
        if cell.electrode_thickness_m is not None:
            updates["Electrode thickness [m]"] = cell.electrode_thickness_m
        if cell.density_kg_per_m3 is not None:
            updates["Density [kg/m^3]"] = cell.density_kg_per_m3
        if cell.specific_heat_J_per_kgK is not None:
            updates["Specific heat capacity [J/kg/K]"] = cell.specific_heat_J_per_kgK
        if cell.thermal_conductivity_W_per_mK is not None:
            updates["Thermal conductivity [W/m/K]"] = cell.thermal_conductivity_W_per_mK
        updates["Ambient temperature [K]"] = environment.ambient_temperature_C + 273.15
        updates["Initial temperature [K]"] = environment.initial_temperature_C + 273.15
        if environment.convection_W_per_m2K is not None:
            updates["Convection coefficient [W/m^2/K]"] = environment.convection_W_per_m2K
        parameters.update(updates)
        return parameters
