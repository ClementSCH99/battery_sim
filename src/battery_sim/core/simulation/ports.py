from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from battery_sim.core.model import Model

if TYPE_CHECKING:
    from battery_sim.core.simulation import Simulation
    from battery_sim.core.simulation import SimulationRun


class SimulationBackend(ABC):

    @abstractmethod
    def run(self, simulation: "Simulation", **solver_options) -> "SimulationRun":
        """
        Execute the simulation and return the canonical SimulationRun output.
        """
        pass

    @abstractmethod
    def supports_model(self, model: Model) -> bool:
        return True