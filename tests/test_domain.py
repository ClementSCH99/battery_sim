# tests/test_domain.py
"""
Unit tests for domain object validation and factory methods.

No PyBaMM dependency — all tests exercise pure domain logic.

LEARNING NOTES:
- Each domain object has a .validate() method that raises a typed
  ValidationError subclass (CellValidationError, ProtocolValidationError, etc.)
- Frozen dataclasses prevent accidental mutation after creation.
- Environment uses a custom __init__ to resolve temperature_C / 
  ambient_temperature_C aliasing — a pattern chosen for backward
  compatibility with early APIs.
- SolverConfig.validate() uses elif chains, meaning only the first
  failing branch is reported. This is a conscious trade-off: fast-fail
  for the most serious error rather than collecting all errors.
"""
import pytest

from battery_sim.core.cell import Cell
from battery_sim.core.experiment import Protocol, ConstantCurrent, Rest, CC_CV, PowerStep, DriveProfile, Step, CycleDefinition
from battery_sim.core.experiment import Environment
from battery_sim.core.experiment import SolverConfig, Solver
from battery_sim.core.experiment import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.drive_cycles import (
    DriveCycleProfile,
    get_drive_cycle,
    list_drive_cycles,
    scale_drive_cycle,
    WLTP_CLASS3,
    US06,
    UDDS,
)
from battery_sim.core.exceptions import (
    CellValidationError,
    ProtocolValidationError,
    EnvironmentValidationError,
    SolverValidationError,
)
from battery_sim.core.result import Signal
from battery_sim.infrastructure.pybamm.pybamm_signal import PYBAMM_SIGNAL_MAP


# ============================================================================
# Cell
# ============================================================================

class TestCellValidation:
    """Cell.validate() enforces positive capacity and voltage."""

    def test_valid_cell_passes(self):
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=5.0)
        cell.validate()  # should not raise

    def test_negative_capacity_rejected(self):
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=-1.0)
        with pytest.raises(CellValidationError):
            cell.validate()

    def test_zero_voltage_rejected(self):
        # LEARNING: 0 is not positive, so validate() rejects it.
        cell = Cell(chemistry="LFP", nominal_voltage_V=0)
        with pytest.raises(CellValidationError):
            cell.validate()

    def test_none_capacity_allowed(self):
        """None means 'not specified' — that's valid (backend picks defaults)."""
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=None)
        cell.validate()  # should not raise

    def test_none_voltage_allowed(self):
        cell = Cell(chemistry="LFP", nominal_voltage_V=None)
        cell.validate()

    def test_negative_voltage_rejected(self):
        cell = Cell(chemistry="LFP", nominal_voltage_V=-3.2)
        with pytest.raises(CellValidationError):
            cell.validate()


class TestCellPresets:
    """Cell.preset() and Cell.list_presets() delegate to CellPresets."""

    def test_preset_lfp_5ah(self):
        cell = Cell.preset("LFP_5AH")
        assert cell.chemistry == "LFP"
        assert cell.nominal_capacity_Ah == 5.0
        cell.validate()

    def test_preset_nonexistent_raises(self):
        with pytest.raises((ValueError, KeyError)):
            Cell.preset("NONEXISTENT")

    def test_list_presets_returns_non_empty(self):
        presets = Cell.list_presets()
        assert isinstance(presets, list)
        assert len(presets) > 0
        assert all(isinstance(name, str) for name in presets)

    def test_all_presets_validate(self):
        """Every shipped preset should pass its own validation."""
        for preset_name in Cell.list_presets():
            cell = Cell.preset(preset_name)
            cell.validate()

    @pytest.mark.parametrize("preset_name", [
        "LFP_PRADA_2P3AH",
        "NMC_CHEN_LGM50",
        "NMC_ECKER_KOKAM",
        "NMC_OKANE_AGING",
        "NMC_MOHTAT_POUCH",
        "NMC_AI_ENERTECH",
    ])
    def test_validated_parameter_set_presets_load(self, preset_name):
        """New validated parameter set presets load and have valid specs."""
        cell = Cell.preset(preset_name)
        assert cell.chemistry, "Chemistry must be set"
        assert cell.nominal_capacity_Ah > 0, "Capacity must be positive"
        assert cell.nominal_voltage_V > 0, "Voltage must be positive"
        assert "source" in cell.metadata, "Metadata must include 'source'"
        cell.validate()


