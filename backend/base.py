# battery_sim/backend/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from battery_sim.core.model import Model

if TYPE_CHECKING:
    from battery_sim.core.result import Result
    from battery_sim.core.simulation import Simulation

class SimulationBackend(ABC):

    @abstractmethod
    def run(self, simulation: "Simulation", **solver_options) -> "Result":
        """
        Execute the simulation and return a Result object.
        """
        pass

    @abstractmethod
    def supports_model(self, model: Model) -> bool:
        return True