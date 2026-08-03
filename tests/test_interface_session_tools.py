"""Contract tests for the extracted session interface handler."""

from battery_sim.core.simulation_session import SimulationSession
from battery_sim.interface.session_tools import SessionToolHandler


def test_session_handler_delegates_report_generation():
    session = SimulationSession(name="research trace")
    handler = SessionToolHandler(session=session)

    summary = handler.get_summary()

    assert "research trace" in summary
