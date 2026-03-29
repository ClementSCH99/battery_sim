"""Integration tests for application service layer.

These tests exercise ComparisonService, SensitivityService,
BatchExecutionService, and ParameterSweep with real PyBaMM execution.

LEARNING NOTES (for future readers):
- All tests use SHORT protocols (60 s) for speed. Real investigations
  use longer durations but test correctness doesn't require them.
- Each service is constructed with its own backend instance via the
  module-scoped `backend` fixture to avoid cross-test state.
- @pytest.mark.slow lets you skip these during fast iteration:
      pytest -m "not slow"

Coverage map (what's tested and why):
  ComparisonService   → metric extraction, relative_to_first, multi-preset
  SensitivityService  → coefficient computation, interpretation labels
  BatchExecutionService → preset batching, parameter variations
  ParameterSweep      → cell sweep, environment sweep, SweepResult shape
"""
import math
import pytest

from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.core.application_services import (
    BatchExecutionService,
    ComparisonService,
    ParameterSweepService,
    SensitivityResult,
    SensitivityService,
    SimulationExecutionService,
)
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.investigation_tools import BatchSimulationConfig
from battery_sim.core.model import Model
from battery_sim.core.parameter_sweep import ParameterSweep, SweepResult
from battery_sim.core.protocol import Protocol, ConstantCurrent
from battery_sim.core.simulation import Simulation
from battery_sim.core.simulation_run import SimulationRun
from battery_sim.core.solver import SolverConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def backend():
    """Shared PyBaMM backend — expensive to create, reused across tests."""
    return PyBaMMBackend()


@pytest.fixture(scope="module")
def short_config(backend):
    """BatchSimulationConfig with a 60-second CC discharge."""
    return BatchSimulationConfig(
        protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        environment=Environment(temperature_C=25.0),
        model=Model.SPM,
        solver_config=SolverConfig(),
        backend=backend,
    )


@pytest.fixture(scope="module")
def baseline_simulation():
    """A minimal Simulation object for sweep/sensitivity tests."""
    return Simulation(
        cell=Cell.preset("LFP_5AH"),
        model=Model.SPM,
        protocol=Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=60),
        ]),
        environment=Environment(temperature_C=25.0),
        solver_config=SolverConfig(),
    )


# ===========================================================================
# ComparisonService
# ===========================================================================

@pytest.mark.slow
class TestComparisonService:
    """Verify metric extraction and comparison logic with real simulations."""

    def test_compare_three_chemistries(self, backend, short_config):
        """Compare LFP, NMC, NCA — verify metric structure for 3+ presets.

        LEARNING: ComparisonService.compare_presets returns a dict with
        'scenarios' and 'metrics' keys.  Each metric entry contains 'values'
        (per-scenario) and optional 'relative_to_first' percentages.
        """
        service = ComparisonService(backend=backend)
        result = service.compare_presets(
            ["LFP_5AH", "NMC_5AH", "NCA_5AH"], short_config,
        )

        assert "metrics" in result, "comparison result missing 'metrics'"
        assert "scenarios" in result
        assert set(result["scenarios"]) == {"LFP_5AH", "NMC_5AH", "NCA_5AH"}

        # Every expected metric should have per-scenario values
        for metric_name, metric_data in result["metrics"].items():
            assert "values" in metric_data, f"metric '{metric_name}' has no 'values'"

    def test_comparison_metrics_are_numeric(self, backend, short_config):
        """All extracted numeric metrics should be finite numbers or None.

        LEARNING: extract_metrics may return None for metrics that cannot
        be computed (e.g. efficiency on a very short simulation).  We accept
        None but reject NaN or Inf — those would indicate a backend bug.
        """
        service = ComparisonService(backend=backend)
        result = service.compare_presets(["LFP_5AH", "NMC_5AH"], short_config)

        for metric_name, metric_data in result["metrics"].items():
            if metric_data.get("type") != "numeric":
                continue
            for scenario, value in metric_data["values"].items():
                assert value is None or (
                    isinstance(value, (int, float)) and math.isfinite(value)
                ), (
                    f"metric '{metric_name}' for '{scenario}' is not a finite "
                    f"number: {value!r}"
                )

    def test_relative_to_first_present(self, backend, short_config):
        """Numeric metrics with a nonzero baseline include relative_to_first.

        LEARNING: relative_to_first shows the percentage change of each
        scenario compared to the first one listed.  It's only computed when
        the baseline value is nonzero.
        """
        service = ComparisonService(backend=backend)
        result = service.compare_presets(["LFP_5AH", "NMC_5AH"], short_config)

        has_relative = False
        for metric_data in result["metrics"].values():
            if "relative_to_first" in metric_data:
                has_relative = True
                for pct in metric_data["relative_to_first"].values():
                    assert isinstance(pct, (int, float))
        assert has_relative, "Expected at least one metric with relative_to_first"


# ===========================================================================
# SensitivityService
# ===========================================================================