# ============================================================================
# Protocol
# ============================================================================

class TestProtocolFactories:
    """Static factories produce correctly structured protocols."""

    def test_cc_creates_single_constant_current_step(self):
        proto = Protocol.cc(current_A=5.0, duration_s=60)
        assert len(proto.steps) == 1
        assert isinstance(proto.steps[0], ConstantCurrent)
        assert proto.steps[0].current_A == 5.0
        assert proto.steps[0].duration_s() == 60

    def test_rest_creates_single_rest_step(self):
        proto = Protocol.rest(duration_s=300)
        assert len(proto.steps) == 1
        assert isinstance(proto.steps[0], Rest)
        assert proto.steps[0].duration_s() == 300

    def test_cccv_creates_single_cc_cv_step(self):
        proto = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=4.2, taper_current_A=0.1)
        assert len(proto.steps) == 1
        assert isinstance(proto.steps[0], CC_CV)

    def test_power_creates_single_power_step(self):
        proto = Protocol.power(power_W=10.0, duration_s=3600)
        assert len(proto.steps) == 1
        assert isinstance(proto.steps[0], PowerStep)
        assert proto.steps[0].power_W == 10.0
        assert proto.steps[0].duration_s() == 3600

    def test_power_negative_allowed(self):
        """Negative power = charge. That's a valid protocol."""
        proto = Protocol.power(power_W=-5.0, duration_s=1800)
        assert len(proto.steps) == 1
        assert isinstance(proto.steps[0], PowerStep)
        assert proto.steps[0].power_W == -5.0


class TestProtocolValidation:

    def test_empty_steps_rejected(self):
        proto = Protocol(steps=[])
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_zero_current_cc_rejected(self):
        # LEARNING: A 0A constant current is physically meaningless.
        proto = Protocol.cc(current_A=0, duration_s=60)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_valid_cc_passes(self):
        proto = Protocol.cc(current_A=2.0, duration_s=120)
        proto.validate()

    def test_zero_duration_rest_rejected(self):
        proto = Protocol.rest(duration_s=0)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_negative_current_cc_allowed(self):
        """Negative current = discharge. That's a valid protocol."""
        proto = Protocol.cc(current_A=-5.0, duration_s=60)
        proto.validate()

    def test_cccv_zero_charge_current_rejected(self):
        proto = Protocol.cccv(charge_current_A=0, cutoff_voltage_V=4.2, taper_current_A=0.1)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_zero_power_rejected(self):
        """Zero power is physically meaningless."""
        proto = Protocol.power(power_W=0, duration_s=3600)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_negative_cutoff_voltage_cccv_rejected(self):
        proto = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=-4.2, taper_current_A=0.1)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_taper_current_above_charge_current_rejected(self):
        proto = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=4.2, taper_current_A=1.1)
        with pytest.raises(ProtocolValidationError):
            proto.validate()

    def test_valid_power_discharge_passes(self):
        """Positive power = discharge."""
        proto = Protocol.power(power_W=10.0, duration_s=3600)
        proto.validate()

    def test_valid_power_charge_passes(self):
        """Negative power = charge."""
        proto = Protocol.power(power_W=-5.0, duration_s=1800)
        proto.validate()


