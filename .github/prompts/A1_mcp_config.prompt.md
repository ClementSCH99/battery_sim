## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end.

## TASK
Fix MCP server configuration and verify it starts cleanly.

## CONTEXT
- Project: PyBaMM battery assistant API with MCP server (`mcp_server.py`)
- `.vscode/mcp.json` is broken (contains only `{`) — the server cannot be discovered by VS Code
- Transport: stdio (local VS Code Copilot)
- Reference config format is documented in `docs/mcp_setup.md`
- The server uses `FastMCP("battery-sim")` and exposes 15 tools

## INSTRUCTIONS
1. **Fix `.vscode/mcp.json`** — Write a valid stdio configuration:
   - `type`: `"stdio"`
   - `command`: `"${workspaceFolder}/.venv/bin/python"`
   - `args`: `["mcp_server.py"]`
   - `cwd`: `"${workspaceFolder}"`
2. **Verify the server starts** — Run `python mcp_server.py` and confirm no import errors
3. **Run fast MCP tests** — `pytest tests/test_mcp.py -k "not slow"` must pass
4. **Verify tool discovery** — Confirm all 15 expected tools are registered (check `TestToolRegistration` test)

## SCOPE BOUNDARIES
- Do NOT add new tools or modify tool logic
- Do NOT change transport protocol
- Only fix configuration and verify startup

## OUTPUT
- Working `.vscode/mcp.json`
- Server starts without errors
- Fast MCP tests pass
- A report in `/docs/reports/A1_mcp_config.md` including:
  - what was done
  - key decisions
  - issues encountered
  - next improvements

## EDUCATION
- Briefly explain MCP stdio transport in the report
- Explain how VS Code discovers MCP servers via `.vscode/mcp.json`

## DEFINITION OF DONE
- `.vscode/mcp.json` contains valid JSON config
- `python mcp_server.py` runs without import errors
- `pytest tests/test_mcp.py -k "not slow"` — all tests pass
- After VS Code reload, battery-sim tools appear in Copilot tool list
