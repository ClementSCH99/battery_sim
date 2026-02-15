# battery_sim/backend/pybamm_backend.py
import pybamm
import numpy as np
from typing import Type

from battery_sim.backend.base import SimulationBackend
from battery_sim.backend.pybamm_signal import PYBAMM_SIGNAL_MAP, DERIVED_SIGNALS
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.result import Result
from battery_sim.core.solver import Solver, SolverConfig
from battery_sim.types.timeseries import TimeSeries
from battery_sim.types.signal import Signal

_SOLVER_REGISTRY: dict[Solver, Type[pybamm.BaseSolver]] = {
     Solver.CASADI: pybamm.CasadiSolver,
     Solver.SCIPY: pybamm.ScipySolver
}


class PyBaMMBackend(SimulationBackend):

    def run(self, simulation: Simulation, **kwargs) -> Result:
        
        model = self._build_model(simulation.model, simulation.environment)
        experiment = self._build_experiment(simulation)
        solver = self._build_solver(simulation.solver_config)
        parameters = self._build_parameters(simulation.cell, simulation.environment)

        sim = pybamm.Simulation(
             model,
             experiment=experiment,
             parameter_values=parameters,
             solver=solver,
             **kwargs
        )

        solution = sim.solve(initial_soc=1)

        data = {}
        time = solution["Time [s]"].data
        time_list = time.tolist() if hasattr(time, 'tolist') else list(time)
        
        # Extract primary signals from PyBaMM
        for signal, (pybamm_name, unit) in PYBAMM_SIGNAL_MAP.items():
            try:
                values = solution[pybamm_name].data
                values_list = values.tolist() if hasattr(values, 'tolist') else list(values)
                
                # Unit conversions
                if signal == Signal.SOC:
                    if np.max(values) <= 1.0:  # If in [0,1], convert to percentage
                        values = values * 100.0
                    unit = "%"
                
                if signal == Signal.TEMPERATURE:
                    values = values - 273.15
                    unit = "°C"
                
                values_list = values.tolist() if hasattr(values, 'tolist') else list(values)
                data[signal] = TimeSeries(
                    time_s=time_list,
                    values=values_list,
                    unit=unit
                )
            except KeyError:
                # Signal not available in this model
                pass
        
        # Compute derived signals
        if Signal.VOLTAGE in data and Signal.CURRENT in data:
            voltage = np.array(data[Signal.VOLTAGE].values)
            current = np.array(data[Signal.CURRENT].values)
            
            # Power = V * I
            power = voltage * current
            data[Signal.POWER] = TimeSeries(
                time_s=time_list,
                values=power.tolist(),
                unit="W"
            )
            
            # Energy = integral of power (trapz rule)
            time_array = np.array(time_list)
            dt = np.diff(time_array)
            energy_increments = power[:-1] * dt / 3600.0  # Convert W*s to Wh
            energy = np.concatenate(([0], np.cumsum(energy_increments)))
            data[Signal.ENERGY] = TimeSeries(
                time_s=time_list,
                values=energy.tolist(),
                unit="Wh"
            )
            
            # Capacity = integral of abs(current) (for charge/discharge tracking)
            capacity_increments = np.abs(current[:-1]) * dt / 3600.0  # Convert A*s to Ah
            capacity = np.concatenate(([0], np.cumsum(capacity_increments)))
            data[Signal.CAPACITY] = TimeSeries(
                time_s=time_list,
                values=capacity.tolist(),
                unit="Ah"
            )
            
            # Internal Resistance approximation = V / I (avoid division by near-zero)
            with np.errstate(divide='ignore', invalid='ignore'):
                resistance = np.where(
                    np.abs(current) > 1e-3,
                    voltage / current,
                    np.nan
                )
            data[Signal.INTERNAL_RESISTANCE] = TimeSeries(
                time_s=time_list,
                values=resistance.tolist(),
                unit="Ω"
            )

        return Result(data)

    def _build_model(self, model: Model, environment: Environment) -> pybamm.lithium_ion.BaseModel:
        options = {}
        
        if environment.convection_W_per_m2K is not None:
            options["thermal"] = "lumped"

            # "isothermal" → pas de thermique
            # "lumped" → 1 température cellule
            # "x-lumped" / "x-full" → spatial 
            

        if model == Model.SPM:
            return pybamm.lithium_ion.SPM(options=options)
        
        elif model == Model.DFN:
            return pybamm.lithium_ion.DFN(options=options)
        
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _build_experiment(self, simulation : Simulation) -> pybamm.Experiment:

        steps = []
        periode = None

        for step in simulation.protocol.steps:
                steps.extend(step.to_pybamm())
        
        if simulation.solver_config.time_step_s is not None:
             periode = f"{simulation.solver_config.time_step_s} seconds"
            
        return pybamm.Experiment(steps, periode)
    
    def _build_solver(self, solver_config: SolverConfig) -> pybamm.BaseSolver:
         try:
             solver_cls = _SOLVER_REGISTRY[solver_config.solver]
         except KeyError:
             raise ValueError(f"Unsopported solver: {solver_config.solver}")
         
         return solver_cls(
              rtol=solver_config.rtol,
              atol=solver_config.atol
         )
    
    def _build_parameters(self, cell: Cell, environment: Environment) -> pybamm.ParameterValues:
        """
        Build a PyBaMM ParameterValues object from:
        - Cell object
        - Environment object
        """
        param_values = pybamm.ParameterValues("Chen2020")
        updates = {}

        # Map Cell parameters to PyBaMM parameters
              
        if cell.nominal_capacity_Ah is not None:
            updates["Nominal cell capacity [A.h]"] = cell.nominal_capacity_Ah
        if cell.nominal_voltage_V is not None:
            updates["Nominal voltage [V]"] = cell.nominal_voltage_V
        
        # TODO: add more parameters as needed
        # TODO: add correct parameters name for the following:

        # if cell.internal_resistance_Ohm is not None:
        #     updates["Internal resistance [Ohm]"] = cell.internal_resistance_Ohm

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


        # Map Environment parameters to PyBaMM parameters
        if environment.temperature_C is not None:
            updates["Ambient temperature [K]"] = environment.temperature_C + 273.15
        if environment.ambiant_temperature_C is not None:
            updates["Ambient temperature [K]"] = environment.ambiant_temperature_C + 273.15
        if environment.convection_W_per_m2K is not None:
            updates["Convection coefficient [W/m^2/K]"] = environment.convection_W_per_m2K


        param_values.update(updates)
        return param_values

    def supports_model(self, model: Model) -> bool:
         return model  in {Model.SPM, Model.DFN}

        


