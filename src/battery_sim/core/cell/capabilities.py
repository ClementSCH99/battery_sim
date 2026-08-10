"""Backend capability metadata for public cell presets."""

from battery_sim.core.cell.model import Cell


CHEMISTRY_PARAMETER_SETS = {
    "LFP": "Prada2013",
    "LFP-PRADA": "Prada2013",
    "NMC": "Chen2020",
    "NMC-CHEN": "Chen2020",
    "NMC-ECKER": "Ecker2015",
    "NMC-OKANE": "OKane2022",
    "NMC-MOHTAT": "Mohtat2020",
    "NMC-AI": "Ai2020",
}

CHEMISTRY_VARIANTS = {
    "LFP-HP": "LFP",
    "NMC-HE": "NMC",
}

EXPLICIT_PARAMETERIZATIONS = {
    "LFP-PRADA", "NMC-CHEN", "NMC-ECKER",
    "NMC-OKANE", "NMC-MOHTAT", "NMC-AI",
}


def describe_parameter_capability(cell: Cell) -> dict:
    """Describe execution support separately from physical fidelity."""
    chemistry = (cell.chemistry or "").strip().upper()
    normalized = CHEMISTRY_VARIANTS.get(chemistry, chemistry)
    parameter_set = CHEMISTRY_PARAMETER_SETS.get(normalized)
    if parameter_set is None:
        return {
            "supports_simulation": False,
            "simulation_fidelity": "unsupported_chemistry",
            "parameter_set": None,
            "mapping_policy": None,
            "reason": (
                f"Unsupported chemistry mapping for '{chemistry}'. "
                "Add an explicit mapping policy before running this preset."
            ),
        }
    if chemistry in EXPLICIT_PARAMETERIZATIONS:
        mapping_policy = "explicit_parameterization"
    elif normalized != chemistry:
        mapping_policy = "chemistry_variant_proxy"
    else:
        mapping_policy = "chemistry_family_proxy"
    reference = mapping_policy == "explicit_parameterization"
    return {
        "supports_simulation": True,
        "simulation_fidelity": (
            "reference_parameterization" if reference else "chemistry_proxy_unscaled"
        ),
        "parameter_set": parameter_set,
        "mapping_policy": mapping_policy,
        "reason": None if reference else (
            "Catalog capacity is not propagated into the proxy parameter set; "
            "results are exploratory and not decision-ready."
        ),
    }
