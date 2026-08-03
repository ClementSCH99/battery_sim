"""Unit contracts for the focused PyBaMM solution extractor."""

import math

from battery_sim.backend.pybamm_result_extractor import PyBaMMResultExtractor
from battery_sim.core.result import Signal


class Variable:
    def __init__(self, data):
        self.data = data


class FakeSolution(dict):
    cycles = []


def _solution(time, voltage, current, **extra):
    values = {
        "Time [s]": Variable(time),
        "Terminal voltage [V]": Variable(voltage),
        "Current [A]": Variable(current),
    }
    values.update({name: Variable(data) for name, data in extra.items()})
    return FakeSolution(values)


def test_temperature_is_converted_from_pybamm_kelvin_to_celsius():
    solution = _solution(
        [0.0, 1.0],
        [3.5, 3.4],
        [1.0, 1.0],
        **{"Cell temperature [K]": [298.15, 299.15]},
    )

    result = PyBaMMResultExtractor().extract(solution)

    temperature = result.get(Signal.TEMPERATURE)
    assert temperature.values == [25.0, 26.0]
    assert temperature.unit == "°C"


def test_discharge_only_trace_does_not_invent_round_trip_efficiency():
    result = PyBaMMResultExtractor().extract(
        _solution([0.0, 1.0, 2.0], [3.5, 3.4, 3.3], [1.0, 1.0, 1.0])
    )

    assert Signal.EFFICIENCY not in result.available_signals()
    assert Signal.INTERNAL_RESISTANCE not in result.available_signals()
    assert result.get(Signal.CAPACITY).values[-1] > 0


def test_charge_only_trace_does_not_invent_round_trip_efficiency():
    result = PyBaMMResultExtractor().extract(
        _solution([0.0, 1.0, 2.0], [3.5, 3.6, 3.7], [-1.0, -1.0, -1.0])
    )

    assert Signal.EFFICIENCY not in result.available_signals()


def test_round_trip_efficiency_requires_observed_charge_and_discharge_energy():
    result = PyBaMMResultExtractor().extract(
        _solution(
            [0.0, 1.0, 2.0, 3.0],
            [4.0, 4.0, 4.0, 4.0],
            [-1.0, -1.0, 1.0, 1.0],
        )
    )

    efficiency = result.get(Signal.EFFICIENCY)
    assert efficiency.values[-1] == 50.0
    assert all(math.isfinite(value) for value in efficiency.values)


def test_internal_resistance_contains_only_finite_estimates():
    time = list(range(12))
    current = [0.0] * 4 + [1.0] * 4 + [2.0] * 4
    voltage = [4.2 - 0.02 * value for value in current]

    result = PyBaMMResultExtractor().extract(_solution(time, voltage, current))

    resistance = result.get(Signal.INTERNAL_RESISTANCE)
    assert resistance.values
    assert all(math.isfinite(value) for value in resistance.values)
