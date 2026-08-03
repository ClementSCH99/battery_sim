"""Temporary launcher for the packaged MCP server.

The implementation lives in :mod:`battery_sim.mcp_server`. This root launcher
will be removed when MCP moves to ``battery_sim.interfaces.mcp``.
"""

from battery_sim.mcp_server import *  # noqa: F401,F403
from battery_sim.mcp_server import mcp


if __name__ == "__main__":
    mcp.run()
