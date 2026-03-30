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


@pytest.mark.slow
class TestThermalCoupling:
    """Thermal-electrochemical coupling produces temperature and heat signals."""

    def test_lumped_thermal_produces_temperature_rise(self, backend):
        """LFP_5AH CC discharge with lumped thermal shows temperature > initial."""
        cell = Cell.preset("LFP_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=1.0, _duration_s=60),
        ])
        environment = Environment(
            temperature_C=25.0,
            thermal_model="lumped",
            convection_W_per_m2K=10.0,
        )
        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=environment,
            solver_config=SolverConfig(),
        )
        run = sim.run(backend)

        assert run.metadata.success, "Thermal simulation failed"

        cell_temp = run.result._data.get(Signal.CELL_TEMPERATURE)
        assert cell_temp is not None, "CELL_TEMPERATURE signal missing"
        assert max(cell_temp.values) > 25.0, (
            "Cell temperature should rise above initial 25 °C"
        )

        irr_heat = run.result._data.get(Signal.IRREVERSIBLE_HEAT)
        assert irr_heat is not None, "IRREVERSIBLE_HEAT signal missing"
        assert any(v != 0.0 for v in irr_heat.values), (
            "Irreversible heat should have non-zero values"
        )

    def test_isothermal_vs_thermal_voltage_differs(self, backend):
        """Isothermal and lumped-thermal produce different voltage curves."""
        cell = Cell.preset("LFP_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=1.0, _duration_s=60),
        ])

        sim_iso = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )
        sim_thermal = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(
                temperature_C=25.0,
                thermal_model="lumped",
                convection_W_per_m2K=10.0,
            ),
            solver_config=SolverConfig(),
        )

        run_iso = sim_iso.run(backend)
        run_thermal = sim_thermal.run(backend)

        assert run_iso.metadata.success
        assert run_thermal.metadata.success

        v_iso = run_iso.result._data[Signal.VOLTAGE].values
        v_thermal = run_thermal.result._data[Signal.VOLTAGE].values
        # The curves should differ (thermal feedback changes kinetics)
        min_len = min(len(v_iso), len(v_thermal))
        diff = sum(abs(a - b) for a, b in zip(v_iso[:min_len], v_thermal[:min_len]))
        assert diff > 0, "Isothermal and thermal voltage curves should differ"


@pytest.mark.slow
class TestDeepElectrochemicalObservability:
    """Phase B: electrode-level physics signals are extracted from DFN/SPM."""

    def test_dfn_exposes_electrochemical_signals(self, backend):
        """DFN model on NMC_5AH produces electrode-level observability signals."""
        cell = Cell.preset("NMC_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=1.0, _duration_s=60),
        ])
        sim = Simulation(
            cell=cell,
            model=Model.DFN,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )
        run = sim.run(backend)

        assert run.metadata.success, "DFN simulation failed"

        phase_b_signals_found = [
            s for s in [
                Signal.NEGATIVE_OCV,
                Signal.POSITIVE_OCV,
                Signal.NEGATIVE_PARTICLE_SURFACE_CONCENTRATION,
                Signal.POSITIVE_PARTICLE_SURFACE_CONCENTRATION,
                Signal.NEGATIVE_EXCHANGE_CURRENT_DENSITY,
                Signal.POSITIVE_EXCHANGE_CURRENT_DENSITY,
                Signal.NEGATIVE_REACTION_OVERPOTENTIAL,
                Signal.POSITIVE_REACTION_OVERPOTENTIAL,
                Signal.ELECTROLYTE_POTENTIAL,
                Signal.NEGATIVE_STOICHIOMETRY,
                Signal.POSITIVE_STOICHIOMETRY,
                Signal.NEGATIVE_SOLID_POTENTIAL,
                Signal.POSITIVE_SOLID_POTENTIAL,
            ]
            if s in run.result._data
        ]
        assert len(phase_b_signals_found) >= 5, (
            f"Expected >=5 Phase B signals, found {len(phase_b_signals_found)}: "
            f"{[s.name for s in phase_b_signals_found]}"
        )

    def test_dfn_ocv_ranges_physically_reasonable(self, backend):
        """Negative OCV should be 0-1 V (graphite) and positive OCV 3-5 V (NMC)."""
        cell = Cell.preset("NMC_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=1.0, _duration_s=60),
        ])
        sim = Simulation(
            cell=cell,
            model=Model.DFN,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )
        run = sim.run(backend)

        assert run.metadata.success

        neg_ocv = run.result._data.get(Signal.NEGATIVE_OCV)
        if neg_ocv is not None:
            assert all(0.0 <= v <= 1.5 for v in neg_ocv.values), (
                f"Negative OCV out of range: min={min(neg_ocv.values):.3f}, "
                f"max={max(neg_ocv.values):.3f}"
            )

        pos_ocv = run.result._data.get(Signal.POSITIVE_OCV)
        if pos_ocv is not None:
            assert all(2.5 <= v <= 5.0 for v in pos_ocv.values), (
                f"Positive OCV out of range: min={min(pos_ocv.values):.3f}, "
                f"max={max(pos_ocv.values):.3f}"
            )

    def test_spm_no_crash_electrolyte_signals_absent(self, backend):
        """SPM model runs without crash; electrolyte-only signals may be absent."""
        cell = Cell.preset("NMC_5AH")
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=1.0, _duration_s=60),
        ])
        sim = Simulation(
            cell=cell,
            model=Model.SPM,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )
        run = sim.run(backend)

        assert run.metadata.success, "SPM simulation should not crash with Phase B signals"