class TestProtocolCombination:
    """Protocol.__add__ merges step lists."""

    def test_add_merges_steps(self):
        p1 = Protocol.cc(current_A=1.0, duration_s=60)
        p2 = Protocol.rest(duration_s=300)
        combined = p1 + p2
        assert len(combined.steps) == 2
        assert isinstance(combined.steps[0], ConstantCurrent)
        assert isinstance(combined.steps[1], Rest)

    def test_total_duration_sums_steps(self):
        p = Protocol.cc(current_A=1.0, duration_s=60) + Protocol.rest(duration_s=300)
        assert p.total_duration_s() == 360.0

    def test_total_duration_skips_undefined(self):
        """CC_CV steps have no fixed duration — total_duration_s() skips them."""
        cc = Protocol.cc(current_A=1.0, duration_s=60)
        cccv = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=4.2, taper_current_A=0.1)
        combined = cc + cccv
        # CC_CV.duration_s() returns None → skipped, only CC counted
        assert combined.total_duration_s() == 60.0

    def test_power_composition(self):
        """PowerStep can be composed with other protocols."""
        p = Protocol.power(power_W=10.0, duration_s=3600) + Protocol.rest(duration_s=600)
        assert len(p.steps) == 2
        assert isinstance(p.steps[0], PowerStep)
        assert isinstance(p.steps[1], Rest)
        assert p.total_duration_s() == 4200.0

    def test_cycle_definition_negative_rest_rejected(self):
        charge = Protocol.cccv(charge_current_A=1.0, cutoff_voltage_V=4.2, taper_current_A=0.1)
        discharge = Protocol.cc(current_A=-1.0, duration_s=60)
        protocol = Protocol.cycle(charge=charge, discharge=discharge, n_cycles=1, rest_s=0)
        assert protocol.cycle_definition is not None
        invalid_protocol = Protocol(
            steps=protocol.steps,
            n_cycles=protocol.n_cycles,
            cycle_definition=CycleDefinition(
                charge=protocol.cycle_definition.charge,
                discharge=protocol.cycle_definition.discharge,
                rest_after_charge_s=-1.0,
                rest_after_discharge_s=protocol.cycle_definition.rest_after_discharge_s,
            ),
        )

        with pytest.raises(ProtocolValidationError):
            invalid_protocol.validate()


# ============================================================================
# Drive Cycles
# ============================================================================

class TestDriveCycleProfiles:
    """DriveCycleProfile creation and lookup."""

    def test_list_drive_cycles_not_empty(self):
        cycles = list_drive_cycles()
        assert isinstance(cycles, list)
        assert len(cycles) > 0
        assert all(isinstance(name, str) for name in cycles)

    def test_wltp_in_registry(self):
        cycles = list_drive_cycles()
        assert "WLTP" in cycles or "WLTP_CLASS3" in cycles

    def test_get_drive_cycle_wltp(self):
        profile = get_drive_cycle("WLTP")
        assert isinstance(profile, DriveCycleProfile)
        assert profile.name == "WLTP Class 3"
        assert len(profile.time_s) >= 2
        assert len(profile.power_normalized) == len(profile.time_s)

    def test_get_drive_cycle_us06(self):
        profile = get_drive_cycle("US06")
        assert isinstance(profile, DriveCycleProfile)
        assert profile.name == "US06"
        assert len(profile.time_s) >= 2

    def test_get_drive_cycle_udds(self):
        profile = get_drive_cycle("UDDS")
        assert isinstance(profile, DriveCycleProfile)
        assert profile.name == "UDDS"
        assert len(profile.time_s) >= 2

    def test_get_drive_cycle_case_insensitive(self):
        """Lookup should be case-insensitive."""
        profile1 = get_drive_cycle("wltp")
        profile2 = get_drive_cycle("WLTP")
        assert profile1.name == profile2.name

    def test_get_drive_cycle_unknown_raises(self):
        """Unknown cycle name should raise KeyError."""
        with pytest.raises(KeyError):
            get_drive_cycle("NONEXISTENT_CYCLE")

    def test_built_in_profiles_valid(self):
        """All built-in profiles should pass validation."""
        for profile in [WLTP_CLASS3, US06, UDDS]:
            # Check monotonic time
            assert all(
                profile.time_s[i] < profile.time_s[i + 1]
                for i in range(len(profile.time_s) - 1)
            )
            # Check power in [0, 1]
            assert all(0.0 <= p <= 1.0 for p in profile.power_normalized)


