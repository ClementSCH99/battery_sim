from dataclasses import dataclass

from battery_sim.core.cell import Cell


@dataclass(frozen=True)
class ParameterMappingPolicy:
    chemistry: str
    normalized_chemistry: str
    parameter_set: str
    mapping_policy: str


_CHEMISTRY_PARAMETER_SETS = {
    "LFP": "Marquis2019",
    "NMC": "Chen2020",
    "NCA": "Chen2020",
    "LCO": "Chen2020",
    "LMNO": "Chen2020",
}

_CHEMISTRY_VARIANTS = {
    "LFP-HP": "LFP",
    "NMC-HE": "NMC",
}


def resolve_parameter_mapping(cell: Cell) -> ParameterMappingPolicy:
    chemistry = (getattr(cell, "chemistry", "") or "").strip().upper()
    if not chemistry:
        raise ValueError("Cell chemistry is required to resolve the PyBaMM parameter mapping.")

    normalized_chemistry = _CHEMISTRY_VARIANTS.get(chemistry, chemistry)
    parameter_set = _CHEMISTRY_PARAMETER_SETS.get(normalized_chemistry)
    if parameter_set is None:
        raise ValueError(
            f"Unsupported chemistry mapping for '{chemistry}'. Add an explicit mapping policy before running this preset."
        )

    mapping_policy = "exact_match" if normalized_chemistry == chemistry else "variant_family_match"
    return ParameterMappingPolicy(
        chemistry=chemistry,
        normalized_chemistry=normalized_chemistry,
        parameter_set=parameter_set,
        mapping_policy=mapping_policy,
    )