# battery_sim/backend/pybamm_backend.py
import pybamm
import numpy as np
import time
from typing import Type

from battery_sim.backend.parameter_mapper import resolve_parameter_mapping
from battery_sim.backend.pybamm_signal import PYBAMM_SIGNAL_MAP, PYBAMM_SIGNAL_ALIASES, DERIVED_SIGNALS
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_backend import SimulationBackend
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest, CC_CV
from battery_sim.core.result import Result
from battery_sim.core.solver import Solver, SolverConfig
from battery_sim.types.timeseries import TimeSeries
from battery_sim.types.signal import Signal

# B11 Observability imports
from battery_sim.core.simulation_metadata import SimulationMetadata
from battery_sim.core.simulation_error import SimulationError, ErrorDetector
from battery_sim.core.convergence_diagnostics import ConvergenceDiagnostics
from battery_sim.core.simulation_run import SimulationRun

_SOLVER_REGISTRY: dict[Solver, Type[pybamm.BaseSolver]] = {
     Solver.CASADI: pybamm.CasadiSolver,
     Solver.SCIPY: pybamm.ScipySolver
}


def translate_protocol_to_pybamm(protocol: Protocol) -> list[str]:
    """Convert domain protocol steps to PyBaMM experiment strings."""
    strings: list[str] = []
    for step in protocol.steps:
        if isinstance(step, ConstantCurrent):
            if step.current_A > 0:
                strings.append(f"Discharge at {step.current_A} A for {step._duration_s} seconds")
            else:
                strings.append(f"Charge at {abs(step.current_A)} A for {step._duration_s} seconds")
        elif isinstance(step, Rest):
            strings.append(f"Rest for {step._duration_s} seconds")
        elif isinstance(step, CC_CV):
            strings.append(f"Charge at {step.charge_current_A} A until {step.cutoff_voltage_V} V")
            strings.append(f"Hold at {step.cutoff_voltage_V} V until {step.taper_current_A} A")
    return strings


