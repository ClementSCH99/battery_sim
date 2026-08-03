"""Concrete dependency composition kept outside the domain and interfaces."""

from battery_sim.core.simulation import SimulationBackend
from battery_sim.infrastructure.pybamm.pybamm_backend import PyBaMMBackend


def create_backend() -> SimulationBackend:
    """Build the supported PyBaMM simulation adapter."""

    return PyBaMMBackend()
