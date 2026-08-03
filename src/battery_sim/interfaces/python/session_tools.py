"""Agent-facing access to the current investigation trace."""

from battery_sim.application.session import SimulationSession


class SessionToolHandler:
    """Present session history without owning simulation or formatting policy."""

    def __init__(self, *, session: SimulationSession) -> None:
        self._session = session

    def get_summary(self) -> str:
        """Return the human-readable investigation report."""
        return self._session.generate_report()
