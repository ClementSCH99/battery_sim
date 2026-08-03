"""Scientific-contract tests for measured trace handling and alignment."""

from types import SimpleNamespace

import pytest

from battery_sim.core.result import Result
from battery_sim.core.services.test_comparison import TraceComparisonService
from battery_sim.core.test_trace import CellTestTrace
from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries


def _run(time_s, voltage_V, current_A=None):
    data = {
        Signal.VOLTAGE: TimeSeries(list(time_s), list(voltage_V), "V"),
    }
    if current_A is not None:
        data[Signal.CURRENT] = TimeSeries(list(time_s), list(current_A), "A")
    return SimpleNamespace(result=Result(data))


def test_trace_requires_source_and_strictly_increasing_finite_time():
    with pytest.raises(ValueError, match="source"):
        CellTestTrace.from_raw(source="", time_s=[0, 1], voltage_V=[4.0, 3.9])
    with pytest.raises(ValueError, match="strictly increasing"):
        CellTestTrace.from_raw(source="cycler", time_s=[0, 0], voltage_V=[4.0, 3.9])
    with pytest.raises(ValueError, match="finite"):
        CellTestTrace.from_raw(source="cycler", time_s=[0, 1], voltage_V=[4.0, float("nan")])


def test_trace_sample_limit_is_part_of_the_canonical_contract():
    samples = list(range(CellTestTrace.MAX_SAMPLES + 1))

    with pytest.raises(ValueError, match="limited"):
        CellTestTrace.from_raw(
            source="cycler",
            time_s=samples,
            voltage_V=[4.0] * len(samples),
        )


def test_negative_discharge_current_is_converted_to_canonical_positive_sign():
    trace = CellTestTrace.from_raw(
        source="cycler export",
        time_s=[10, 11],
        voltage_V=[4.0, 3.9],
        current_A=[-2.0, -2.0],
        current_sign_convention="discharge_negative",
    )

    assert trace.current_A == (2.0, 2.0)
    assert trace.elapsed_time_s == (0.0, 1.0)
    assert trace.provenance()["time_origin_normalized"] is True


def test_exact_voltage_and_current_match_has_zero_residual():
    run = _run([0, 1, 2], [4.1, 4.0, 3.9], [2.0, 2.0, 2.0])
    trace = CellTestTrace.from_raw(
        source="test bench A",
        test_id="T-001",
        time_s=[100, 101, 102],
        voltage_V=[4.1, 4.0, 3.9],
        current_A=[-2.0, -2.0, -2.0],
        current_sign_convention="discharge_negative",
    )

    comparison = TraceComparisonService().compare(run, trace)

    assert comparison.metrics["voltage_rmse_V"] == pytest.approx(0.0)
    assert comparison.metrics["current_rmse_A"] == pytest.approx(0.0)
    assert comparison.coverage["status"] == "complete"
    assert comparison.coverage["extrapolation_used"] is False


def test_voltage_residual_is_simulation_minus_measurement():
    run = _run([0, 1, 2], [4.2, 4.1, 4.0])
    trace = CellTestTrace.from_raw(
        source="test bench A",
        time_s=[0, 1, 2],
        voltage_V=[4.1, 4.0, 3.9],
    )

    comparison = TraceComparisonService().compare(run, trace)

    assert comparison.metrics["voltage_bias_V"] == pytest.approx(0.1)
    assert comparison.metrics["voltage_rmse_V"] == pytest.approx(0.1)


def test_early_simulation_termination_produces_partial_coverage_without_extrapolation():
    run = _run([0, 5], [4.1, 3.8])
    trace = CellTestTrace.from_raw(
        source="test bench A",
        time_s=[0, 5, 10],
        voltage_V=[4.1, 3.8, 3.6],
    )

    comparison = TraceComparisonService().compare(run, trace)

    assert comparison.coverage["status"] == "partial"
    assert comparison.coverage["test_duration_fraction"] == pytest.approx(0.5)
    assert comparison.coverage["compared_samples"] == 2
    assert len(comparison.aligned_trace["time_s"]) == 2
    assert comparison.warnings
