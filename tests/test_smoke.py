"""Smoke tests that run real PyBaMM simulations.

These tests verify end-to-end execution paths work — they answer the
single question "does the system basically work?".  If someone breaks
the PyBaMM integration, these tests fail immediately.

Named after the hardware testing practice of plugging in a device and
checking if smoke comes out.

Marked with @pytest.mark.slow so you can exclude them during fast
iteration (``pytest -m "not slow"``), and include them in CI.

Protocols are kept SHORT (60 seconds) so tests run in seconds, not
minutes.  Real investigations use longer protocols, but tests should
be fast enough that developers actually run them.
"""
import pytest

from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.solver import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend


@pytest.fixture(scope="module")
def backend():
    """Shared PyBaMM backend for all smoke tests."""
    return PyBaMMBackend()


@pytest.mark.slow
class TestSingleSimulation:
    """A single simulation runs end-to-end and returns a SimulationRun."""

    def test_lfp_discharge_returns_simulation_run(self, backend):
        """LFP_5AH preset, SPM model, 1C discharge for 60 s at 25 °C."""
        cell = Cell.preset("LFP_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ])
        environment = Environment(temperature_C=25.0)

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=environment,
            solver_config=SolverConfig(),
        )
        sim.validate()

        result = sim.run(backend)

        assert isinstance(result, SimulationRun), (
            f"Expected SimulationRun, got {type(result).__name__}"
        )
        # The solver itself must have succeeded (metadata.success).
        # We don't check is_successful() because the observability layer may
        # flag NaN in derived signals like internal_resistance — a known
        # PyBaMM limitation, not a simulation failure.
        assert result.metadata.success, (
            "PyBaMM solver did not report success"
        )
        assert len(result.available_signals()) > 0, (
            "SimulationRun should expose at least one signal"
        )


@pytest.mark.slow
class TestComparePresets:
    """Comparing two presets via the application service layer works."""

    def test_compare_lfp_and_nmc(self, backend):
        """Run LFP_5AH and NMC_5AH and confirm both produce results."""
        from battery_sim.core.application_services import ComparisonService
        from battery_sim.core.investigation_tools import BatchSimulationConfig

        protocol = Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ])
        config = BatchSimulationConfig(
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            model=Model.SPM,
            solver_config=SolverConfig(),
            backend=backend,
        )

        service = ComparisonService(backend=backend)
        comparison = service.compare_presets(["LFP_5AH", "NMC_5AH"], config)

        assert comparison is not None, "compare_presets returned None"
        assert "metrics" in comparison, "comparison result missing 'metrics' key"