class TestScaleDriveCycle:
    """Drive cycle scaling and discretization."""

    def test_scale_drive_cycle_basic(self):
        profile = get_drive_cycle("WLTP")
        segments = scale_drive_cycle(profile, peak_power_kW=150.0)
        
        assert isinstance(segments, list)
        assert len(segments) > 0
        # Should have (power_W, duration_s) tuples
        for power_W, duration_s in segments:
            assert isinstance(power_W, float)
            assert isinstance(duration_s, float)

    def test_scale_drive_cycle_power_in_watts(self):
        profile = get_drive_cycle("US06")
        segments = scale_drive_cycle(profile, peak_power_kW=100.0)
        
        # With 100 kW peak, max power should be 100,000 W
        max_power = max(abs(p) for p, _ in segments)
        assert max_power <= 100_000.0

    def test_scale_drive_cycle_duration_preserved(self):
        """Total duration should equal cycle's max time."""
        profile = get_drive_cycle("UDDS")
        segments = scale_drive_cycle(profile, peak_power_kW=150.0)
        
        total_duration = sum(duration for _, duration in segments)
        expected_duration = profile.time_s[-1] - profile.time_s[0]
        
        assert abs(total_duration - expected_duration) < 0.1

    def test_scale_with_different_peak_powers(self):
        profile = get_drive_cycle("WLTP")
        segments_100 = scale_drive_cycle(profile, peak_power_kW=100.0)
        segments_200 = scale_drive_cycle(profile, peak_power_kW=200.0)
        
        # Powers should scale proportionally
        for (p1, d1), (p2, d2) in zip(segments_100, segments_200):
            # Duration should be the same
            assert d1 == d2
            # Power should scale ~2x
            if p1 != 0:
                assert abs(p2 / p1 - 2.0) < 0.01

    def test_scale_with_vehicle_mass_relative_to_reference(self):
        profile = get_drive_cycle("WLTP")

        reference = scale_drive_cycle(profile, vehicle_mass_kg=1800.0)
        lighter = scale_drive_cycle(profile, vehicle_mass_kg=900.0)

        for (reference_power, _), (lighter_power, _) in zip(reference, lighter):
            assert lighter_power == pytest.approx(reference_power * 0.5)

    def test_scale_rejects_non_positive_vehicle_inputs(self):
        profile = get_drive_cycle("WLTP")

        with pytest.raises(ValueError, match="vehicle_mass_kg"):
            scale_drive_cycle(profile, vehicle_mass_kg=0.0)
        with pytest.raises(ValueError, match="peak_power_kW"):
            scale_drive_cycle(profile, peak_power_kW=0.0)


class TestDriveProfile:
    """DriveProfile step creation and validation."""

    def test_drive_profile_creates_basic(self):
        segments = [(10_000, 60), (15_000, 120)]
        profile = DriveProfile(segments=segments, cycle_name="test")
        
        assert len(profile.segments) == 2
        assert profile.cycle_name == "test"

    def test_drive_profile_duration_s(self):
        segments = [(10_000, 60), (15_000, 120)]
        profile = DriveProfile(segments=segments)
        
        assert profile.duration_s() == 180.0

    def test_drive_profile_empty_segments_rejected(self):
        """Empty segments list should be rejected."""
        with pytest.raises(ProtocolValidationError):
            DriveProfile(segments=[], cycle_name="empty")

    def test_protocol_drive_cycle_wltp_creates_protocol(self):
        """Protocol.drive_cycle() should create a valid protocol."""
        protocol = Protocol.drive_cycle("WLTP")
        
        assert len(protocol.steps) == 1
        assert isinstance(protocol.steps[0], DriveProfile)
        
        # Should have many segments (one per time interval in WLTP)
        drive_profile = protocol.steps[0]
        assert len(drive_profile.segments) > 10

    def test_protocol_drive_cycle_us06_with_custom_power(self):
        """Protocol.drive_cycle() should scale by peak power."""
        protocol = Protocol.drive_cycle(
            "US06",
            vehicle_mass_kg=1600,
            peak_power_kW=200.0
        )
        
        drive_profile = protocol.steps[0]
        max_power = max(abs(p) for p, _ in drive_profile.segments)
        
        # Max power should be ~200 kW
        assert max_power <= 200_000.0

    def test_protocol_drive_cycle_unknown_raises(self):
        """Unknown cycle name should raise KeyError."""
        with pytest.raises(KeyError):
            Protocol.drive_cycle("INVALID_CYCLE")

    def test_drive_profile_composition_with_rest(self):
        """DriveProfile can be composed with Rest steps."""
        protocol = Protocol.drive_cycle("UDDS") + Protocol.rest(600)
        
        assert len(protocol.steps) == 2
        assert isinstance(protocol.steps[0], DriveProfile)
        assert isinstance(protocol.steps[1], Rest)

    def test_drive_profile_total_duration(self):
        """Protocol.total_duration_s() should work for DriveProfile."""
        protocol = Protocol.drive_cycle("US06") + Protocol.rest(300)
        total_duration = protocol.total_duration_s()
        
        # US06 is ~600s + rest 300s = 900s
        assert 800 < total_duration < 1000

    def test_protocol_drive_cycle_validates(self):
        """Drive cycle protocol should pass validation."""
        protocol = Protocol.drive_cycle("WLTP")
        protocol.validate()  # Should not raise


