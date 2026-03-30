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
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest, CC_CV, Step
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.core.model import Model
from battery_sim.core.simulation import Simulation
from battery_sim.core.exceptions import (
    CellValidationError,
    ProtocolValidationError,
    EnvironmentValidationError,
    SolverValidationError,
)
from battery_sim.types.signal import Signal
from battery_sim.backend.pybamm_signal import PYBAMM_SIGNAL_MAP


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

    def test_negative_current_cc_allowed(self):
        """Negative current = discharge. That's a valid protocol."""
        proto = Protocol.cc(current_A=-5.0, duration_s=60)
        proto.validate()

    def test_cccv_zero_charge_current_rejected(self):
        proto = Protocol.cccv(charge_current_A=0, cutoff_voltage_V=4.2, taper_current_A=0.1)
        with pytest.raises(ProtocolValidationError):
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

    from battery_sim.backend.pybamm_signal import DERIVED_SIGNALS

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
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(sei_growth=True)
        resolved = cfg.resolve()
        assert resolved.sei == "ec reaction limited"

    def test_legacy_plating_resolves_to_irreversible(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(lithium_plating=True)
        resolved = cfg.resolve()
        assert resolved.lithium_plating == "irreversible"

    def test_legacy_am_loss_resolves_to_stress_driven(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(active_material_loss=True)
        resolved = cfg.resolve()
        assert resolved.am_loss == "stress-driven"

    def test_explicit_sei_model_resolves(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(sei_model="solvent-diffusion limited")
        resolved = cfg.resolve()
        assert resolved.sei == "solvent-diffusion limited"

    def test_explicit_model_overrides_boolean(self):
        """When both sei_model and sei_growth are set, explicit model wins."""
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(sei_model="ec reaction limited", sei_growth=True)
        resolved = cfg.resolve()
        assert resolved.sei == "ec reaction limited"

    def test_invalid_sei_model_raises(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(sei_model="invalid")
        with pytest.raises(ValueError, match="Invalid SEI model"):
            cfg.validate()

    def test_invalid_plating_model_raises(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(lithium_plating_model="invalid")
        with pytest.raises(ValueError, match="Invalid lithium plating model"):
            cfg.validate()

    def test_invalid_am_loss_model_raises(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(am_loss_model="invalid")
        with pytest.raises(ValueError, match="Invalid AM loss model"):
            cfg.validate()

    def test_invalid_particle_mechanics_raises(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(particle_mechanics="invalid")
        with pytest.raises(ValueError, match="Invalid particle mechanics"):
            cfg.validate()

    def test_particle_mechanics_and_sei_on_cracks_valid(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(
            particle_mechanics="swelling and cracking",
            sei_on_cracks=True,
        )
        cfg.validate()  # should not raise
        resolved = cfg.resolve()
        assert resolved.particle_mechanics == "swelling and cracking"
        assert resolved.sei_on_cracks is True

    def test_any_enabled_with_submodel(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(sei_model="reaction limited")
        assert cfg.any_enabled() is True

    def test_any_enabled_false_by_default(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig()
        assert cfg.any_enabled() is False

    def test_any_enabled_particle_mechanics(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig(particle_mechanics="swelling only")
        assert cfg.any_enabled() is True

    def test_no_degradation_resolves_to_none(self):
        from battery_sim.core.degradation import DegradationConfig
        cfg = DegradationConfig()
        resolved = cfg.resolve()
        assert resolved.sei is None
        assert resolved.lithium_plating is None
        assert resolved.am_loss is None
