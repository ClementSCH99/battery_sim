# tests/test_errors.py
"""
Unit tests for ErrorDetector and ConstraintChecker using synthetic data.

No PyBaMM dependency — we build Result objects from hand-crafted TimeSeries.

LEARNING NOTES:
- ErrorDetector performs post-simulation anomaly detection: voltage bounds,
  NaN/Inf, and divergence. It works on a Result object and returns a list
  of SimulationError value objects.
- ConstraintChecker performs pre-simulation feasibility checking: "can this
  cell + environment combination even work?". Returns ConstraintViolation
  value objects.
- Both are purely functional (static methods, no state) — easy to test.
"""
import math
import pytest

from battery_sim.types.signal import Signal
from battery_sim.types.timeseries import TimeSeries
from battery_sim.core.result import Result
from battery_sim.core.simulation_error import ErrorDetector, ErrorType, SimulationError
from battery_sim.core.investigation_tools import ConstraintChecker, ConstraintViolation
from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment


# ============================================================================
# Helper
# ============================================================================

def make_result(voltage_values=None, current_values=None, time_s=None):
    """Build a minimal Result from synthetic arrays."""
    data = {}
    if time_s is None:
        length = len(voltage_values) if voltage_values else len(current_values or [])
        time_s = list(range(length))

    if voltage_values is not None:
        data[Signal.VOLTAGE] = TimeSeries(time_s=time_s, values=voltage_values, unit="V")
    if current_values is not None:
        data[Signal.CURRENT] = TimeSeries(time_s=time_s, values=current_values, unit="A")
    return Result(data)


# ============================================================================
# ErrorDetector — voltage violations
# ============================================================================