# ============================================================================
# Environment
# ============================================================================

class TestEnvironmentValidation:

    def test_valid_temperature_passes(self):
        env = Environment(temperature_C=25.0)
        env.validate()

    def test_too_cold_rejected(self):
        env = Environment(temperature_C=-50)
        with pytest.raises(EnvironmentValidationError):
            env.validate()

    def test_too_hot_rejected(self):
        env = Environment(temperature_C=110)
        with pytest.raises(EnvironmentValidationError):
            env.validate()

    def test_initial_cell_temperature_is_validated_independently(self):
        env = Environment(temperature_C=25.0, initial_temperature_C=120.0)
        with pytest.raises(EnvironmentValidationError, match="Initial cell"):
            env.validate()

    def test_boundary_cold_accepted(self):
        """Exactly -40°C is the lower bound — should be accepted."""
        env = Environment(temperature_C=-40.0)
        env.validate()

    def test_boundary_hot_accepted(self):
        """Exactly 100°C is the upper bound — should be accepted."""
        env = Environment(temperature_C=100.0)
        env.validate()

    def test_valid_thermal_model_lumped(self):
        env = Environment(temperature_C=25.0, thermal_model="lumped")
        env.validate()

    def test_valid_thermal_model_x_full(self):
        env = Environment(temperature_C=25.0, thermal_model="x-full")
        env.validate()

    def test_invalid_thermal_model_rejected(self):
        env = Environment(temperature_C=25.0, thermal_model="invalid")
        with pytest.raises(EnvironmentValidationError):
            env.validate()

    def test_convection_without_thermal_model_backward_compat(self):
        """Setting convection but no explicit thermal_model should be accepted."""
        env = Environment(temperature_C=25.0, convection_W_per_m2K=10.0)
        env.validate()
        assert env.thermal_model is None  # stays None; backend auto-promotes


class TestEnvironmentAlias:
    """ambient_temperature_C is a legacy alias for temperature_C."""

    def test_alias_constructor(self):
        env = Environment(ambient_temperature_C=25.0)
        assert env.temperature_C == 25.0

    def test_alias_property_same_value(self):
        env = Environment(temperature_C=30.0)
        assert env.ambient_temperature_C == env.temperature_C

    def test_initial_temperature_defaults_to_ambient(self):
        env = Environment(ambient_temperature_C=12.0)
        assert env.initial_temperature_C == 12.0

    def test_initial_temperature_can_differ_from_ambient(self):
        env = Environment(
            ambient_temperature_C=5.0,
            initial_temperature_C=25.0,
        )
        env.validate()
        assert env.ambient_temperature_C == 5.0
        assert env.initial_temperature_C == 25.0

    def test_missing_temperature_raises(self):
        with pytest.raises(TypeError):
            Environment()


