# battery_sim/types/signal.py

from enum import Enum

class Signal(str, Enum):
    """Canonical runtime signal vocabulary exposed through Result."""

    # Primary electrical signals
    TIME = "time"
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    ENERGY = "energy"
    
    # Battery state signals
    SOC = "soc"
    SOH = "soh"
    CAPACITY = "capacity"
    CAPACITY_FADE = "capacity_fade"
    
    # Thermal signals
    TEMPERATURE = "temperature"
    HEAT_GENERATION = "heat_generation"
    
    # Internal states (for DFN model)
    ANODE_POTENTIAL = "anode_potential"
    CATHODE_POTENTIAL = "cathode_potential"
    OVERPOTENTIAL = "overpotential"
    ELECTROLYTE_CONCENTRATION = "electrolyte_concentration"
    
    # Performance metrics
    INTERNAL_RESISTANCE = "internal_resistance"
    EFFICIENCY = "efficiency"

    # Degradation signals
    SEI_THICKNESS = "sei_thickness"
    LITHIUM_PLATING_CAPACITY = "lithium_plating_capacity"
    LOSS_OF_ACTIVE_MATERIAL = "loss_of_active_material"
    TOTAL_CAPACITY_LOSS = "total_capacity_loss"

    # Cycling signals (time axis = cycle number)
    CYCLE_DISCHARGE_CAPACITY = "cycle_discharge_capacity"
    CYCLE_CHARGE_CAPACITY = "cycle_charge_capacity"
    CYCLE_COULOMBIC_EFFICIENCY = "cycle_coulombic_efficiency"
    CYCLE_CAPACITY_RETENTION = "cycle_capacity_retention"
