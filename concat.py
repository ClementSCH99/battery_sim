
################################################################################
# FILE: backend/base.py
################################################################################

# battery_sim/backend/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

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
################################################################################
# FILE: backend/pybamm_backend.py
################################################################################

# battery_sim/backend/pybamm_backend.py
import pybamm
from typing import Type

from battery_sim.backend.base import SimulationBackend
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

        sim = pybamm.Simulation(
             model,
             experiment=experiment,
             solver=solver,
             **kwargs
        )

        solution = sim.solve()

        time = solution["Time [s]"].data
        voltage = solution["Terminal voltage [V]"].data

        return Result({
             "time": TimeSeries(time_s=time, values=time, unit="s"),
             "voltage": TimeSeries(time_s=time, values=voltage, unit="V")
        })

    def _build_model(self, model: Model):
        if model == Model.SPM:
            return pybamm.lithium_ion.SPM()
        
        elif model == Model.DFN:
            return pybamm.lithium_ion.DFN()
        
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _build_experiment(self, simulation : Simulation):

        steps = []
        for step in simulation.protocol.steps:
                steps.extend(step.to_pybamm())
        
        if simulation.solver_config.time_step_s:
             periode = f"{simulation.solver_config.time_step_s} seconds"
            
        return pybamm.Experiment(steps, periode)
    
    def _build_solver(self, solver_config: SolverConfig):
         try:
             solver_cls = _SOLVER_REGISTRY[solver_config.solver]
         except KeyError:
              raise ValueError(f"Unsopported solver: {solver_config.solver}")
         
         return solver_cls(
              rtol=solver_config.rtol,
              atol=solver_config.atol
         )
    


        



################################################################################
# FILE: core/cell.py
################################################################################

# battery_sim/core/cell.py
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass(frozen=True)
class Cell:
    chemistry: str
    nominal_capacity_Ah: Optional[float] = None
    nominal_voltage_V: Optional[float] = None
    geometry: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
################################################################################
# FILE: core/environment.py
################################################################################

# battery_sim/core/environment.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Environment:
    temperature_C: float
    convection_W_per_m2K: Optional[float] = None

################################################################################
# FILE: core/model.py
################################################################################

# battery_sim/core/model.py
from enum import Enum

class Model(Enum):
    SPM = "single_particule"
    DFN = "doyle_fuller_newman"
################################################################################
# FILE: core/protocol.py
################################################################################

# battery_sim/core/protocol.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Step:
    def to_pybamm(self) -> list[str]:
        raise NotImplementedError
    pass

    def duration_s(self) -> Optional[float]:
        """
        Returns duration in second if fixed, None otherwise.
        """
        return None

@dataclass(frozen=True)
class ConstantCurrent(Step):
    current_A: float
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s

    def to_pybamm(self) -> List[str]:
        """
        Charge: current < 0
        Discharge: current > 0
        """
        if self.current_A > 0:
            return [f"Discharge at {self.current_A} A for {self._duration_s} seconds"]
        else:
            return [f"Charge at {abs(self.current_A)} A for {self._duration_s} seconds"]


@dataclass(frozen=True)
class Rest(Step):
    _duration_s: float

    def duration_s(self) -> float:
        return self._duration_s
    
    def to_pybamm(self) -> List[str]:
        return [f"Rest for {self._duration_s} seconds"]


@dataclass(frozen=True)
class CC_CV(Step):
    charge_current_A: float
    cutoff_voltage_V: float
    taper_current_A: float

    def to_pybamm(self) -> List[str]:
        CC = f"Charge at {self.charge_current_A} A until {self.cutoff_voltage_V} V"
        CV = f"Hold at {self.cutoff_voltage_V} V until {self.taper_current_A} A"
        return [CC,CV]


@dataclass(frozen=True)
class Protocol:
    steps: List[Step]

    def __add__(self, other):
        if not isinstance(other, Protocol):
            return NotImplemented
        return Protocol(self.steps + other.steps)
    
    def total_duration_s(self) -> float:
        total: float = 0.0

        for step in self.steps:
            duration = step.duration_s()
            if duration is None:
                continue
            total += duration
        
        return total


    @staticmethod
    def cc(current_A: float, duration_s: float) -> "Protocol":
        return Protocol([ConstantCurrent(current_A, duration_s)])

    @staticmethod
    def rest(duration_s: float) -> "Protocol":
        return Protocol([Rest(duration_s)])

    @staticmethod
    def cccv(charge_current_A: float, cutoff_voltage_V: float, taper_current_A: float) -> "Protocol":
        return Protocol([CC_CV(charge_current_A, cutoff_voltage_V, taper_current_A)])

    @staticmethod
    def experiment(steps: List[Step]) -> "Protocol":
        return Protocol(steps)

################################################################################
# FILE: core/result.py
################################################################################

# battery_sim/core/result.py
from typing import Optional, Dict
from battery_sim.types.timeseries import TimeSeries

class Result:
    def __init__(self, data: Dict[str, TimeSeries]):
        self._data = data

    def get(self, name: str) -> TimeSeries:
        return self._data[name]

    def final(self, name: str) -> float:
        return self._data[name].values[-1]

    def available_signals(self):
        return list(self._data.keys())
    
    def plot(self, names: Optional[list[str]]):
        import matplotlib.pyplot as plt

        if names is None:
            names = self.available_signals()

        for name in names:
            if name not in self._data:
                raise KeyError(f"Signal '{name}' not found")
            
            ts = self._data[name]
            plt.plot(ts.time_s, ts.values, label=name)
        
        plt.xlabel("Time [s]")
        plt.ylabel("Value")
        plt.grid(True)
        plt.tight_layout()
        plt.legend()
        plt.savefig("fig.jpeg")
################################################################################
# FILE: core/simulation.py
################################################################################

# battery_sim/core/simulation.py
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from battery_sim.core.result import Result
    from battery_sim.backend.base import SimulationBackend

from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig


@dataclass(frozen=True)
class Simulation:
    cell: Cell
    model: Model
    protocol: Protocol
    environment: Environment
    backend: Optional["SimulationBackend"] = None
    solver_config: SolverConfig = field(default_factory=SolverConfig)

    def run(self, **solver_options) -> "Result":
        """
        Execute the simulation and return a Result object.

        """
        if self.backend is None:
            raise RuntimeError("No backend configuration for this simulation")
        
        return self.backend.run(self, **solver_options)

################################################################################
# FILE: core/solver.py
################################################################################

# battery_sim/core/solver.py
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from battery_sim.core.protocol import Protocol

import numpy as np

class Solver(Enum):
    CASADI = "casadi"
    SCIPY = "scipy"

@dataclass(frozen=True)
class SolverConfig:
    solver: Solver = Solver.CASADI
    rtol: float = 1e-6
    atol: float = 1e-9
    time_step_s: Optional[float] = None

    def build_t_eval(self, protocol: Protocol) -> Optional[np.ndarray]:
        if self.time_step_s is None:
            return None
        
        final_time = protocol.total_duration_s()
        return np.arange(0, final_time + self.time_step_s, self.time_step_s)
################################################################################
# FILE: types/timeseries.py
################################################################################

# battery_sim/types/timeseries.py
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class TimeSeries:
    time_s: List[float]
    values: List[float]
    unit: str