@pytest.mark.slow
class TestAdvancedDegradation:
    """Phase C: advanced degradation sub-model selectors work end-to-end."""

    def test_sei_solvent_diffusion_limited(self, backend):
        """Run NMC_5AH cycling (3 cycles) with sei_model='solvent-diffusion limited' on SPMe."""
        from battery_sim.core.degradation import DegradationConfig

        cell = Cell.preset("NMC_5AH")
        charge = Protocol.cccv(
            charge_current_A=2.0,
            cutoff_voltage_V=4.2,
            taper_current_A=0.1,
        )
        discharge = Protocol.cc(current_A=5.0, duration_s=120)
        protocol = Protocol.cycle(charge, discharge, n_cycles=3, rest_s=60)

        sim = Simulation(
            cell=cell,
            model=Model.SPMe,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.2),
            degradation=DegradationConfig(sei_model="solvent-diffusion limited"),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "SEI solvent-diffusion limited simulation failed"

        sei = run.result._data.get(Signal.SEI_THICKNESS)
        assert sei is not None, "SEI_THICKNESS signal missing"
        assert len(sei.values) > 0
        # SEI thickness should be monotonically non-decreasing
        for i in range(1, len(sei.values)):
            assert sei.values[i] >= sei.values[i - 1] - 1e-15, (
                f"SEI thickness decreased at index {i}: "
                f"{sei.values[i-1]} -> {sei.values[i]}"
            )

    def test_sei_ec_reaction_limited_via_explicit_model(self, backend):
        """Explicit sei_model='ec reaction limited' works the same as sei_growth=True."""
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
            degradation=DegradationConfig(sei_model="ec reaction limited"),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "Explicit SEI model simulation failed"

        sei = run.result._data.get(Signal.SEI_THICKNESS)
        assert sei is not None, "SEI_THICKNESS signal missing"
        assert len(sei.values) > 0

    def test_sei_reaction_limited_on_spme(self, backend):
        """Explicit sei_model='reaction limited' works on SPMe model."""
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
            model=Model.SPMe,
            protocol=protocol,
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=0.2),
            degradation=DegradationConfig(sei_model="reaction limited"),
        )
        run = sim.run(backend)

        assert isinstance(run, SimulationRun)
        assert run.metadata.success, "SEI reaction limited on SPMe failed"

        sei = run.result._data.get(Signal.SEI_THICKNESS)
        assert sei is not None, "SEI_THICKNESS signal missing"
        assert len(sei.values) > 0


@pytest.mark.slow
class TestValidatedParameterSetPresets:
    """Smoke tests for newly added validated PyBaMM parameter set presets."""

    @pytest.mark.parametrize("preset_name,current_A", [
        ("NMC_ECKER_KOKAM", 0.15),   # ~1C for 0.156 Ah single electrode pair
        ("NMC_OKANE_AGING", 1.0),
        ("NMC_MOHTAT_POUCH", 1.0),
        ("NMC_AI_ENERTECH", 1.0),
    ])
    def test_validated_preset_cc_discharge(self, backend, preset_name, current_A):
        """Each validated parameter set preset runs a CC discharge and returns voltage data."""
        cell = Cell.preset(preset_name)
        protocol = Protocol(steps=[
            ConstantCurrent(current_A=current_A, _duration_s=60),
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
            f"Expected SimulationRun for {preset_name}, got {type(result).__name__}"
        )
        assert result.metadata.success, (
            f"PyBaMM solver did not report success for {preset_name}"
        )

        voltage = result.result._data.get(Signal.VOLTAGE)
        assert voltage is not None, f"Voltage signal missing for {preset_name}"
        assert len(voltage.values) > 0, f"Voltage data empty for {preset_name}"
        assert all(2.0 <= v <= 5.0 for v in voltage.values), (
            f"Voltage out of physical range for {preset_name}: "
            f"min={min(voltage.values):.3f}, max={max(voltage.values):.3f}"
        )
