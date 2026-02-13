# battery_sim/core/simulation.py
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from battery_sim.core.result import Result
    
from battery_sim.backend.base import SimulationBackend
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.core.exceptions import SimulationValidationError


@dataclass(frozen=True)
class Simulation:
    cell: Cell
    model: Model
    protocol: Protocol
    environment: Environment
    backend: SimulationBackend
    solver_config: SolverConfig = field(default_factory=SolverConfig)

    def run(self, **solver_options) -> "Result":
        """
        Execute the simulation and return a Result object.
        """
        self.validate()
        return self.backend.run(self, **solver_options)
    
    def validate(self) -> None:
        """
        Validate that simulation parameters are consistent.
        """

        if self.backend is None:
            raise SimulationValidationError(
                "No backend selected - Simulation no possible"
            )
        
        if not self.backend.supports_model(self.model):
            raise SimulationValidationError(
                   f"Model {self.model} not supported by backend {type(self.backend).__name__}"
                   )

        self.cell.validate()
        self.protocol.validate()
        self.environment.validate()
        self.solver_config.validate()

        
        


