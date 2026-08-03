"""Canonical import location for the agent-facing facade.

The implementation remains temporarily in ``core.agent_api`` while its large
methods are extracted into focused interface handlers. Keeping this module as
the public entry point lets callers migrate now without a flag-day move.
"""

from battery_sim.interfaces.python.tool_registry import AgentAPI, agent_tool

__all__ = ["AgentAPI", "agent_tool"]
