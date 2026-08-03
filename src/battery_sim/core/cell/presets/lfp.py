"""LFP exploration and literature-backed presets."""

from battery_sim.core.cell.model import Cell
from battery_sim.core.cell.preset import CellPreset


LFP_5AH = CellPreset(
    name="LFP_5AH",
    chemistry="LFP",
    description=(
        "Synthetic 5 Ah LFP exploration preset mapped to Prada2013. "
        "Nominal and packaging values are illustrative; this is not a "
        "CATL/BYD digital twin."
    ),
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
            "source": "illustrative engineering assumptions; electrochemistry from PyBaMM Prada2013",
            "pybamm_parameter_set": "Prada2013",
            "representation": "synthetic scaling; not a calibrated commercial cell",
        }
    ),
    weight_kg=0.100,                            # ~100g typical for 5Ah
    volume_L=0.050,                             # ~50mL typical
    cost_usd=3.00,                              # ~$3 for commodity LFP cell
    max_charge_c_rate=1.0,                      # 1C charging (5A)
    max_discharge_c_rate=3.0,                   # 3C discharging (15A)
)

LFP_10AH = CellPreset(
    name="LFP_10AH",
    chemistry="LFP",
    description="Synthetic 10 Ah scaling of the Prada2013 LFP exploration preset.",
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
            "source": "illustrative engineering assumptions; electrochemistry from PyBaMM Prada2013",
            "pybamm_parameter_set": "Prada2013",
            "representation": "synthetic scaling; not a calibrated commercial cell",
        }
    ),
    weight_kg=0.200,                            # 2× weight of 5Ah
    volume_L=0.100,                             # 2× volume of 5Ah
    cost_usd=6.00,                              # ~$6 for 10Ah LFP
    max_charge_c_rate=1.0,                      # 1C charging (10A)
    max_discharge_c_rate=3.0,                   # 3C discharging (30A)
)

# ============ NMC (LiNi₀.₆Mn₀.₂Co₀.₂O₂) - High energy, medium cycle life ============
LFP_PRADA_2P3AH = CellPreset(
    name="LFP_PRADA_2P3AH",
    chemistry="LFP",
    description=(
        "2.3 Ah LFP/graphite reference case using the PyBaMM Prada2013 "
        "parameter set. Intended for reproducible model benchmarks, not "
        "as a digital twin of a commercial cell."
    ),
    cell=Cell(
        chemistry="LFP-PRADA",
        nominal_capacity_Ah=2.3,
        nominal_voltage_V=3.2,
        metadata={
            "source": "Prada et al., J. Electrochem. Soc., 2013",
            "designed_for": "reproducible LFP reference simulations",
            "anode": "graphite",
            "cathode": "LFP",
            "min_voltage_v": "2.0",
            "max_voltage_v": "3.6",
            "pybamm_parameter_set": "Prada2013",
            "representation": "literature parameter set; not a commercial-cell digital twin",
        },
    ),
)

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
    ),
    weight_kg=0.400,                            # ~400g for 20Ah (2× weight of 10Ah)
    volume_L=0.200,                             # ~200mL for 20Ah
    cost_usd=12.00,                             # ~$12 for high-power LFP
    max_charge_c_rate=2.0,                      # 2C = 40A (high power)
    max_discharge_c_rate=4.0,                   # 4C = 80A (very high power)
)