@pytest.mark.slow
class TestSensitivityService:
    """Verify sensitivity analysis produces meaningful coefficients."""

    def test_sensitivity_temperature(self, backend, short_config):
        """Sensitivity on temperature returns a valid SensitivityResult.

        LEARNING: SensitivityService.analyze_single_parameter requires a
        metric_extractor callable.  We use peak_power here because it is
        reliably available even for short simulations.
        """
        service = SensitivityService(backend=backend)
        cell = Cell.preset("LFP_5AH")

        def peak_power_extractor(run: SimulationRun) -> float:
            try:
                return float(run.result.peak_power() or 0.0)
            except Exception:
                return 0.0

        result = service.analyze_single_parameter(
            cell,
            "temperature_C",
            [10.0, 25.0, 40.0],
            short_config,
            peak_power_extractor,
        )

        assert isinstance(result, SensitivityResult)
        assert result.parameter_name == "temperature_C"
        assert len(result.parameter_values) == 3
        assert len(result.metric_values) == 3
        assert result.sensitivity_coefficient is not None
        assert math.isfinite(result.sensitivity_coefficient)

    def test_sensitivity_interpretation(self, backend, short_config):
        """SensitivityResult.interpretation() returns a recognised category.

        LEARNING: The interpretation labels are fixed strings defined in
        application_services.SensitivityResult.  They map coefficient
        ranges to human-friendly severity bands.
        """
        service = SensitivityService(backend=backend)
        cell = Cell.preset("LFP_5AH")

        def peak_power_extractor(run: SimulationRun) -> float:
            try:
                return float(run.result.peak_power() or 0.0)
            except Exception:
                return 0.0

        result = service.analyze_single_parameter(
            cell,
            "temperature_C",
            [10.0, 25.0, 40.0],
            short_config,
            peak_power_extractor,
        )

        interpretation = result.interpretation()
        valid_labels = {
            "VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH",
        }
        assert any(label in interpretation for label in valid_labels), (
            f"Unexpected interpretation: {interpretation!r}"
        )


# ===========================================================================
# BatchExecutionService
# ===========================================================================

@pytest.mark.slow
class TestBatchExecutionService:
    """Verify batch preset and parameter-variation execution."""

    def test_batch_presets(self, backend, short_config):
        """Run multiple presets and verify all return SimulationRun.

        LEARNING: run_presets returns List[Tuple[str, Optional[SimulationRun]]].
        On failure a tuple of (name, None) is returned instead of raising.
        """
        service = BatchExecutionService(backend=backend)
        results = service.run_presets(["LFP_5AH", "NMC_5AH"], short_config)

        assert len(results) == 2
        for name, run in results:
            assert isinstance(name, str)
            assert isinstance(run, SimulationRun), (
                f"Preset '{name}' did not produce a SimulationRun"
            )
            assert run.metadata is not None
            assert run.metadata.success

    def test_batch_parameter_variations(self, backend, short_config):
        """Vary nominal_capacity_Ah across values and verify runs.

        LEARNING: run_parameter_variations delegates to ParameterSweepService
        internally.  The returned list is [(value, Optional[SimulationRun])].
        """
        service = BatchExecutionService(backend=backend)
        baseline_cell = Cell.preset("LFP_5AH")

        results = service.run_parameter_variations(
            baseline_cell,
            "nominal_capacity_Ah",
            [3.0, 5.0, 7.0],
            short_config,
        )

        assert len(results) == 3
        for value, run in results:
            assert isinstance(value, (int, float))
            assert isinstance(run, SimulationRun), (
                f"Variation {value} did not produce a SimulationRun"
            )


# ===========================================================================
# ParameterSweep (core/parameter_sweep.py)
# ===========================================================================

@pytest.mark.slow
class TestParameterSweep:
    """Verify ParameterSweep wrapper produces correct SweepResult objects."""

    def test_sweep_cell_parameter(self, backend, baseline_simulation):
        """Sweep nominal_capacity_Ah and verify SweepResult structure.

        LEARNING: ParameterSweep wraps ParameterSweepService and returns
        typed SweepResult objects (not raw tuples), which include the
        ParameterOverride for reproducibility.
        """
        sweep = ParameterSweep(backend)
        results = sweep.sweep_cell_parameter(
            baseline_simulation,
            "nominal_capacity_Ah",
            [3.0, 5.0, 7.0],
        )

        assert len(results) == 3
        for r in results:
            assert isinstance(r, SweepResult)
            assert r.parameter_name == "nominal_capacity_Ah"
            assert r.parameter_value in [3.0, 5.0, 7.0]
            assert isinstance(r.simulation_result, SimulationRun)
            assert r.override.cell_parameters.get("nominal_capacity_Ah") == r.parameter_value

    def test_sweep_environment_parameter(self, backend, baseline_simulation):
        """Sweep temperature and verify results.

        LEARNING: Environment sweeps set override.environment_parameters
        rather than cell_parameters.
        """
        sweep = ParameterSweep(backend)
        results = sweep.sweep_environment_parameter(
            baseline_simulation,
            "temperature_C",
            [10.0, 25.0, 40.0],
        )

        assert len(results) == 3
        for r in results:
            assert isinstance(r, SweepResult)
            assert r.parameter_name == "temperature_C"
            assert isinstance(r.simulation_result, SimulationRun)
            assert r.override.environment_parameters.get("temperature_C") == r.parameter_value
