# battery_sim/core/model.py
from enum import Enum

class Model(str, Enum):
    """Canonical public battery model choices."""

    SPM = "single_particle"
    DFN = "doyle_fuller_newman"

    @property
    def label(self) -> str:
        labels = {
            Model.SPM: "Single Particle Model (SPM)",
            Model.DFN: "Doyle-Fuller-Newman Model (DFN)",
        }
        return labels[self]

    @classmethod
    def from_value(cls, value: str) -> "Model":
        normalized = value.strip().lower()
        aliases = {
            "spm": cls.SPM,
            "single_particle": cls.SPM,
            "single_particule": cls.SPM,
            "dfn": cls.DFN,
            "doyle_fuller_newman": cls.DFN,
        }
        if normalized not in aliases:
            raise ValueError(f"Unsupported model value: {value}")
        return aliases[normalized]

    @classmethod
    def _missing_(cls, value: object) -> "Model | None":
        if isinstance(value, str):
            try:
                return cls.from_value(value)
            except ValueError:
                return None
        return None