# ============================================================================
# SolverConfig
# ============================================================================

class TestSolverConfigValidation:

    def test_defaults_valid(self):
        cfg = SolverConfig()
        cfg.validate()

    def test_negative_initial_soc_rejected(self):
        cfg = SolverConfig(initial_soc=-0.1)
        with pytest.raises(SolverValidationError):
            cfg.validate()

    def test_soc_above_one_rejected(self):
        cfg = SolverConfig(initial_soc=1.5)
        with pytest.raises(SolverValidationError):
            cfg.validate()

    def test_negative_rtol_rejected(self):
        cfg = SolverConfig(rtol=-1e-6)
        with pytest.raises(SolverValidationError):
            cfg.validate()

    def test_negative_atol_rejected(self):
        cfg = SolverConfig(atol=-1e-9)
        with pytest.raises(SolverValidationError):
            cfg.validate()

    def test_soc_boundary_zero_accepted(self):
        """SOC=0 means fully discharged — valid."""
        cfg = SolverConfig(initial_soc=0.0)
        cfg.validate()

    def test_soc_boundary_one_accepted(self):
        cfg = SolverConfig(initial_soc=1.0)
        cfg.validate()

    # LEARNING: SolverConfig.validate() checks rtol < 0 (not rtol <= 0).
    # The error message says "strictly positive" but rtol=0 passes.
    # This is a known boundary inconsistency; not fixed here to stay in scope.


# ============================================================================
# Model
# ============================================================================

class TestModelEnum:

    def test_spm_value(self):
        assert Model.SPM == "single_particle"
        assert Model.SPM.value == "single_particle"

    def test_from_value_case_insensitive(self):
        assert Model.from_value("spm") is Model.SPM
        assert Model.from_value("SPM") is Model.SPM

    def test_from_value_typo_tolerance(self):
        """French-style spelling 'particule' is aliased."""
        assert Model.from_value("single_particule") is Model.SPM

    def test_from_value_unknown_raises(self):
        with pytest.raises(ValueError):
            Model.from_value("unknown_model")

    def test_from_value_all_aliases(self):
        assert Model.from_value("spme") is Model.SPMe
        assert Model.from_value("dfn") is Model.DFN
        assert Model.from_value("doyle_fuller_newman") is Model.DFN

    def test_label_property(self):
        assert "Single Particle" in Model.SPM.label


# ============================================================================
# Simulation (composite validation)
# ============================================================================

class TestSimulationValidation:

    def _make_valid_simulation(self) -> Simulation:
        return Simulation(
            cell=Cell.preset("LFP_5AH"),
            model=Model.SPM,
            protocol=Protocol.cc(current_A=1.0, duration_s=60),
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(),
        )

    def test_valid_simulation_passes(self):
        sim = self._make_valid_simulation()
        sim.validate()

    def test_invalid_cell_propagates(self):
        """Simulation.validate() calls cell.validate() — error propagates."""
        sim = Simulation(
            cell=Cell(chemistry="LFP", nominal_capacity_Ah=-1.0),
            model=Model.SPM,
            protocol=Protocol.cc(current_A=1.0, duration_s=60),
            environment=Environment(temperature_C=25.0),
        )
        with pytest.raises(CellValidationError):
            sim.validate()

    def test_invalid_protocol_propagates(self):
        sim = Simulation(
            cell=Cell(chemistry="LFP"),
            model=Model.SPM,
            protocol=Protocol(steps=[]),
            environment=Environment(temperature_C=25.0),
        )
        with pytest.raises(ProtocolValidationError):
            sim.validate()

    def test_invalid_environment_propagates(self):
        sim = Simulation(
            cell=Cell(chemistry="LFP"),
            model=Model.SPM,
            protocol=Protocol.cc(current_A=1.0, duration_s=60),
            environment=Environment(temperature_C=-50),
        )
        with pytest.raises(EnvironmentValidationError):
            sim.validate()

    def test_invalid_solver_propagates(self):
        sim = Simulation(
            cell=Cell(chemistry="LFP"),
            model=Model.SPM,
            protocol=Protocol.cc(current_A=1.0, duration_s=60),
            environment=Environment(temperature_C=25.0),
            solver_config=SolverConfig(initial_soc=-0.5),
        )
        with pytest.raises(SolverValidationError):
            sim.validate()


