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
from battery_sim.core.protocol import Protocol, ConstantCurrent, CC_CV
from battery_sim.core.environment import Environment
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.solver import SolverConfig
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.types.signal import Signal

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


@pytest.mark.slow
class TestCCCVProtocol:
    """CC-CV charge followed by CC discharge runs end-to-end."""

    def test_cccv_charge_then_cc_discharge(self, backend):
        """CC-CV charge (2 A → 3.65 V, taper 0.1 A) then CC discharge (5 A, 120 s)."""
        cell = Cell.preset("LFP_5AH")

        charge = Protocol.cccv(
            charge_current_A=2.0,
            cutoff_voltage_V=3.65,
            taper_current_A=0.1,
        )
        discharge = Protocol.cc(current_A=5.0, duration_s=120)
        protocol = charge + discharge

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.5),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun), (
            f"Expected SimulationRun, got {type(run).__name__}"
        )
        assert run.metadata.success, "PyBaMM solver did not report success"
        assert len(run.result.available_signals()) >= 1, (
            "SimulationRun should expose at least one signal"
        )

    def test_cccv_only(self, backend):
        """Standalone CC-CV charge produces a valid SimulationRun."""
        cell = Cell.preset("LFP_5AH")

        protocol = Protocol.cccv(
            charge_current_A=1.0,
            cutoff_voltage_V=3.65,
            taper_current_A=0.05,
        )

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.5),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "Standalone CC-CV charge failed"


@pytest.mark.slow
class TestCycling:
    """Multi-cycle charge-discharge experiments produce per-cycle metrics."""

    def test_lfp_cycling_3_cycles(self, backend):
        """Run 3 charge-discharge cycles and extract per-cycle metrics."""
        cell = Cell.preset("LFP_5AH")
        charge = Protocol.cccv(
            charge_current_A=2.0,
            cutoff_voltage_V=3.65,
            taper_current_A=0.1,
        )
        discharge = Protocol.cc(current_A=5.0, duration_s=120)
        protocol = Protocol.cycle(charge, discharge, n_cycles=3, rest_s=60)

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.2),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "Cycling simulation failed"

        # Per-cycle signals should be available
        cycle_cap = run.result._data.get(Signal.CYCLE_DISCHARGE_CAPACITY)
        assert cycle_cap is not None, "CYCLE_DISCHARGE_CAPACITY signal missing"
        assert len(cycle_cap.values) == 3, (
            f"Expected 3 cycle values, got {len(cycle_cap.values)}"
        )

        cycle_eff = run.result._data.get(Signal.CYCLE_COULOMBIC_EFFICIENCY)
        assert cycle_eff is not None, "CYCLE_COULOMBIC_EFFICIENCY signal missing"

        cycle_ret = run.result._data.get(Signal.CYCLE_CAPACITY_RETENTION)
        assert cycle_ret is not None, "CYCLE_CAPACITY_RETENTION signal missing"
        # First cycle retention should be 100%
        assert abs(cycle_ret.values[0] - 100.0) < 0.01

    def test_cycling_analyzer(self, backend):
        """CyclingAnalyzer produces summary and fade rate from a cycling run."""
        from battery_sim.core.application_services import CyclingAnalyzer

        cell = Cell.preset("LFP_5AH")
        charge = Protocol.cccv(
            charge_current_A=2.0,
            cutoff_voltage_V=3.65,
            taper_current_A=0.1,
        )
        discharge = Protocol.cc(current_A=5.0, duration_s=120)
        protocol = Protocol.cycle(charge, discharge, n_cycles=3, rest_s=60)

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.2),
        )
        run = sim.run(backend)

        summary = CyclingAnalyzer.cycling_summary(run)
        assert "discharge_capacity_Ah" in summary
        assert len(summary["discharge_capacity_Ah"]) == 3

        fade = CyclingAnalyzer.capacity_fade_rate(run)
        # fade can be positive (growing) or negative (fading) — just not None
        assert fade is not None


@pytest.mark.slow
class TestDegradation:
    """Degradation sub-models produce additional signals during cycling."""

    def test_lfp_sei_degradation_3_cycles(self, backend):
        """Run 3 cycles with SEI degradation and check capacity fade signals."""
        from battery_sim.core.degradation import DegradationConfig

        cell = Cell.preset("LFP_5AH")
        charge = Protocol.cccv(
            charge_current_A=2.0,
            cutoff_voltage_V=3.65,
            taper_current_A=0.1,
        )
        discharge = Protocol.cc(current_A=5.0, duration_s=120)
        protocol = Protocol.cycle(charge, discharge, n_cycles=3, rest_s=60)

        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.2),
            degradation=DegradationConfig(sei_growth=True),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "SEI degradation simulation failed"

        # SEI thickness signal should be present
        sei = run.result._data.get(Signal.SEI_THICKNESS)
        assert sei is not None, "SEI_THICKNESS signal missing"
        assert len(sei.values) > 0
        # SEI thickness should be non-negative
        assert all(v >= 0 for v in sei.values)

        # Total capacity loss should be present
        total_loss = run.result._data.get(Signal.TOTAL_CAPACITY_LOSS)
        assert total_loss is not None, "TOTAL_CAPACITY_LOSS signal missing"

    def test_spme_model_runs(self, backend):
        """SPMe model runs end-to-end without degradation."""
        cell = Cell.preset("LFP_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ])
        sim = Simulation(
            cell=cell,
            model=Model.SPMe,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "SPMe simulation failed"
