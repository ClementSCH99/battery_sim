# Phase 3c: MCP Server Tests

Add tests for the MCP server tool schema and round-trip invocation.

## Prerequisites
- Phase 1 (MCP Server) must be complete — `mcp_server.py` exists and works

## Context

The MCP server wraps `AgentAPI` methods as MCP tools. Tests should verify:
1. Tool schemas are correctly defined (names, parameter types)
2. Tool invocations reach `AgentAPI` and return structured results
3. The server can start without errors

## Steps

### 1. Create `tests/test_mcp.py`

**Schema validation (fast, no PyBaMM):**
```python
def test_mcp_server_imports():
    """MCP server module imports without errors."""
    import mcp_server  # Should not crash

def test_mcp_tools_are_registered():
    """All expected tools are registered on the FastMCP server."""
    from mcp_server import mcp  # or however the server instance is exposed
    # Inspect registered tools
    expected_tools = {"list_presets", "run_simulation", "compare_presets",
                      "sensitivity_analysis", "check_feasibility", "get_session_summary"}
    # Verify all expected tools exist in server's tool registry
```

**Tool schema correctness (fast, no PyBaMM):**
```python
def test_list_presets_schema():
    """list_presets tool has correct parameter schema."""
    # Verify: chemistry parameter is optional string

def test_run_simulation_schema():
    """run_simulation tool has required preset_name parameter."""
    # Verify: preset_name is required string, others are optional

def test_compare_presets_schema():
    """compare_presets tool requires preset_names list."""
    # Verify: preset_names is required list[str]
```

**Round-trip invocation (slow, requires PyBaMM):**
```python
@pytest.mark.slow
def test_list_presets_invocation():
    """Calling list_presets through MCP tools returns valid JSON."""
    # Call the underlying function directly (not via MCP transport)
    # Verify: returns dict with 'presets' key

@pytest.mark.slow
def test_run_simulation_invocation():
    """Calling run_simulation returns metrics JSON."""
    # Call with preset_name="LFP_5AH"
    # Verify: returns dict with simulation metrics
```

### 2. Test strategy

For MCP-specific testing, there are two approaches:

**Approach A: Direct function testing** (recommended for unit tests)
- Import the MCP tool functions directly
- Call them as regular Python functions
- Verify return values

**Approach B: MCP client testing** (for integration tests)
- Use `mcp` SDK's test client if available
- Or start the server in a subprocess and communicate via stdio
- This tests the full MCP protocol round-trip

Start with Approach A. Add Approach B only if needed.

## Files to Read First
- `mcp_server.py` — the MCP server to test
- `core/agent_api.py` — underlying API being wrapped
- MCP SDK docs for test utilities (if any)

## Files to Create
- **Create**: `tests/test_mcp.py`

## Definition of Done
- [ ] MCP server imports without errors
- [ ] All expected tools are registered
- [ ] Tool schemas have correct parameter types
- [ ] Round-trip test: `list_presets` → JSON with presets
- [ ] Round-trip test: `run_simulation("LFP_5AH")` → JSON with metrics
- [ ] All tests pass: `pytest tests/test_mcp.py -v`
