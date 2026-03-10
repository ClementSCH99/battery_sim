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