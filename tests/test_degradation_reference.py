"""Real PyBaMM reference for the experimental degradation path."""

import pytest

from battery_sim.interfaces.python.tool_registry import AgentAPI


@pytest.mark.slow
def test_okane_aging_path_produces_observed_cycles_and_labeled_projection():
    result = AgentAPI().predict_lifetime(
        "NMC_OKANE_AGING",
        n_representative_cycles=3,
        temperature_C=25.0,
    )

    assert result.json_data["type"] == "lifetime_prediction"
    assert result.json_data["projection"]["observed_cycle_count"] == 3
    assert result.json_data["projection"]["method"] == (
        "ordinary least-squares linear fit"
    )
    assert result.json_data["evidence"]["observed"] == (
        "per-cycle discharge capacity from SimulationRun"
    )
    assert result.json_data["evidence"]["validation_status"] == (
        "not validated against cell test data"
    )
