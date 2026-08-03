"""Experimental presets outside the initial LFP/NMC product scope."""

from battery_sim.core.cell.model import Cell
from battery_sim.core.cell.preset import CellPreset


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
    ),
    weight_kg=0.065,                            # Slightly lighter, high energy density
    volume_L=0.032,                             # Smallest volume for same energy
    cost_usd=4.50,                              # ~$4.50 for premium NCA
    max_charge_c_rate=0.7,                      # Lower charge C-rate than NMC
    max_discharge_c_rate=3.0,                   # Good discharge performance
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
    ),
    weight_kg=0.050,                            # Lightweight but high cost
    volume_L=0.025,                             # Small volume
    cost_usd=3.50,                              # ~$3.50 despite lower cycle life
    max_charge_c_rate=0.8,                      # More conservative
    max_discharge_c_rate=2.5,                   # Lower discharge C-rate
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
    ),
    weight_kg=0.080,                            # Heavier chemistry
    volume_L=0.040,                             # Similar volume to 5Ah NMC
    cost_usd=3.50,                              # ~$3.50 for safe chemistry
    max_charge_c_rate=1.0,
    max_discharge_c_rate=2.5,
)

# ============ Literature-backed PyBaMM reference parameter sets ============

