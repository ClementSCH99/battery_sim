"""Contracts separating ambient, initial and simulated cell temperature."""

import pytest

from battery_sim.infrastructure.pybamm.pybamm_backend import PyBaMMBackend
from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Environment


def test_backend_maps_ambient_and_initial_temperature_independently():
    environment = Environment(
        ambient_temperature_C=5.0,
        initial_temperature_C=25.0,
    )

    parameters = PyBaMMBackend()._build_parameters(
        Cell.preset("NMC_CHEN_LGM50"),
        environment,
    )

    assert parameters["Ambient temperature [K]"] == pytest.approx(278.15)
    assert parameters["Initial temperature [K]"] == pytest.approx(298.15)