class PyBaMMBackend(SimulationBackend):

    def run(self, simulation: Simulation, **kwargs) -> SimulationRun:
        """
        Execute simulation and return complete SimulationRun with observability.
        
        This method orchestrates the simulation workflow without handling details.
        """
        solution, elapsed_seconds = self._execute_simulation(simulation, **kwargs)
        result = self._extract_result(solution)
        observability = self._build_observability_data(result, solution, simulation, elapsed_seconds)
        
        return SimulationRun(
            result=result,
            metadata=observability['metadata'],
            errors=observability['errors'],
            diagnostics=observability['diagnostics'],
        )
    
    def _execute_simulation(self, simulation: Simulation, **kwargs) -> tuple:
        """
        Execute PyBaMM simulation and return solution with timing.
        
        Returns:
            (solution, elapsed_seconds): PyBaMM solution object and wall-clock time
        """
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

        start_time = time.time()
        solution = sim.solve(initial_soc=simulation.solver_config.initial_soc)
        elapsed_seconds = time.time() - start_time
        
        return solution, elapsed_seconds
    
    def _extract_result(self, solution) -> Result:
        """
        Extract Result object from PyBaMM solution.
        
        This handles all signal extraction and derived signal computation.
        """
        data = {}
        time_data = solution["Time [s]"].data
        time_list = time_data.tolist() if hasattr(time_data, 'tolist') else list(time_data)

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
            
            # Energy = integral of power
            energy_rate = power[:-1] * dt / 3600.0  # Convert W*s to Wh
            energy = np.concatenate(([0], np.cumsum(energy_rate)))
            data[Signal.ENERGY] = TimeSeries(
                time_s=time_list,
                values=energy.tolist(),
                unit="Wh"
            )
            
            # Track charged/discharged capacity and energy
            charged_capacity_array = np.zeros_like(current)
            discharged_capacity_array = np.zeros_like(current)
            charged_energy_array = np.zeros_like(current)
            discharged_energy_array = np.zeros_like(current)
            
            for i in range(len(current) - 1):
                if current[i] < 0:
                    charged_capacity_array[i+1] = charged_capacity_array[i] + abs(current[i]) * dt[i] / 3600.0
                    discharged_capacity_array[i+1] = discharged_capacity_array[i]
                    charged_energy_array[i+1] = charged_energy_array[i] + abs(voltage[i] * current[i]) * dt[i] / 3600.0
                    discharged_energy_array[i+1] = discharged_energy_array[i]
                elif current[i] > 0:
                    discharged_capacity_array[i+1] = discharged_capacity_array[i] + current[i] * dt[i] / 3600.0
                    charged_capacity_array[i+1] = charged_capacity_array[i]
                    discharged_energy_array[i+1] = discharged_energy_array[i] + voltage[i] * current[i] * dt[i] / 3600.0
                    charged_energy_array[i+1] = charged_energy_array[i]
                else:
                    charged_capacity_array[i+1] = charged_capacity_array[i]
                    discharged_capacity_array[i+1] = discharged_capacity_array[i]
                    charged_energy_array[i+1] = charged_energy_array[i]
                    discharged_energy_array[i+1] = discharged_energy_array[i]
            
            capacity = discharged_capacity_array - charged_capacity_array
            data[Signal.CAPACITY] = TimeSeries(
                time_s=time_list,
                values=capacity.tolist(),
                unit="Ah"
            )
            
            # Efficiency calculation
            efficiency = np.zeros_like(current, dtype=float)
            for i in range(len(current)):
                if charged_energy_array[i] > 0.0:
                    # Calculate round-trip efficiency
                    efficiency[i] = (discharged_energy_array[i] / charged_energy_array[i]) * 100.0
                elif discharged_energy_array[i] > 0.0:
                    # Discharge-only phase: assume 100% efficiency (no charging losses)
                    efficiency[i] = 100.0
                else:
                    # No activity: no meaningful efficiency
                    efficiency[i] = 100.0
            
            data[Signal.EFFICIENCY] = TimeSeries(
                time_s=time_list,
                values=efficiency.tolist(),
                unit="%"
            )
            
            # Internal Resistance
            window_size = max(int(len(current) / 20), 3)
            resistance = np.full_like(current, np.nan, dtype=float)
            
            for i in range(window_size, len(current) - window_size):
                i_start = i - window_size
                i_end = i + window_size
                
                if np.mean(np.abs(current[i_start:i_end])) < 0.01:
                    continue
                
                dv = voltage[i_end] - voltage[i_start]
                di = current[i_end] - current[i_start]
                
                if abs(di) > 0.01:
                    resistance[i] = abs(dv / di)
            
            data[Signal.INTERNAL_RESISTANCE] = TimeSeries(
                time_s=time_list,
                values=resistance.tolist(),
                unit="Ω"
            )
        
        return Result(data)
    
    def _extract_solution_telemetry(self, solution, elapsed_seconds: float) -> dict:
        termination = str(getattr(solution, "termination", "unknown"))
        termination_text = termination.strip() or "unknown"
        total_time = getattr(getattr(solution, "total_time", None), "value", None)
        lower_termination = termination_text.lower()
        failure_markers = ("error", "fail", "infeasible", "singular", "diverg")

        return {
            "success": not any(marker in lower_termination for marker in failure_markers),
            "convergence_reason": termination_text,
            "duration_s": total_time if total_time is not None else elapsed_seconds,
            "duration_source": "pybamm_total_time" if total_time is not None else "wall_clock",
        }

    def _build_observability_data(self, result: Result, solution, simulation: Simulation, elapsed_seconds: float) -> dict:
        """
        Build all B11 observability components from result.
        
        Returns:
            dict with 'metadata', 'errors', 'diagnostics' keys
        """
        telemetry = self._extract_solution_telemetry(solution, elapsed_seconds)
        time_data = solution["Time [s]"].data
        solver_iterations = len(time_data) if time_data is not None else 0
        
        metadata = SimulationMetadata.create(
            solver_config=simulation.solver_config,
            solver_iterations=solver_iterations,
            solver_iterations_kind="time_points",
            success=telemetry["success"],
            convergence_reason=telemetry["convergence_reason"],
            duration_s=telemetry["duration_s"],
            duration_source=telemetry["duration_source"],
            protocol_steps=len(simulation.protocol.steps) if simulation.protocol else 0,
        )
        
        errors = ErrorDetector.detect_all(result, cell=simulation.cell, model=simulation.model)
        
        diagnostics = ConvergenceDiagnostics.create(
            total_time_steps=solver_iterations,
            avg_newton_iterations=None,
            max_newton_iterations=None,
            min_newton_iterations=None,
            problem_description="Newton iteration telemetry unavailable in current PyBaMM integration",
            telemetry_status="unavailable",
        )
        
        return {
            'metadata': metadata,
            'errors': errors,
            'diagnostics': diagnostics,
        }

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

        steps = translate_protocol_to_pybamm(simulation.protocol)
        periode = None
        
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
        - Cell object (with chemistry-specific parameters)
        - Environment object
        
        Mapping is centralized in backend.parameter_mapper with an explicit
        policy for exact chemistries and supported chemistry variants.
        """
        mapping = resolve_parameter_mapping(cell)
        param_values = pybamm.ParameterValues(mapping.parameter_set)
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
        updates["Ambient temperature [K]"] = environment.ambient_temperature_C + 273.15
        if environment.convection_W_per_m2K is not None:
            updates["Convection coefficient [W/m^2/K]"] = environment.convection_W_per_m2K


        param_values.update(updates)
        return param_values

    def supports_model(self, model: Model) -> bool:
         return model  in {Model.SPM, Model.DFN}

        


