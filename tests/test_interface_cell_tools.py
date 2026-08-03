"""Fast contract tests for cell discovery and feasibility handlers."""

from battery_sim.interfaces.python.schema import APISchema
from battery_sim.interfaces.python.cell_tools import CellToolHandler


def test_catalog_exposes_reference_provenance_and_missing_packaging_data():
    handler = CellToolHandler(schema=APISchema())

    response = handler.list_presets(chemistry="LFP")
    presets = {preset["name"]: preset for preset in response.json_data["presets"]}
    reference = presets["LFP_PRADA_2P3AH"]

    assert response.json_data["chemistries"] == ["LFP"]
    assert reference["parameter_set"] == "Prada2013"
    assert "not a commercial-cell digital twin" in reference["representation"]
    assert reference["packaging_data_complete"] is False


def test_feasibility_response_states_its_limited_scope():
    handler = CellToolHandler(schema=APISchema())

    response = handler.check_feasibility("NMC_CHEN_LGM50", temperature_C=25.0)

    assert response.json_data["feasible"] is True
    assert response.json_data["scope"] == "domain pre-check; does not prove PyBaMM convergence"
    assert "does not guarantee solver convergence" in response.interpretation_hints[0]
