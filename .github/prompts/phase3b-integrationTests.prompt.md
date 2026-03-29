# Phase 3b: Integration Tests

Add integration tests that exercise the service layer with real PyBaMM execution.

## Prerequisites
- Phase 2a (CC-CV) should be complete for full protocol coverage
- Phase 1 (MCP Server) should be complete for MCP integration tests (→ see Phase 3c separately)

## Context

Current integration coverage:
- `test_smoke.py::test_lfp_discharge_returns_simulation_run` — single CC discharge
- `test_smoke.py::test_compare_lfp_and_nmc` — ComparisonService with 2 presets

Missing: service-layer tests for `SensitivityService`, `ParameterSweepService`, `BatchExecutionService`, and the `AgentAPI` orchestration.

## Steps

### 1. Create `tests/test_services.py`

**ComparisonService (extend existing coverage):**
```python
@pytest.mark.slow
def test_compare_three_chemistries():
    """Compare LFP, NMC, NCA — verify metric structure for 3+ presets."""
    # Verify: result has 'metrics' key, each preset has expected metric names
    # Verify: relative_to_first calculations are present

@pytest.mark.slow
def test_comparison_metrics_are_numeric():
    """All extracted metrics should be finite numbers or None."""
    # Run comparison, iterate metrics, assert isinstance(v, (int, float)) or v is None
```

**SensitivityService:**
```python
@pytest.mark.slow
def test_sensitivity_temperature():
    """Sensitivity analysis on temperature should return valid SensitivityResult."""
    # Vary temperature [10, 25, 40] for LFP_5AH
    # Verify: SensitivityResult has parameter_values, metric_values, sensitivity_coefficient
    # Verify: sensitivity_coefficient is a finite number

@pytest.mark.slow
def test_sensitivity_interpretation():
    """SensitivityResult.interpretation() returns a valid category string."""
    # After analysis, call .interpretation()
    # Should be one of: "VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"
```

**BatchExecutionService:**
```python
@pytest.mark.slow
def test_batch_presets():
    """Run multiple presets in batch and verify all return SimulationRun."""
    # run_presets(["LFP_5AH", "NMC_5AH"], config)
    # Verify: returns list of (name, SimulationRun) tuples
    # Verify: each run has metadata and result

@pytest.mark.slow
def test_batch_parameter_variations():
    """Vary a cell parameter across values and verify runs."""
    # run_parameter_variations(baseline_cell, "nominal_capacity_Ah", [3.0, 5.0, 7.0], config)
    # Verify: returns list of (value, SimulationRun) tuples
```

**ParameterSweep:**
```python
@pytest.mark.slow
def test_sweep_cell_parameter():
    """Sweep nominal_capacity_Ah and verify SweepResult structure."""
    # sweep_cell_parameter(..., "nominal_capacity_Ah", [3.0, 5.0, 7.0])
    # Verify: returns list of SweepResult with correct parameter values

@pytest.mark.slow
def test_sweep_environment_parameter():
    """Sweep temperature and verify results."""
    # sweep_environment_parameter(..., "temperature_C", [10, 25, 40])
```

### 2. Create `tests/test_agent_api.py`

Test the `AgentAPI` orchestration layer:

```python
@pytest.mark.slow
def test_list_presets_returns_dual_format():
    api = AgentAPI()
    result = api.list_presets()
    assert isinstance(result, DualFormatResult)
    assert "presets" in result.json_data
    assert len(result.json_data["presets"]) > 0
    assert len(result.markdown_text) > 0

@pytest.mark.slow
def test_compare_presets_records_session():
    api = AgentAPI()
    api.compare_presets(["LFP_5AH", "NMC_5AH"])
    summary = api.get_session_summary()
    assert "compare_presets" in summary

@pytest.mark.slow
def test_check_feasibility():
    api = AgentAPI()
    result = api.check_feasibility("LFP_5AH", temperature_C=25.0)
    assert isinstance(result, DualFormatResult)
    assert "feasible" in result.json_data
```

### 3. Keep tests fast where possible

For service tests that don't need real simulation results, consider mocking the backend:

```python
class MockBackend(SimulationBackend):
    def run(self, simulation, **solver_options):
        """Return a minimal SimulationRun with synthetic data."""
        ...
```

This lets you test service orchestration logic without PyBaMM. Mark real-execution tests with `@pytest.mark.slow`.

## Files to Read First
- `core/application_services.py` — all service classes and their methods
- `core/parameter_sweep.py` — `ParameterSweep` class
- `core/agent_api.py` — `AgentAPI` methods
- `core/investigation_tools.py` — `BatchSimulationConfig`
- `core/result_formatter.py` — `DualFormatResult`
- `tests/test_smoke.py` — existing test patterns

## Files to Create
- **Create**: `tests/test_services.py` — service integration tests
- **Create**: `tests/test_agent_api.py` — AgentAPI integration tests

## Definition of Done
- [ ] Service tests cover ComparisonService, SensitivityService, BatchExecutionService, ParameterSweep
- [ ] AgentAPI tests verify tool output format and session tracking
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Slow tests are marked with `@pytest.mark.slow` for selective execution
