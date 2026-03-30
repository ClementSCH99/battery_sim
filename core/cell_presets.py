# battery_sim/core/cell_presets.py
"""
Cell Presets: Predefined battery cell configurations.

This module provides preset battery cell configurations for common chemistries,
enabling quick setup with realistic parameters based on industry standards.
"""

from dataclasses import dataclass, replace
from typing import Dict, Optional
from battery_sim.core.cell import Cell


@dataclass(frozen=True)
class CellPreset:
    """A preset battery cell configuration with documentation."""
    name: str
    chemistry: str
    description: str
    cell: Cell


class CellPresets:
    """
    Library of standard battery cell presets.
    
    Each preset includes parameters typical for that chemistry at room temperature (25°C),
    based on commercial cell specifications and academic references.
    """

    # ============ LiFePO4 (LFP) - Long cycle life, safe, lower energy density ============
    LFP_5AH = CellPreset(
        name="LFP_5AH",
        chemistry="LFP",
        description="5 Ah LiFePO4 cell (CATL, BYD typical specs). Safe, long cycle life (~3000 cycles), lower energy density (~160 Wh/kg).",
        cell=Cell(
            chemistry="LFP",
            nominal_capacity_Ah=5.0,                 # 5 Ah
            nominal_voltage_V=3.2,                   # 3.2V nominal (LFP nominal)
            internal_resistance_Ohm=0.050,           # ~50 mΩ (lower for LFP)
            electrode_area_m2=0.040,                 # 40 cm² typical
            electrode_thickness_m=100e-6,            # 100 μm
            density_kg_per_m3=2700.0,                # Iron compounds, slightly heavier
            specific_heat_J_per_kgK=900.0,           # J/(kg·K)
            thermal_conductivity_W_per_mK=15.0,      # Good thermal conductivity
            metadata={
                "nominal_energy_wh": "16.0",
                "min_voltage_v": "2.5",
                "max_voltage_v": "3.65",
                "cycle_life": "3000-5000",
                "source": "CATL/BYD specifications"
            }
        )
    )

    LFP_10AH = CellPreset(
        name="LFP_10AH",
        chemistry="LFP",
        description="10 Ah LiFePO4 cell. Scaled version for larger capacity applications.",
        cell=Cell(
            chemistry="LFP",
            nominal_capacity_Ah=10.0,
            nominal_voltage_V=3.2,
            internal_resistance_Ohm=0.045,           # Slightly lower due to larger size
            electrode_area_m2=0.080,                 # Proportionally larger
            electrode_thickness_m=100e-6,
            density_kg_per_m3=2700.0,
            specific_heat_J_per_kgK=900.0,
            thermal_conductivity_W_per_mK=15.0,
            metadata={
                "nominal_energy_wh": "32.0",
                "min_voltage_v": "2.5",
                "max_voltage_v": "3.65",
                "cycle_life": "3000-5000",
                "source": "CATL/BYD specifications"
            }
        )
    )

    # ============ NMC (LiNi₀.₆Mn₀.₂Co₀.₂O₂) - High energy, medium cycle life ============
    NMC_5AH = CellPreset(
        name="NMC_5AH",
        chemistry="NMC",
        description="5 Ah NMC 622 cell (Samsung, LG typical). High energy density (~250 Wh/kg), medium cycle life (~1000-2000 cycles).",
        cell=Cell(
            chemistry="NMC",
            nominal_capacity_Ah=5.0,
            nominal_voltage_V=3.7,                   # 3.7V nominal (NMC nominal)
            internal_resistance_Ohm=0.070,           # ~70 mΩ (typical for NMC)
            electrode_area_m2=0.050,
            electrode_thickness_m=110e-6,            # Slightly thicker for higher energy
            density_kg_per_m3=2350.0,                # Lighter than LFP
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,      # Lower than LFP
            metadata={
                "nominal_energy_wh": "18.5",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.2",
                "cycle_life": "1000-2000",
                "source": "Samsung/LG specifications"
            }
        )
    )

    NMC_10AH = CellPreset(
        name="NMC_10AH",
        chemistry="NMC",
        description="10 Ah NMC 622 cell. Scaled version for larger capacity applications.",
        cell=Cell(
            chemistry="NMC",
            nominal_capacity_Ah=10.0,
            nominal_voltage_V=3.7,
            internal_resistance_Ohm=0.065,
            electrode_area_m2=0.100,
            electrode_thickness_m=110e-6,
            density_kg_per_m3=2350.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "nominal_energy_wh": "37.0",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.2",
                "cycle_life": "1000-2000",
                "source": "Samsung/LG specifications"
            }
        )
    )

    # ============ NCA (LiNi₀.₈Co₀.₁Al₀.₁O₂) - Very high energy, shorter cycle life ============
    NCA_5AH = CellPreset(
        name="NCA_5AH",
        chemistry="NCA",
        description="5 Ah NCA cell (Tesla, Panasonic). Very high energy density (~270 Wh/kg), shorter cycle life (~800-1200 cycles).",
        cell=Cell(
            chemistry="NCA",
            nominal_capacity_Ah=5.0,
            nominal_voltage_V=3.7,
            internal_resistance_Ohm=0.080,           # Slightly higher due to cobalt content
            electrode_area_m2=0.050,
            electrode_thickness_m=120e-6,            # Thicker for maximum energy
            density_kg_per_m3=2400.0,                # Similar to NMC but cobalt heavier
            specific_heat_J_per_kgK=820.0,
            thermal_conductivity_W_per_mK=8.0,       # Lower than NMC
            metadata={
                "nominal_energy_wh": "18.5",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.3",                # Higher cutoff for more energy
                "cycle_life": "800-1200",
                "source": "Tesla/Panasonic specifications"
            }
        )
    )

    # ============ LCO (LiCoO₂) - High voltage, lower cycle life, expensive ============
    LCO_3AH = CellPreset(
        name="LCO_3AH",
        chemistry="LCO",
        description="3 Ah LCO cell. High voltage (4.35V), high energy density but lower cycle life (~500-800 cycles), expensive.",
        cell=Cell(
            chemistry="LCO",
            nominal_capacity_Ah=3.0,
            nominal_voltage_V=3.8,
            internal_resistance_Ohm=0.090,           # Higher resistance, less stable
            electrode_area_m2=0.030,
            electrode_thickness_m=100e-6,
            density_kg_per_m3=2600.0,                # Cobalt is heavy
            specific_heat_J_per_kgK=800.0,
            thermal_conductivity_W_per_mK=7.0,       # Low thermal conductivity
            metadata={
                "nominal_energy_wh": "11.4",
                "min_voltage_v": "2.7",
                "max_voltage_v": "4.35",              # High voltage operation
                "cycle_life": "500-800",
                "source": "Sony/Samsung specifications"
            }
        )
    )

    # ============ LMNO (LiMn₂O₄) - Safe, good thermal stability, lower energy ============
    LMNO_4AH = CellPreset(
        name="LMNO_4AH",
        chemistry="LMNO",
        description="4 Ah LMNO cell. Safe (spinel structure), good thermal stability, lower energy density (~120 Wh/kg).",
        cell=Cell(
            chemistry="LMNO",
            nominal_capacity_Ah=4.0,
            nominal_voltage_V=3.8,
            internal_resistance_Ohm=0.060,
            electrode_area_m2=0.040,
            electrode_thickness_m=90e-6,
            density_kg_per_m3=2500.0,
            specific_heat_J_per_kgK=920.0,           # Higher specific heat
            thermal_conductivity_W_per_mK=18.0,      # Good thermal conductivity
            metadata={
                "nominal_energy_wh": "15.2",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.3",
                "cycle_life": "2000-3000",
                "source": "Electrochem literature"
            }
        )
    )

    # ============ Validated PyBaMM Parameter Sets ============

    # Ecker et al. 2015 — Kokam SLPB 75106100 NMC/graphite pouch cell
    NMC_ECKER_KOKAM = CellPreset(
        name="NMC_ECKER_KOKAM",
        chemistry="NMC-ECKER",
        description="Ecker et al. 2015 Kokam SLPB 75106100 NMC/graphite pouch cell. First complete open-source parameterization, 0.156 Ah single electrode pair (full cell ~7.5 Ah with 48 pairs).",
        cell=Cell(
            chemistry="NMC-ECKER",
            nominal_capacity_Ah=0.15625,
            nominal_voltage_V=3.6,
            internal_resistance_Ohm=0.070,
            electrode_area_m2=0.008585,
            electrode_thickness_m=74e-6,
            density_kg_per_m3=2350.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "source": "Ecker et al., J. Electrochem. Soc., 2015",
                "cell_format": "pouch (Kokam SLPB 75106100)",
                "designed_for": "general characterization",
                "anode": "graphite",
                "cathode": "NMC",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.2",
                "note": "Capacity is for a single electrode pair; full cell is ~7.5 Ah (48 pairs)",
                "pybamm_parameter_set": "Ecker2015",
            }
        )
    )

    # O'Kane et al. 2022 — extended Chen2020 with full degradation sub-models
    NMC_OKANE_AGING = CellPreset(
        name="NMC_OKANE_AGING",
        chemistry="NMC-OKANE",
        description="O'Kane et al. 2022 NMC/graphite cell. Extended Chen2020 with SEI, lithium plating, and active material loss sub-models for aging studies.",
        cell=Cell(
            chemistry="NMC-OKANE",
            nominal_capacity_Ah=5.0,
            nominal_voltage_V=3.6,
            internal_resistance_Ohm=0.070,
            electrode_area_m2=0.050,
            electrode_thickness_m=85e-6,
            density_kg_per_m3=2350.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "source": "O'Kane et al., Phys. Chem. Chem. Phys., 2022",
                "cell_format": "cylindrical",
                "designed_for": "degradation studies",
                "anode": "graphite",
                "cathode": "NMC",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.2",
                "degradation_models": "SEI, lithium plating, active material loss",
                "pybamm_parameter_set": "OKane2022",
            }
        )
    )

    # Mohtat et al. 2020 — NMC/graphite pouch cell
    NMC_MOHTAT_POUCH = CellPreset(
        name="NMC_MOHTAT_POUCH",
        chemistry="NMC-MOHTAT",
        description="Mohtat et al. 2020 NMC532/graphite pouch cell. 5 Ah capacity, designed for electrode-level differential expansion studies.",
        cell=Cell(
            chemistry="NMC-MOHTAT",
            nominal_capacity_Ah=5.0,
            nominal_voltage_V=3.6,
            internal_resistance_Ohm=0.065,
            electrode_area_m2=0.050,
            electrode_thickness_m=62e-6,
            density_kg_per_m3=2350.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "source": "Mohtat et al., J. Electrochem. Soc., 2020",
                "cell_format": "pouch",
                "designed_for": "electrode-level analysis",
                "anode": "graphite",
                "cathode": "NMC",
                "min_voltage_v": "2.8",
                "max_voltage_v": "4.2",
                "pybamm_parameter_set": "Mohtat2020",
            }
        )
    )

    # Ai et al. 2020 — Enertech NMC/graphite pouch cell
    NMC_AI_ENERTECH = CellPreset(
        name="NMC_AI_ENERTECH",
        chemistry="NMC-AI",
        description="Ai et al. 2020 Enertech NMC/graphite pouch cell. 2.28 Ah, 34 electrode pairs, with thermal-mechanical stress modelling.",
        cell=Cell(
            chemistry="NMC-AI",
            nominal_capacity_Ah=2.28,
            nominal_voltage_V=3.6,
            internal_resistance_Ohm=0.065,
            electrode_area_m2=0.0024,
            electrode_thickness_m=77e-6,
            density_kg_per_m3=2400.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "source": "Ai et al., J. Electrochem. Soc., 2020",
                "cell_format": "pouch (Enertech)",
                "designed_for": "thermal-mechanical stress analysis",
                "anode": "graphite",
                "cathode": "NMC",
                "min_voltage_v": "3.0",
                "max_voltage_v": "4.2",
                "electrode_pairs": "34",
                "pybamm_parameter_set": "Ai2020",
            }
        )
    )

    # ============ NMC High Energy (for EVs) ============
    NMC_HE_50AH = CellPreset(
        name="NMC_HE_50AH",
        chemistry="NMC-HE",
        description="50 Ah NMC High Energy cell (typical EV format). Optimized for energy density.",
        cell=Cell(
            chemistry="NMC-HE",
            nominal_capacity_Ah=50.0,
            nominal_voltage_V=3.7,
            internal_resistance_Ohm=0.015,           # Much lower for large cell
            electrode_area_m2=0.500,                 # Large electrode area
            electrode_thickness_m=110e-6,
            density_kg_per_m3=2350.0,
            specific_heat_J_per_kgK=850.0,
            thermal_conductivity_W_per_mK=10.0,
            metadata={
                "nominal_energy_wh": "185.0",
                "min_voltage_v": "2.5",
                "max_voltage_v": "4.2",
                "cycle_life": "1000-1500",
                "format": "Cylindrical 18650 or prismatic",
                "source": "EV battery specifications"
            }
        )
    )

    # ============ LFP High Power ============
    LFP_HP_20AH = CellPreset(
        name="LFP_HP_20AH",
        chemistry="LFP-HP",
        description="20 Ah LFP High Power cell. Optimized for power delivery (lower internal resistance).",
        cell=Cell(
            chemistry="LFP-HP",
            nominal_capacity_Ah=20.0,
            nominal_voltage_V=3.2,
            internal_resistance_Ohm=0.020,           # Low IR for high power
            electrode_area_m2=0.200,
            electrode_thickness_m=100e-6,
            density_kg_per_m3=2700.0,
            specific_heat_J_per_kgK=900.0,
            thermal_conductivity_W_per_mK=15.0,
            metadata={
                "nominal_energy_wh": "64.0",
                "min_voltage_v": "2.5",
                "max_voltage_v": "3.65",
                "cycle_life": "3000-5000",
                "max_power_kw": "10",
                "source": "BYD/CATL high power specs"
            }
        )
    )

    @classmethod
    def get(cls, preset_name: str) -> CellPreset:
        """
        Get a preset by name.
        
        Args:
            preset_name: Name of preset (e.g., 'LFP_5AH', 'NMC_5AH')
            
        Returns:
            CellPreset with cell configuration
            
        Raises:
            ValueError: If preset not found
        """
        if not hasattr(cls, preset_name):
            available = cls.list_all()
            raise ValueError(
                f"Preset '{preset_name}' not found. "
                f"Available presets: {', '.join(available)}"
            )
        return getattr(cls, preset_name)

    @classmethod
    def list_all(cls) -> list[str]:
        """List all available preset names."""
        return [name for name in dir(cls) 
                if isinstance(getattr(cls, name), CellPreset)]

    @classmethod
    def by_chemistry(cls, chemistry: str) -> Dict[str, CellPreset]:
        """
        Get all presets for a specific chemistry.
        
        Args:
            chemistry: Chemistry name (e.g., 'LFP', 'NMC', 'NCA')
            
        Returns:
            Dictionary mapping preset names to CellPresets
        """
        result = {}
        for name in cls.list_all():
            preset = getattr(cls, name)
            if preset.chemistry.startswith(chemistry):
                result[name] = preset
        return result

    @classmethod
    def get_cell(cls, preset_name: str) -> Cell:
        """
        Convenience method: get just the Cell object from a preset.
        
        Args:
            preset_name: Name of preset
            
        Returns:
            Cell object with preset parameters
        """
        return cls.get(preset_name).cell

    @staticmethod
    def describe(preset_name: str) -> str:
        """Get human-readable description of a preset."""
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
            for key, value in preset.cell.metadata.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)
