# battery_sim/core/simulation.py
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from battery_sim.core.simulation import SimulationRun
    from battery_sim.core.simulation import SimulationBackend
    
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig
from battery_sim.core.degradation import DegradationConfig


@dataclass(frozen=True)
class Simulation:
    """Fully specified simulation request (cell + model + protocol + environment).

    Call ``run(backend)`` to execute and obtain a ``SimulationRun``.
    Call ``validate()`` to check parameter consistency without executing.
    """

    cell: Cell
    model: Model
    protocol: Protocol
    environment: Environment
    solver_config: SolverConfig = field(default_factory=SolverConfig)
    degradation: Optional[DegradationConfig] = None

    def run(self, backend: "SimulationBackend", **solver_options) -> "SimulationRun":
        """
        Execute the simulation and return the canonical SimulationRun output.

        The backend is provided at run time by the service layer, keeping the
        Simulation dataclass free of infrastructure concerns.

        SimulationRun contains the Result payload plus metadata, errors, and
        diagnostics. Compatibility delegates remain available on SimulationRun,
        so existing code can still call common Result methods directly on the run:
            run = simulation.run(backend)
            efficiency = run.charge_discharge_efficiency()  # Works!
            result = run.result  # Access Result separately if needed
        """
        self.validate()
        return backend.run(self, **solver_options)
    
    def validate(self) -> None:
        """
        Validate that simulation parameters are consistent.
        """
        self.cell.validate()
        self.protocol.validate()
        self.environment.validate()
        self.solver_config.validate()
        if self.degradation is not None:
            self.degradation.validate()

        
        


