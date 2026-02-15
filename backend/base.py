# battery_sim/backend/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from battery_sim.core.model import Model

if TYPE_CHECKING:
    from battery_sim.core.result import Result
    from battery_sim.core.simulation import Simulation
    from battery_sim.core.simulation_run import SimulationRun

class SimulationBackend(ABC):

    @abstractmethod
    def run(self, simulation: "Simulation", **solver_options) -> "SimulationRun":
        """
        Execute the simulation and return a SimulationRun object.
        
        **B11 Enhancement**: Returns complete SimulationRun with Result, Metadata, Errors, and Diagnostics.
        
        The SimulationRun can be used as:
            run = backend.run(simulation)
            result = run.result  # Access the Result object
            efficiency = run.charge_discharge_efficiency()  # Delegate to result
            duration = run.metadata.duration_s  # Access timing info
            errors = run.errors  # Check for any errors/warnings
        """
        pass

    @abstractmethod
    def supports_model(self, model: Model) -> bool:
        return True