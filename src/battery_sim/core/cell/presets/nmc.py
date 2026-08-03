"""NMC exploration and literature-backed presets."""

from battery_sim.core.cell.model import Cell
from battery_sim.core.cell.preset import CellPreset


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
    ),
    weight_kg=0.070,                            # ~70g for high-energy NMC
    volume_L=0.035,                             # ~35mL
    cost_usd=4.00,                              # ~$4 for higher energy NMC
    max_charge_c_rate=1.0,                      # 1C charging
    max_discharge_c_rate=3.0,                   # 3C discharging
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
    ),
    weight_kg=0.140,                            # 2× weight of 5Ah
    volume_L=0.070,                             # 2× volume of 5Ah
    cost_usd=8.00,                              # ~$8 for 10Ah NMC
    max_charge_c_rate=1.0,
    max_discharge_c_rate=3.0,
)

# ============ NCA (LiNi₀.₈Co₀.₁Al₀.₁O₂) - Very high energy, shorter cycle life ============
NMC_CHEN_LGM50 = CellPreset(
    name="NMC_CHEN_LGM50",
    chemistry="NMC",
    description=(
        "5 Ah graphite/NMC reference case using the PyBaMM Chen2020 "
        "LG M50 parameter set. Intended for reproducible model benchmarks."
    ),
    cell=Cell(
        chemistry="NMC-CHEN",
        nominal_capacity_Ah=5.0,
        nominal_voltage_V=3.63,
        metadata={
            "source": "Chen et al., J. Electrochem. Soc., 2020",
            "cell_format": "LG M50 cylindrical cell",
            "designed_for": "reproducible NMC reference simulations",
            "anode": "graphite",
            "cathode": "NMC",
            "min_voltage_v": "2.5",
            "max_voltage_v": "4.2",
            "pybamm_parameter_set": "Chen2020",
            "representation": "literature parameter set; not a calibrated project cell",
        },
    ),
)

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
    ),
    weight_kg=0.002,                            # ~2g for single pair
    volume_L=0.001,                             # ~1mL for single pair
    cost_usd=0.05,                              # Research prototype
    max_charge_c_rate=1.0,
    max_discharge_c_rate=1.0,
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
    ),
    weight_kg=0.070,                            # Typical 5Ah NMC
    volume_L=0.035,
    cost_usd=4.00,
    max_charge_c_rate=1.0,
    max_discharge_c_rate=3.0,
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
    ),
    weight_kg=0.070,
    volume_L=0.035,
    cost_usd=4.00,
    max_charge_c_rate=1.0,
    max_discharge_c_rate=3.0,
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
    ),
    weight_kg=0.032,                            # ~32g for 2.28Ah
    volume_L=0.016,
    cost_usd=2.00,
    max_charge_c_rate=1.0,
    max_discharge_c_rate=3.0,
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
    ),
    weight_kg=0.700,                            # ~700g for 50Ah (scaled)
    volume_L=0.350,                             # ~350mL for 50Ah
    cost_usd=40.00,                             # ~$40 for large capacity NMC
    max_charge_c_rate=1.0,                      # 1C = 50A
    max_discharge_c_rate=3.0,                   # 3C = 150A
)

# ============ LFP High Power ============
