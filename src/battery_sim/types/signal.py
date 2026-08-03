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
    IRREVERSIBLE_HEAT = "irreversible_heat"
    REVERSIBLE_HEAT = "reversible_heat"
    OHMIC_HEAT = "ohmic_heat"
    CELL_TEMPERATURE = "cell_temperature"
    
    # Internal states (for DFN model)
    ANODE_POTENTIAL = "anode_potential"
    CATHODE_POTENTIAL = "cathode_potential"
    OVERPOTENTIAL = "overpotential"
    ELECTROLYTE_CONCENTRATION = "electrolyte_concentration"

    # Electrode surface concentrations
    NEGATIVE_PARTICLE_SURFACE_CONCENTRATION = "negative_particle_surface_concentration"
    POSITIVE_PARTICLE_SURFACE_CONCENTRATION = "positive_particle_surface_concentration"

    # Electrode open-circuit voltages (OCV vs Li/Li+)
    NEGATIVE_OCV = "negative_ocv"
    POSITIVE_OCV = "positive_ocv"

    # Electrode reaction overpotentials (Butler-Volmer)
    NEGATIVE_REACTION_OVERPOTENTIAL = "negative_reaction_overpotential"
    POSITIVE_REACTION_OVERPOTENTIAL = "positive_reaction_overpotential"

    # Exchange current densities (Butler-Volmer kinetics)
    NEGATIVE_EXCHANGE_CURRENT_DENSITY = "negative_exchange_current_density"
    POSITIVE_EXCHANGE_CURRENT_DENSITY = "positive_exchange_current_density"

    # Electrolyte potentials (SPMe/DFN only)
    ELECTROLYTE_POTENTIAL = "electrolyte_potential"

    # Electrode stoichiometries (electrode-level SOC)
    NEGATIVE_STOICHIOMETRY = "negative_stoichiometry"
    POSITIVE_STOICHIOMETRY = "positive_stoichiometry"

    # Solid-phase potential
    NEGATIVE_SOLID_POTENTIAL = "negative_solid_potential"
    POSITIVE_SOLID_POTENTIAL = "positive_solid_potential"

    # Performance metrics
    INTERNAL_RESISTANCE = "internal_resistance"
    EFFICIENCY = "efficiency"

    # Degradation signals
    SEI_THICKNESS = "sei_thickness"
    SEI_FILM_RESISTANCE = "sei_film_resistance"
    LITHIUM_PLATING_CAPACITY = "lithium_plating_capacity"
    LITHIUM_PLATING_THICKNESS = "lithium_plating_thickness"
    LOSS_OF_ACTIVE_MATERIAL = "loss_of_active_material"
    TOTAL_CAPACITY_LOSS = "total_capacity_loss"
    NEGATIVE_PARTICLE_CRACK_LENGTH = "negative_particle_crack_length"

    # Cycling signals (time axis = cycle number)
    CYCLE_DISCHARGE_CAPACITY = "cycle_discharge_capacity"
    CYCLE_CHARGE_CAPACITY = "cycle_charge_capacity"
    CYCLE_COULOMBIC_EFFICIENCY = "cycle_coulombic_efficiency"
    CYCLE_CAPACITY_RETENTION = "cycle_capacity_retention"
