from dataclasses import dataclass

from battery_sim.core.cell import Cell


@dataclass(frozen=True)
class ParameterMappingPolicy:
    chemistry: str
    normalized_chemistry: str
    parameter_set: str
    mapping_policy: str


_CHEMISTRY_PARAMETER_SETS = {
    # Prada2013 is the only installed parameter set explicitly parameterized
    # for an LFP positive electrode. Marquis2019 uses a LiCoO2 OCP and must not
    # be labelled as LFP even if a simulation with it happens to converge.
    "LFP": "Prada2013",
    "LFP-PRADA": "Prada2013",
    "NMC": "Chen2020",
    "NMC-CHEN": "Chen2020",
    "NCA": "Chen2020",
    "LCO": "Chen2020",
    "LMNO": "Chen2020",
    # Validated parameter sets from PyBaMM literature
    "NMC-ECKER": "Ecker2015",        # Ecker et al. 2015, Kokam SLPB 75106100 pouch
    "NMC-OKANE": "OKane2022",        # O'Kane et al. 2022, degradation-focused
    "NMC-MOHTAT": "Mohtat2020",      # Mohtat et al. 2020, pouch cell
    "NMC-AI": "Ai2020",              # Ai et al. 2020, Enertech pouch cell
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
