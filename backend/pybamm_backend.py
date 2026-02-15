# battery_sim/backend/pybamm_backend.py
import pybamm
import numpy as np
from typing import Type

from battery_sim.backend.base import SimulationBackend
from battery_sim.backend.pybamm_signal import PYBAMM_SIGNAL_MAP, PYBAMM_SIGNAL_ALIASES, DERIVED_SIGNALS
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

        solution = sim.solve(
            initial_soc=0
            )

        data = {}
        time = solution["Time [s]"].data
        time_list = time.tolist() if hasattr(time, 'tolist') else list(time)

        # Flatten if 2D
        if isinstance(time_list, list) and len(time_list) > 0 and isinstance(time_list[0], list):
            time_list = [t[0] if isinstance(t, list) else t for t in time_list]
        
        # Extract primary signals from PyBaMM  
        # Note: SOC is not available in standard SPM/DFN models - they compute voltage only
        for signal, (pybamm_name, unit) in PYBAMM_SIGNAL_MAP.items():
            values = None
            found_name = None
            
            # Try primary name first
            try:
                values = solution[pybamm_name].data
                found_name = pybamm_name
            except KeyError:
                # Try alternative names if available
                if signal in PYBAMM_SIGNAL_ALIASES:
                    for alt_name in PYBAMM_SIGNAL_ALIASES[signal]:
                        try:
                            values = solution[alt_name].data
                            found_name = alt_name
                            break
                        except KeyError:
                            continue
            
            # Skip if signal not found
            if values is None:
                continue
            
            values_array = np.array(values)
            
            # Unit conversions
            if signal == Signal.SOC:
                if np.max(values_array) <= 1.0:  # If in [0,1], convert to percentage
                    values_array = values_array * 100.0
                unit = "%"
            
            if signal == Signal.TEMPERATURE:
                values_array = values_array - 273.15
                unit = "°C"
            
            # Convert to list and flatten if 2D
            values_list = values_array.tolist() if hasattr(values_array, 'tolist') else list(values_array)
            if isinstance(values_list, list) and len(values_list) > 0 and isinstance(values_list[0], list):
                values_list = [v[0] if isinstance(v, list) else v for v in values_list]
            
            data[signal] = TimeSeries(
                time_s=time_list,
                values=values_list,
                unit=unit
            )
        
        # Compute derived signals
        if Signal.VOLTAGE in data and Signal.CURRENT in data:
            voltage = np.array(data[Signal.VOLTAGE].values)
            current = np.array(data[Signal.CURRENT].values)
            time_array = np.array(time_list)
            dt = np.diff(time_array)
            
            # Power = V * I
            power = voltage * current
            data[Signal.POWER] = TimeSeries(
                time_s=time_list,
                values=power.tolist(),
                unit="W"
            )
            
            # Energy = integral of power (trapz rule for accuracy)
            # Use trapezoid rule: integral = sum((V[i]+V[i+1])/2 * (I[i]+I[i+1])/2 * dt)
            energy_rate = power[:-1] * dt / 3600.0  # Convert W*s to Wh
            energy = np.concatenate(([0], np.cumsum(energy_rate)))
            data[Signal.ENERGY] = TimeSeries(
                time_s=time_list,
                values=energy.tolist(),
                unit="Wh"
            )
            
            # Separate charged and discharged tracking
            # Charging: current < 0 (using PyBaMM convention)
            # Discharging: current > 0
            charged_capacity_array = np.zeros_like(current)
            discharged_capacity_array = np.zeros_like(current)
            charged_energy_array = np.zeros_like(current)
            discharged_energy_array = np.zeros_like(current)
            
            for i in range(len(current) - 1):
                # Charged: negative current
                if current[i] < 0:
                    charged_capacity_array[i+1] = charged_capacity_array[i] + abs(current[i]) * dt[i] / 3600.0
                    discharged_capacity_array[i+1] = discharged_capacity_array[i]
                    charged_energy_array[i+1] = charged_energy_array[i] + abs(voltage[i] * current[i]) * dt[i] / 3600.0
                    discharged_energy_array[i+1] = discharged_energy_array[i]
                # Discharged: positive current
                elif current[i] > 0:
                    discharged_capacity_array[i+1] = discharged_capacity_array[i] + current[i] * dt[i] / 3600.0
                    charged_capacity_array[i+1] = charged_capacity_array[i]
                    discharged_energy_array[i+1] = discharged_energy_array[i] + voltage[i] * current[i] * dt[i] / 3600.0
                    charged_energy_array[i+1] = charged_energy_array[i]
                else:
                    # No current
                    charged_capacity_array[i+1] = charged_capacity_array[i]
                    discharged_capacity_array[i+1] = discharged_capacity_array[i]
                    charged_energy_array[i+1] = charged_energy_array[i]
                    discharged_energy_array[i+1] = discharged_energy_array[i]
            
            # Net capacity = absolute value of final discharged - final charged
            capacity = discharged_capacity_array - charged_capacity_array
            data[Signal.CAPACITY] = TimeSeries(
                time_s=time_list,
                values=capacity.tolist(),
                unit="Ah"
            )
            
            # Calculate efficiency (energy out / energy in)
            # Only where both > 0
            efficiency = np.zeros_like(current) * np.nan
            for i in range(len(current)):
                if charged_energy_array[i] > 0:
                    efficiency[i] = (discharged_energy_array[i] / charged_energy_array[i]) * 100.0
            
            data[Signal.EFFICIENCY] = TimeSeries(
                time_s=time_list,
                values=efficiency.tolist(),
                unit="%"
            )
            
            # Internal Resistance: Calculate from voltage change divided by current change
            # Better than V/I which mixes different time periods
            # Use moving window to smooth
            window_size = max(int(len(current) / 20), 3)  # ~5% of data points
            resistance = np.full_like(current, np.nan)
            
            for i in range(window_size, len(current) - window_size):
                i_start = i - window_size
                i_end = i + window_size
                
                # Skip if current is near zero (no meaningful resistance)
                if np.mean(np.abs(current[i_start:i_end])) < 0.01:
                    continue
                
                # dV / dI (voltage change over current change)
                dv = voltage[i_end] - voltage[i_start]
                di = current[i_end] - current[i_start]
                
                if abs(di) > 0.01:  # Avoid division by very small change
                    resistance[i] = abs(dv / di)
            
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

        


