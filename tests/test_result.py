# tests/test_result.py
"""
Unit tests for Result metric calculations using synthetic data.

No PyBaMM dependency — we build Result objects from hand-crafted TimeSeries.

LEARNING NOTES:
- Result wraps a Dict[Signal, TimeSeries] and provides convenience accessors
  like .voltage(), .current(), etc. that return Optional[TimeSeries].
- Analysis methods (.min_voltage(), .total_energy_Wh(), …) return
  Optional[float] — None when the required signal is absent.
- This pattern allows callers to safely chain: if result.voltage() is not None.
"""
import math
import pytest
import numpy as np

from battery_sim.core.result import Signal
from battery_sim.core.result import TimeSeries
from battery_sim.core.result import Result


# ============================================================================
# Helper
# ============================================================================

def make_result(
    voltage_values=None,
    current_values=None,
    time_s=None,
    power_values=None,
    energy_values=None,
    soc_values=None,
    extra_signals=None,
):
    """Build a Result from synthetic arrays.

    Only signals whose values are provided are included — this lets tests
    exercise the 'signal missing' branches as well.
    """
    data = {}
    if time_s is None:
        # Derive a default time axis from the first non-None signal
        length = 0
        for v in (voltage_values, current_values, power_values, energy_values, soc_values):
            if v is not None:
                length = len(v)
                break
        time_s = list(range(length))

    if voltage_values is not None:
        data[Signal.VOLTAGE] = TimeSeries(time_s=time_s, values=voltage_values, unit="V")
    if current_values is not None:
        data[Signal.CURRENT] = TimeSeries(time_s=time_s, values=current_values, unit="A")
    if power_values is not None:
        data[Signal.POWER] = TimeSeries(time_s=time_s, values=power_values, unit="W")
    if energy_values is not None:
        data[Signal.ENERGY] = TimeSeries(time_s=time_s, values=energy_values, unit="Wh")
    if soc_values is not None:
        data[Signal.SOC] = TimeSeries(time_s=time_s, values=soc_values, unit="%")
    if extra_signals:
        data.update(extra_signals)
    return Result(data)


# ============================================================================
# Convenience accessors
# ============================================================================

class TestResultAccessors:

    def test_voltage_returns_timeseries(self):
        r = make_result(voltage_values=[3.2, 3.3, 3.1])
        ts = r.voltage()
        assert ts is not None
        assert ts.values == [3.2, 3.3, 3.1]

    def test_current_returns_timeseries(self):
        r = make_result(current_values=[1.0, 1.0, 1.0])
        assert r.current() is not None

    def test_missing_signal_returns_none(self):
        r = make_result(voltage_values=[3.3])
        assert r.current() is None
        assert r.power() is None
        assert r.temperature() is None

    def test_available_signals(self):
        r = make_result(voltage_values=[3.2], current_values=[1.0])
        sigs = r.available_signals()
        assert Signal.VOLTAGE in sigs
        assert Signal.CURRENT in sigs
        assert Signal.POWER not in sigs


# ============================================================================
# Analysis methods
# ============================================================================

class TestResultMetrics:

    def test_min_voltage(self):
        r = make_result(voltage_values=[3.5, 3.2, 3.8])
        assert r.min_voltage() == pytest.approx(3.2)

    def test_max_voltage(self):
        r = make_result(voltage_values=[3.5, 3.2, 3.8])
        assert r.max_voltage() == pytest.approx(3.8)

    def test_peak_current(self):
        """peak_current returns max(|I|), so negative currents count."""
        r = make_result(current_values=[1.0, -5.0, 2.0])
        assert r.peak_current() == pytest.approx(5.0)

    def test_peak_current_all_positive(self):
        r = make_result(current_values=[1.0, 3.0, 2.0])
        assert r.peak_current() == pytest.approx(3.0)

    def test_total_energy_from_energy_signal(self):
        """total_energy_Wh() returns the final value of the energy signal."""
        r = make_result(energy_values=[0.0, 1.0, 2.5, 4.0])
        assert r.total_energy_Wh() == pytest.approx(4.0)

    def test_final_soc(self):
        r = make_result(soc_values=[100.0, 80.0, 60.0])
        assert r.final_soc() == pytest.approx(60.0)


# ============================================================================
# Missing signals → None, not crashes
# ============================================================================

class TestResultMissingSignals:
    """When a signal is absent the method should return None, never crash."""

    def test_min_voltage_none_when_no_voltage(self):
        r = make_result(current_values=[1.0])
        assert r.min_voltage() is None

    def test_max_voltage_none_when_no_voltage(self):
        r = make_result(current_values=[1.0])
        assert r.max_voltage() is None

    def test_peak_current_none_when_no_current(self):
        r = make_result(voltage_values=[3.3])
        assert r.peak_current() is None

    def test_total_energy_none_when_no_energy(self):
        r = make_result(voltage_values=[3.3])
        assert r.total_energy_Wh() is None

    def test_final_soc_none_when_no_soc(self):
        r = make_result(voltage_values=[3.3])
        assert r.final_soc() is None

    def test_peak_power_none_when_no_power(self):
        r = make_result(voltage_values=[3.3])
        assert r.peak_power() is None


class TestResultEmpty:
    """An empty Result (no signals at all) should not crash."""

    def test_empty_result_available_signals(self):
        r = Result({})
        assert r.available_signals() == []

    def test_empty_result_voltage_none(self):
        r = Result({})
        assert r.voltage() is None

    def test_empty_result_min_voltage_none(self):
        r = Result({})
        assert r.min_voltage() is None


# ============================================================================
# NaN handling
# ============================================================================

class TestResultNaN:
    """Methods should not raise when data contains NaN."""

    def test_min_voltage_with_nan(self):
        r = make_result(voltage_values=[3.2, float('nan'), 3.1])
        # np.min propagates NaN — that's numpy's default behaviour.
        # The key assertion: it does NOT raise an exception.
        result = r.min_voltage()
        assert result is not None

    def test_max_voltage_with_nan(self):
        r = make_result(voltage_values=[3.2, float('nan'), 3.1])
        result = r.max_voltage()
        assert result is not None

    def test_peak_current_with_nan(self):
        r = make_result(current_values=[1.0, float('nan'), 2.0])
        result = r.peak_current()
        assert result is not None
