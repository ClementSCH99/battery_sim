"""Literature-backed scientific regression cases for the simulation kernel."""

import numpy as np
import pytest

from battery_sim.backend.parameter_mapper import resolve_parameter_mapping
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.core.cell import Cell
from battery_sim.core.reference_cases import (
    NMC_CHEN_SPM_CCCV_CHARGE,
    NMC_CHEN_SPM_REST,
    PROTOCOL_REFERENCE_CASES,
    REFERENCE_CASES,
    get_reference_case,
)
from battery_sim.core.simulation_metadata import SimulationMetadata
from battery_sim.core.solver import SolverConfig
from battery_sim.types.signal import Signal


class TestReferenceCaseDefinitions:
    def test_names_are_unique_and_lookup_is_stable(self):
        names = [case.name for case in (*REFERENCE_CASES, *PROTOCOL_REFERENCE_CASES)]

        assert len(names) == len(set(names))
        for case in REFERENCE_CASES:
            assert get_reference_case(case.name) is case

    def test_protocol_reference_provenance_matches_mapper(self):
        for case in PROTOCOL_REFERENCE_CASES:
            mapping = resolve_parameter_mapping(Cell.preset(case.preset_name))
            assert mapping.parameter_set == case.parameter_set

    def test_parameter_provenance_matches_preset_and_mapper(self):
        for case in REFERENCE_CASES:
            cell = Cell.preset(case.preset_name)
            mapping = resolve_parameter_mapping(cell)

            assert cell.metadata["pybamm_parameter_set"] == case.parameter_set
            assert mapping.parameter_set == case.parameter_set

    def test_lfp_family_never_maps_to_licoo2_marquis_set(self):
        assert resolve_parameter_mapping(Cell.preset("LFP_5AH")).parameter_set == "Prada2013"
        assert resolve_parameter_mapping(Cell.preset("LFP_PRADA_2P3AH")).parameter_set == "Prada2013"

    def test_voltage_windows_are_explicit_backend_overrides(self):
        backend = PyBaMMBackend()
        for case in REFERENCE_CASES:
            simulation = case.build_simulation()
            parameters = backend._build_parameters(simulation.cell, simulation.environment)

            assert parameters["Lower voltage cut-off [V]"] == case.lower_voltage_V
            assert parameters["Upper voltage cut-off [V]"] == case.upper_voltage_V

    def test_provenance_metadata_round_trips_and_is_human_visible(self):
        metadata = SimulationMetadata.create(
            solver_config=SolverConfig(),
            backend_name="PyBaMM",
            backend_version="test-version",
            model="single_particle",
            cell_chemistry="LFP-PRADA",
            parameter_set="Prada2013",
            parameter_mapping_policy="exact_match",
        )

        restored = SimulationMetadata.from_dict(metadata.to_dict())

        assert restored == metadata
        assert "PyBaMM test-version" in restored.summary()
        assert "parameters=Prada2013" in restored.summary()
        assert restored.simulation_id == metadata.simulation_id

    def test_simulation_metadata_ids_are_unique(self):
        first = SimulationMetadata.create(solver_config=SolverConfig())
        second = SimulationMetadata.create(solver_config=SolverConfig())

        assert first.simulation_id
        assert first.simulation_id != second.simulation_id


@pytest.fixture(scope="module")
def backend():
    return PyBaMMBackend()


