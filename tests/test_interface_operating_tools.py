"""Fast contracts for operating-point result presentation."""

from battery_sim.core.investigation_tools import OperatingWindowPoint
from battery_sim.core.experiment import Model
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.simulation_session import SimulationSession
from battery_sim.interface.operating_tools import OperatingToolHandler


class UnusedBackend(SimulationBackend):
    def run(self, simulation, **solver_options):
        raise AssertionError("fake analyzer should avoid backend execution")

    def supports_model(self, model):
        return True


class FakeAnalyzer:
    def __init__(self, backend, model):
        self.points = [
            OperatingWindowPoint(0.5, 25.0, 1.5, "safe", 3.0, 3.4, 0.0, 0.45, True, "within voltage screen"),
            OperatingWindowPoint(0.2, 0.0, 3.0, "avoid", None, None, None, None, False, "solver failed"),
        ]

    def analyze(self, cell, grid_size):
        return {
            "grid_points": self.points,
            "total_points": 2,
            "summary": {
                "safe": 1,
                "caution": 0,
                "avoid": 1,
                "percent_safe": 50.0,
                "percent_caution": 0.0,
                "percent_avoid": 50.0,
                "max_safe_crate": 1.5,
                "safe_temperature_range_C": [25.0, 25.0],
            },
        }

    def get_derating_curves(self):
        return {
            "max_crate_vs_temperature": [{"temperature_C": 25.0, "max_c_rate": 1.5}],
            "max_crate_vs_soc": [{"soc_level": 0.5, "max_c_rate": 1.5}],
        }


def _handler():
    session = SimulationSession(name="operating handler test")
    return (
        OperatingToolHandler(
            backend=UnusedBackend(),
            session=session,
            default_model=Model.SPM,
            analyzer_factory=FakeAnalyzer,
        ),
        session,
    )


def test_operating_screen_reports_failures_and_scope():
    handler, session = _handler()

    result = handler.operating_window("LFP_5AH")

    assert result.json_data["successful_points"] == 1
    assert result.json_data["failed_points"] == 1
    assert result.json_data["evidence"]["thermal_model"].startswith("isothermal")
    assert "not a safety qualification" in result.json_data["evidence"]["validation_status"]
    assert session.investigation_history[-1].investigation_type == "operating_window"


def test_derating_power_is_cell_watts_and_not_pack_kw():
    handler, _ = _handler()

    result = handler.derating_curves("LFP_5AH")

    point = result.json_data["max_crate_vs_temperature"][0]
    assert point["cell_power_W"] == 24.0
    assert "24.0 W" in result.markdown_text
    assert "production" in result.markdown_text