class TestVoltageViolations:

    def test_spike_above_max(self):
        """Voltage exceeding safe upper bound triggers a violation."""
        r = make_result(voltage_values=[3.2, 3.3, 6.0, 3.1], time_s=[0, 1, 2, 3])
        errors = ErrorDetector.detect_voltage_violations(r, min_voltage_v=2.5, max_voltage_v=4.2)
        assert len(errors) >= 1
        assert any(e.error_type == ErrorType.VOLTAGE_OUT_OF_BOUNDS for e in errors)

    def test_drop_below_min(self):
        """Voltage dropping below safe lower bound triggers a violation."""
        r = make_result(voltage_values=[3.2, 1.5, 3.1], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_voltage_violations(r, min_voltage_v=2.5, max_voltage_v=4.2)
        assert len(errors) >= 1
        assert errors[0].severity == "critical"

    def test_clean_voltage_no_violations(self):
        r = make_result(voltage_values=[3.2, 3.5, 3.3], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_voltage_violations(r, min_voltage_v=2.5, max_voltage_v=4.2)
        assert len(errors) == 0

    def test_no_voltage_signal_no_violations(self):
        """If voltage signal is absent, there's nothing to check."""
        r = make_result(current_values=[1.0, 2.0])
        errors = ErrorDetector.detect_voltage_violations(r)
        assert len(errors) == 0


# ============================================================================
# ErrorDetector — numerical issues
# ============================================================================

class TestNumericalIssues:

    def test_nan_detected(self):
        """NaN in signals triggers NAN_DETECTED error."""
        r = make_result(voltage_values=[3.2, float('nan'), 3.1], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_numerical_issues(r)
        assert any(e.error_type == ErrorType.NAN_DETECTED for e in errors)

    def test_inf_detected(self):
        """Infinity in signals triggers INF_DETECTED error."""
        r = make_result(voltage_values=[3.2, float('inf'), 3.1], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_numerical_issues(r)
        assert any(e.error_type == ErrorType.INF_DETECTED for e in errors)

    def test_clean_data_no_numerical_issues(self):
        r = make_result(voltage_values=[3.2, 3.3, 3.1], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_numerical_issues(r)
        assert len(errors) == 0

    def test_nan_in_current_also_detected(self):
        """Numerical issue detection scans all signals, not just voltage."""
        r = make_result(
            voltage_values=[3.2, 3.3],
            current_values=[1.0, float('nan')],
            time_s=[0, 1],
        )
        errors = ErrorDetector.detect_numerical_issues(r)
        assert any(e.error_type == ErrorType.NAN_DETECTED for e in errors)


# ============================================================================
# ErrorDetector — divergence
# ============================================================================

class TestDivergenceDetection:

    def test_diverging_voltage_detected(self):
        """Voltage growing beyond threshold ratio triggers divergence warning."""
        r = make_result(voltage_values=[3.0, 4.0, 8.0, 15.0], time_s=[0, 1, 2, 3])
        errors = ErrorDetector.detect_divergence(r, growth_threshold=2.0)
        assert any(e.error_type == ErrorType.DIVERGENCE for e in errors)

    def test_stable_voltage_no_divergence(self):
        r = make_result(voltage_values=[3.2, 3.3, 3.2, 3.1], time_s=[0, 1, 2, 3])
        errors = ErrorDetector.detect_divergence(r)
        assert len(errors) == 0


# ============================================================================
# ErrorDetector — detect_all
# ============================================================================

class TestDetectAll:

    def test_clean_data_no_errors(self):
        r = make_result(voltage_values=[3.2, 3.3, 3.1], time_s=[0, 1, 2])
        errors = ErrorDetector.detect_all(r)
        assert len(errors) == 0

    def test_multiple_issues_aggregated(self):
        """detect_all should report both voltage violation AND NaN."""
        r = make_result(
            voltage_values=[3.2, float('nan'), 6.0],
            time_s=[0, 1, 2],
        )
        errors = ErrorDetector.detect_all(r)
        types = {e.error_type for e in errors}
        assert ErrorType.NAN_DETECTED in types
        assert ErrorType.VOLTAGE_OUT_OF_BOUNDS in types


# ============================================================================
# SimulationError value object
# ============================================================================

class TestSimulationErrorVO:
    """SimulationError is a frozen dataclass — test its methods."""

    def test_is_critical(self):
        err = SimulationError(
            error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
            severity="critical",
            message="Low voltage",
        )
        assert err.is_critical()
        assert not err.is_warning()

    def test_round_trip_dict(self):
        err = SimulationError(
            error_type=ErrorType.NAN_DETECTED,
            severity="critical",
            message="NaN in voltage",
            value=None,
        )
        d = err.to_dict()
        restored = SimulationError.from_dict(d)
        assert restored.error_type == err.error_type
        assert restored.message == err.message

    def test_summary_format(self):
        err = SimulationError(
            error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
            severity="critical",
            message="Voltage too low",
            value=-0.5,
            bounds="[2.5V, 4.2V]",
            location="at 120s",
        )
        s = err.summary()
        assert "CRITICAL" in s
        assert "-0.5" in s


# ============================================================================
# ConstraintChecker — cell feasibility
# ============================================================================

class TestConstraintCheckerCell:

    def test_valid_preset_cell_no_critical(self):
        cell = Cell.preset("LFP_5AH")
        violations = ConstraintChecker.check_cell_feasibility(cell)
        critical = [v for v in violations if v.severity == "critical" and v.violated]
        assert len(critical) == 0

    def test_negative_capacity_flagged(self):
        cell = Cell(chemistry="LFP", nominal_capacity_Ah=-1.0)
        violations = ConstraintChecker.check_cell_feasibility(cell)
        violated_names = [v.constraint_name for v in violations if v.violated]
        assert "capacity_positive" in violated_names

    def test_extreme_voltage_flagged(self):
        cell = Cell(chemistry="TEST", nominal_voltage_V=10.0)
        violations = ConstraintChecker.check_cell_feasibility(cell)
        violated_names = [v.constraint_name for v in violations if v.violated]
        assert "voltage_in_range" in violated_names

    def test_negative_resistance_flagged(self):
        cell = Cell(chemistry="TEST", internal_resistance_Ohm=-0.01)
        violations = ConstraintChecker.check_cell_feasibility(cell)
        violated_names = [v.constraint_name for v in violations if v.violated]
        assert "resistance_non_negative" in violated_names


# ============================================================================
# ConstraintChecker — protocol feasibility
# ============================================================================

class TestConstraintCheckerProtocol:

    def test_standard_conditions_feasible(self):
        """25°C with a standard cell should produce no critical violations."""
        cell = Cell.preset("LFP_5AH")
        env = Environment(temperature_C=25.0)
        violations = ConstraintChecker.check_protocol_feasibility(cell, env)
        critical = [v for v in violations if v.severity == "critical" and v.violated]
        assert len(critical) == 0

    def test_extreme_temperature_flagged(self):
        """Very hot conditions should produce a warning."""
        cell = Cell.preset("LFP_5AH")
        env = Environment(temperature_C=80.0)
        violations = ConstraintChecker.check_protocol_feasibility(cell, env)
        assert any("temperature" in v.constraint_name.lower() for v in violations)


# ============================================================================
# ConstraintChecker — feasibility report
# ============================================================================

class TestFeasibilityReport:

    def test_report_returns_string(self):
        cell = Cell.preset("LFP_5AH")
        env = Environment(temperature_C=25.0)
        report = ConstraintChecker.get_feasibility_report(cell, env)
        assert isinstance(report, str)
        assert "FEASIBILITY REPORT" in report