@pytest.mark.slow
@pytest.mark.parametrize("case", REFERENCE_CASES, ids=lambda case: case.name)
def test_reference_discharge(case, backend):
    """Verify provenance, sign, conservation, bounds and expected trend."""
    run = case.build_simulation().run(backend)

    assert run.metadata.success, run.metadata.convergence_reason
    assert run.metadata.backend_name == "PyBaMM"
    assert run.metadata.backend_version
    assert run.metadata.model == case.model.value
    assert run.metadata.parameter_set == case.parameter_set
    assert run.metadata.cell_chemistry == Cell.preset(case.preset_name).chemistry

    available = set(run.result.available_signals())
    assert set(case.required_signals) <= available

    time = np.asarray(run.result.get(Signal.TIME).values, dtype=float)
    voltage = np.asarray(run.result.get(Signal.VOLTAGE).values, dtype=float)
    current = np.asarray(run.result.get(Signal.CURRENT).values, dtype=float)
    power = np.asarray(run.result.get(Signal.POWER).values, dtype=float)

    assert np.all(np.diff(time) > 0), "Time must increase strictly"
    assert time[0] == pytest.approx(0.0)
    assert time[-1] == pytest.approx(case.duration_s, abs=1e-6)

    # battery_sim and PyBaMM both use discharge-positive current and power.
    assert np.all(current > 0)
    assert current == pytest.approx(case.current_A, rel=1e-6)
    assert np.all(power > 0)
    assert power == pytest.approx(voltage * current, rel=1e-12, abs=1e-12)

    # A short constant-current discharge must stay inside the parameter-set
    # voltage window and should not finish above its initial loaded voltage.
    assert np.min(voltage) >= case.lower_voltage_V - 1e-6
    assert np.max(voltage) <= case.upper_voltage_V + 1e-6
    assert voltage[-1] <= voltage[0] + 1e-5

    delivered_capacity = run.result.discharged_capacity()
    assert delivered_capacity == pytest.approx(
        case.expected_discharged_capacity_Ah,
        rel=5e-4,
    )
    assert run.result.discharged_energy() > 0
    assert run.result.charged_energy() == pytest.approx(0.0, abs=1e-12)


@pytest.mark.slow
def test_prada_lfp_rejects_unparameterized_lumped_thermal_model(backend):
    case = get_reference_case("lfp_prada_spm_0p5c_discharge")
    simulation = case.build_simulation()
    from dataclasses import replace
    from battery_sim.core.environment import Environment

    simulation = replace(
        simulation,
        environment=Environment(
            ambient_temperature_C=25.0,
            thermal_model="lumped",
            convection_W_per_m2K=10.0,
        ),
    )

    with pytest.raises(ValueError, match="Prada2013 supports isothermal"):
        simulation.run(backend)


@pytest.mark.slow
def test_prada_lfp_rejects_unparameterized_degradation_model(backend):
    from dataclasses import replace
    from battery_sim.core.degradation import DegradationConfig

    simulation = get_reference_case("lfp_prada_spm_0p5c_discharge").build_simulation()
    simulation = replace(simulation, degradation=DegradationConfig(sei_growth=True))

    with pytest.raises(ValueError, match="Prada2013 does not provide"):
        simulation.run(backend)


@pytest.mark.slow
def test_reference_rest_preserves_zero_current_and_voltage(backend):
    case = NMC_CHEN_SPM_REST
    run = case.build_simulation().run(backend)

    assert run.is_successful()
    voltage = np.asarray(run.result.get(Signal.VOLTAGE).values, dtype=float)
    current = np.asarray(run.result.get(Signal.CURRENT).values, dtype=float)
    energy = np.asarray(run.result.get(Signal.ENERGY).values, dtype=float)
    capacity = np.asarray(run.result.get(Signal.CAPACITY).values, dtype=float)

    assert np.allclose(current, 0.0, atol=1e-12)
    assert np.allclose(energy, 0.0, atol=1e-12)
    assert np.allclose(capacity, 0.0, atol=1e-12)
    assert np.ptp(voltage) <= case.maximum_voltage_drift_V
    assert Signal.EFFICIENCY not in run.result.available_signals()


@pytest.mark.slow
def test_reference_cccv_charge_obeys_sign_cutoff_and_taper(backend):
    case = NMC_CHEN_SPM_CCCV_CHARGE
    run = case.build_simulation().run(backend)

    assert run.is_successful()
    voltage = np.asarray(run.result.get(Signal.VOLTAGE).values, dtype=float)
    current = np.asarray(run.result.get(Signal.CURRENT).values, dtype=float)

    assert np.all(current <= 1e-8), "charge current must be non-positive"
    assert np.any(current < -case.taper_current_A)
    assert abs(current[-1]) <= case.taper_current_A * 1.02
    assert voltage[-1] == pytest.approx(case.upper_voltage_V, abs=2e-3)
    assert np.max(voltage) <= case.upper_voltage_V + 2e-3
    assert voltage[-1] > voltage[0]
    assert run.result.charged_capacity() > 0
    assert run.result.charged_energy() > 0
    assert run.result.discharged_capacity() == pytest.approx(0.0, abs=1e-10)
    assert run.result.discharged_energy() == pytest.approx(0.0, abs=1e-10)
    assert Signal.EFFICIENCY not in run.result.available_signals()
