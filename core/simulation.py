# battery_sim/core/simulation.py
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from battery_sim.core.simulation_run import SimulationRun
    
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.core.exceptions import SimulationValidationError
from battery_sim.core.simulation_backend import SimulationBackend


@dataclass(frozen=True)
class Simulation:
    cell: Cell
    model: Model
    protocol: Protocol
    environment: Environment
    backend: SimulationBackend
    solver_config: SolverConfig = field(default_factory=SolverConfig)

    def run(self, **solver_options) -> "SimulationRun":
        """
        Execute the simulation and return the canonical SimulationRun output.

        SimulationRun contains the Result payload plus metadata, errors, and
        diagnostics. Compatibility delegates remain available on SimulationRun,
        so existing code can still call common Result methods directly on the run:
            run = simulation.run()
            efficiency = run.charge_discharge_efficiency()  # Works!
            result = run.result  # Access Result separately if needed
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

        
        


