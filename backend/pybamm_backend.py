# battery_sim/backend/pybamm_backend.py
import pybamm
from typing import Type

from battery_sim.backend.base import SimulationBackend
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.result import Result
from battery_sim.core.solver import Solver, SolverConfig
from battery_sim.types.timeseries import TimeSeries

_SOLVER_REGISTRY: dict[Solver, Type[pybamm.BaseSolver]] = {
     Solver.CASADI: pybamm.CasadiSolver,
     Solver.SCIPY: pybamm.ScipySolver
}


class PyBaMMBackend(SimulationBackend):

    def run(self, simulation: Simulation, **kwargs) -> Result:
        
        model = self._build_model(simulation.model)
        experiment = self._build_experiment(simulation)
        solver = self._build_solver(simulation.solver_config)
        parameters = self._build_parameters(simulation.cell)

        sim = pybamm.Simulation(
             model,
             experiment=experiment,
             parameter_values=parameters,
             solver=solver,
             **kwargs
        )

        solution = sim.solve(
             initial_soc=1
        )

        time = solution["Time [s]"].data
        voltage = solution["Terminal voltage [V]"].data
        c_rate = solution["C-rate"].data

        return Result({
             "time": TimeSeries(time_s=time, values=time, unit="s"),
             "voltage": TimeSeries(time_s=time, values=voltage, unit="V"),
             "c-rate": TimeSeries(time_s=time, values=c_rate, unit="-")
        })

    def _build_model(self, model: Model) -> pybamm.lithium_ion.BaseModel:
        if model == Model.SPM:
            return pybamm.lithium_ion.SPM()
        
        elif model == Model.DFN:
            return pybamm.lithium_ion.DFN()
        
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _build_experiment(self, simulation : Simulation) -> pybamm.Experiment:

        steps = []
        periode = None

        for step in simulation.protocol.steps:
                steps.extend(step.to_pybamm())
        
        if simulation.solver_config.time_step_s is not None:
             periode = f"{simulation.solver_config.time_step_s} seconds"

        temperature_k = simulation.environment.temperature_C + 273.15
            
        return pybamm.Experiment(steps, periode, temperature_k)
    
    def _build_solver(self, solver_config: SolverConfig) -> pybamm.BaseSolver:
         try:
             solver_cls = _SOLVER_REGISTRY[solver_config.solver]
         except KeyError:
             raise ValueError(f"Unsopported solver: {solver_config.solver}")
         
         return solver_cls(
              rtol=solver_config.rtol,
              atol=solver_config.atol
         )
    
    def _build_parameters(self, cell: Cell) -> pybamm.ParameterValues:
        """
        Build a PyBaMM ParameterValues object from a Cell object.
        """
        param_values = pybamm.ParameterValues("Chen2020")

        # Map Cell parameters to PyBaMM parameters
        if cell.nominal_capacity_Ah is not None:
            param_values["Nominal cell capacity [A.h]"] = cell.nominal_capacity_Ah
        if cell.nominal_voltage_V is not None:
            param_values["Nominal voltage [V]"] = cell.nominal_voltage_V
        
        # TODO: add more parameters as needed
        # TODO: add correct parameters name for the following:

        # if cell.internal_resistance_Ohm is not None:
        #     param_values["Internal resistance [Ohm]"] = cell.internal_resistance_Ohm

        if cell.electrode_area_m2 is not None:
            param_values["Electrode area [m^2]"] = cell.electrode_area_m2
        if cell.electrode_thickness_m is not None:
            param_values["Electrode thickness [m]"] = cell.electrode_thickness_m

        if cell.density_kg_per_m3 is not None:
            param_values["Density [kg/m^3]"] = cell.density_kg_per_m3
        if cell.specific_heat_J_per_kgK is not None:
            param_values["Specific heat capacity [J/kg/K]"] = cell.specific_heat_J_per_kgK
        if cell.thermal_conductivity_W_per_mK is not None:
            param_values["Thermal conductivity [W/m/K]"] = cell.thermal_conductivity_W_per_mK

        return param_values
    
    def supports_model(self, model: Model) -> bool:
         return model  in {Model.SPM, Model.DFN}

        