# ============================================================================
# Deep Electrochemical Observability Signals
# ============================================================================

class TestElectrochemicalSignals:
    """Verify Phase B electrochemical observability signals are registered."""

    PHASE_B_SIGNALS = [
        Signal.NEGATIVE_PARTICLE_SURFACE_CONCENTRATION,
        Signal.POSITIVE_PARTICLE_SURFACE_CONCENTRATION,
        Signal.NEGATIVE_OCV,
        Signal.POSITIVE_OCV,
        Signal.NEGATIVE_REACTION_OVERPOTENTIAL,
        Signal.POSITIVE_REACTION_OVERPOTENTIAL,
        Signal.NEGATIVE_EXCHANGE_CURRENT_DENSITY,
        Signal.POSITIVE_EXCHANGE_CURRENT_DENSITY,
        Signal.ELECTROLYTE_POTENTIAL,
        Signal.NEGATIVE_STOICHIOMETRY,
        Signal.POSITIVE_STOICHIOMETRY,
        Signal.NEGATIVE_SOLID_POTENTIAL,
        Signal.POSITIVE_SOLID_POTENTIAL,
    ]

    def test_all_signals_exist_and_have_unique_values(self):
        """Every Phase B signal is a valid enum member with a unique string value."""
        values = [s.value for s in self.PHASE_B_SIGNALS]
        assert len(values) == len(set(values)), "Duplicate signal values detected"

    def test_all_signals_in_pybamm_signal_map(self):
        """Every Phase B signal has a corresponding entry in PYBAMM_SIGNAL_MAP."""
        for signal in self.PHASE_B_SIGNALS:
            assert signal in PYBAMM_SIGNAL_MAP, (
                f"{signal.name} missing from PYBAMM_SIGNAL_MAP"
            )


# ============================================================================
# Thermal Signals — Phase A
# ============================================================================

class TestThermalSignals:
    """Verify Phase A thermal signals are registered."""

    PHASE_A_SIGNALS = [
        Signal.HEAT_GENERATION,
        Signal.IRREVERSIBLE_HEAT,
        Signal.REVERSIBLE_HEAT,
        Signal.OHMIC_HEAT,
        Signal.CELL_TEMPERATURE,
    ]

    def test_all_thermal_signals_unique(self):
        """Every Phase A thermal signal has a unique string value."""
        values = [s.value for s in self.PHASE_A_SIGNALS]
        assert len(values) == len(set(values)), "Duplicate thermal signal values"

    def test_all_thermal_signals_in_pybamm_signal_map(self):
        """Every Phase A thermal signal maps to PyBaMM."""
        for signal in self.PHASE_A_SIGNALS:
            assert signal in PYBAMM_SIGNAL_MAP, (
                f"{signal.name} missing from PYBAMM_SIGNAL_MAP"
            )


# ============================================================================
# Degradation Signals — Phase C
# ============================================================================

