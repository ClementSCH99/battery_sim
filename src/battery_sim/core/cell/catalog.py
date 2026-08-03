"""Searchable catalog of built-in cell presets."""

from battery_sim.core.cell.model import Cell
from battery_sim.core.cell.preset import CellPreset
from battery_sim.core.cell.presets.lfp import (
    LFP_5AH,
    LFP_10AH,
    LFP_HP_20AH,
    LFP_PRADA_2P3AH,
)
from battery_sim.core.cell.presets.nmc import (
    NMC_5AH,
    NMC_10AH,
    NMC_AI_ENERTECH,
    NMC_CHEN_LGM50,
    NMC_ECKER_KOKAM,
    NMC_HE_50AH,
    NMC_MOHTAT_POUCH,
    NMC_OKANE_AGING,
)
from battery_sim.core.cell.presets.other import (
    LCO_3AH,
    LMNO_4AH,
    NCA_5AH,
)


class CellPresets:
    """Library of engineering and literature-backed cell presets."""

    LFP_5AH = LFP_5AH
    LFP_10AH = LFP_10AH
    LFP_PRADA_2P3AH = LFP_PRADA_2P3AH
    LFP_HP_20AH = LFP_HP_20AH

    NMC_5AH = NMC_5AH
    NMC_10AH = NMC_10AH
    NMC_CHEN_LGM50 = NMC_CHEN_LGM50
    NMC_ECKER_KOKAM = NMC_ECKER_KOKAM
    NMC_OKANE_AGING = NMC_OKANE_AGING
    NMC_MOHTAT_POUCH = NMC_MOHTAT_POUCH
    NMC_AI_ENERTECH = NMC_AI_ENERTECH
    NMC_HE_50AH = NMC_HE_50AH

    NCA_5AH = NCA_5AH
    LCO_3AH = LCO_3AH
    LMNO_4AH = LMNO_4AH

    @classmethod
    def get(cls, preset_name: str) -> CellPreset:
        if not hasattr(cls, preset_name):
            available = cls.list_all()
            raise ValueError(
                f"Preset '{preset_name}' not found. "
                f"Available presets: {', '.join(available)}"
            )
        return getattr(cls, preset_name)

    @classmethod
    def list_all(cls) -> list[str]:
        return [
            name
            for name in dir(cls)
            if isinstance(getattr(cls, name), CellPreset)
        ]

    @classmethod
    def by_chemistry(cls, chemistry: str) -> dict[str, CellPreset]:
        return {
            name: preset
            for name in cls.list_all()
            if (preset := getattr(cls, name)).chemistry.startswith(chemistry)
        }

    @classmethod
    def get_cell(cls, preset_name: str) -> Cell:
        return cls.get(preset_name).cell

    @staticmethod
    def describe(preset_name: str) -> str:
        preset = CellPresets.get(preset_name)
        lines = [
            f"Preset: {preset.name}",
            f"Chemistry: {preset.chemistry}",
            f"Description: {preset.description}",
            "",
            "Parameters:",
            f"  Capacity: {preset.cell.nominal_capacity_Ah} Ah",
            f"  Nominal Voltage: {preset.cell.nominal_voltage_V} V",
            f"  Internal Resistance: {preset.cell.internal_resistance_Ohm} Ω",
            f"  Electrode Area: {preset.cell.electrode_area_m2} m²",
        ]
        if preset.cell.metadata:
            lines.append("\nMetadata:")
            lines.extend(
                f"  {key}: {value}"
                for key, value in preset.cell.metadata.items()
            )
        return "\n".join(lines)