class TestDegradationSignals:
    """Verify Phase C degradation signals are registered."""

    from battery_sim.infrastructure.pybamm.pybamm_signal import DERIVED_SIGNALS

    PHASE_C_SIGNALS = [
        Signal.SEI_THICKNESS,
        Signal.SEI_FILM_RESISTANCE,
        Signal.LITHIUM_PLATING_CAPACITY,
        Signal.LITHIUM_PLATING_THICKNESS,
        Signal.LOSS_OF_ACTIVE_MATERIAL,
        Signal.TOTAL_CAPACITY_LOSS,
        Signal.NEGATIVE_PARTICLE_CRACK_LENGTH,
    ]

    PHASE_C_CYCLING_SIGNALS = [
        Signal.CYCLE_DISCHARGE_CAPACITY,
        Signal.CYCLE_CHARGE_CAPACITY,
        Signal.CYCLE_COULOMBIC_EFFICIENCY,
        Signal.CYCLE_CAPACITY_RETENTION,
    ]

    def test_all_degradation_signals_unique(self):
        """Every Phase C degradation signal has a unique string value."""
        values = [s.value for s in self.PHASE_C_SIGNALS]
        assert len(values) == len(set(values)), "Duplicate degradation signal values"

    def test_all_degradation_signals_in_pybamm_signal_map(self):
        """Every Phase C degradation signal maps to PyBaMM."""
        for signal in self.PHASE_C_SIGNALS:
            assert signal in PYBAMM_SIGNAL_MAP, (
                f"{signal.name} missing from PYBAMM_SIGNAL_MAP"
            )

    def test_all_cycling_signals_are_derived(self):
        """Cycling signals are derived (not in PYBAMM_SIGNAL_MAP)."""
        for signal in self.PHASE_C_CYCLING_SIGNALS:
            assert signal in self.DERIVED_SIGNALS, (
                f"{signal.name} missing from DERIVED_SIGNALS"
            )


# ============================================================================
# Degradation Config — Phase C
# ============================================================================

class TestDegradationConfig:
    """DegradationConfig resolve/validate logic (no PyBaMM needed)."""

    def test_legacy_sei_resolves_to_ec_reaction_limited(self):
        """Backward compat: sei_growth=True resolves to 'ec reaction limited'."""
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(sei_growth=True)
        resolved = cfg.resolve()
        assert resolved.sei == "ec reaction limited"

    def test_legacy_plating_resolves_to_irreversible(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(lithium_plating=True)
        resolved = cfg.resolve()
        assert resolved.lithium_plating == "irreversible"

    def test_legacy_am_loss_resolves_to_stress_driven(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(active_material_loss=True)
        resolved = cfg.resolve()
        assert resolved.am_loss == "stress-driven"

    def test_explicit_sei_model_resolves(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(sei_model="solvent-diffusion limited")
        resolved = cfg.resolve()
        assert resolved.sei == "solvent-diffusion limited"

    def test_explicit_model_overrides_boolean(self):
        """When both sei_model and sei_growth are set, explicit model wins."""
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(sei_model="ec reaction limited", sei_growth=True)
        resolved = cfg.resolve()
        assert resolved.sei == "ec reaction limited"

    def test_invalid_sei_model_raises(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(sei_model="invalid")
        with pytest.raises(ValueError, match="Invalid SEI model"):
            cfg.validate()

    def test_invalid_plating_model_raises(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(lithium_plating_model="invalid")
        with pytest.raises(ValueError, match="Invalid lithium plating model"):
            cfg.validate()

    def test_invalid_am_loss_model_raises(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(am_loss_model="invalid")
        with pytest.raises(ValueError, match="Invalid AM loss model"):
            cfg.validate()

    def test_invalid_particle_mechanics_raises(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(particle_mechanics="invalid")
        with pytest.raises(ValueError, match="Invalid particle mechanics"):
            cfg.validate()

    def test_particle_mechanics_and_sei_on_cracks_valid(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(
            particle_mechanics="swelling and cracking",
            sei_on_cracks=True,
        )
        cfg.validate()  # should not raise
        resolved = cfg.resolve()
        assert resolved.particle_mechanics == "swelling and cracking"
        assert resolved.sei_on_cracks is True

    def test_any_enabled_with_submodel(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(sei_model="reaction limited")
        assert cfg.any_enabled() is True

    def test_any_enabled_false_by_default(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig()
        assert cfg.any_enabled() is False

    def test_any_enabled_particle_mechanics(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig(particle_mechanics="swelling only")
        assert cfg.any_enabled() is True

    def test_no_degradation_resolves_to_none(self):
        from battery_sim.core.experiment import DegradationConfig
        cfg = DegradationConfig()
        resolved = cfg.resolve()
        assert resolved.sei is None
        assert resolved.lithium_plating is None
        assert resolved.am_loss is None
