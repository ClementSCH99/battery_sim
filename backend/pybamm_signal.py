# battery_sim/backend/pybamm_signal
from battery_sim.types.signal import Signal

# Map Signal enum to PyBaMM signal names.
# Signal.TEMPERATURE is the runtime cell temperature signal, distinct from the
# Environment ambient temperature input.

PYBAMM_SIGNAL_MAP = {
    Signal.TIME: ("Time [s]", "s"),
    Signal.VOLTAGE: ("Terminal voltage [V]", "V"),
    Signal.CURRENT: ("Current [A]", "A"),
    Signal.SOC: ("State of charge", "-"),  # Will try alternatives if not found
    Signal.TEMPERATURE: ("Cell temperature [K]", "K"),
    Signal.HEAT_GENERATION: ("Total heat generation [W]", "W"),
    Signal.IRREVERSIBLE_HEAT: ("Irreversible electrochemical heating [W.m-3]", "W/m³"),
    Signal.REVERSIBLE_HEAT: ("Reversible heating [W.m-3]", "W/m³"),
    Signal.OHMIC_HEAT: ("Ohmic heating [W.m-3]", "W/m³"),
    Signal.CELL_TEMPERATURE: ("X-averaged cell temperature [K]", "K"),
    
    # Internal states (DFN model specifics)
    Signal.ANODE_POTENTIAL: ("Negative electrode potential [V]", "V"),
    Signal.CATHODE_POTENTIAL: ("Positive electrode potential [V]", "V"),
    Signal.OVERPOTENTIAL: ("Overpotential [V]", "V"),
    Signal.ELECTROLYTE_CONCENTRATION: ("Electrolyte concentration [mol.m-3]", "mol.m-3"),

    # Deep electrochemical observability signals
    Signal.NEGATIVE_PARTICLE_SURFACE_CONCENTRATION: (
        "X-averaged negative particle surface concentration [mol.m-3]", "mol/m³"),
    Signal.POSITIVE_PARTICLE_SURFACE_CONCENTRATION: (
        "X-averaged positive particle surface concentration [mol.m-3]", "mol/m³"),
    Signal.NEGATIVE_OCV: (
        "X-averaged negative electrode open-circuit potential [V]", "V"),
    Signal.POSITIVE_OCV: (
        "X-averaged positive electrode open-circuit potential [V]", "V"),
    Signal.NEGATIVE_REACTION_OVERPOTENTIAL: (
        "X-averaged negative electrode reaction overpotential [V]", "V"),
    Signal.POSITIVE_REACTION_OVERPOTENTIAL: (
        "X-averaged positive electrode reaction overpotential [V]", "V"),
    Signal.NEGATIVE_EXCHANGE_CURRENT_DENSITY: (
        "X-averaged negative electrode exchange current density [A.m-2]", "A/m²"),
    Signal.POSITIVE_EXCHANGE_CURRENT_DENSITY: (
        "X-averaged positive electrode exchange current density [A.m-2]", "A/m²"),
    Signal.ELECTROLYTE_POTENTIAL: (
        "X-averaged electrolyte potential [V]", "V"),
    Signal.NEGATIVE_STOICHIOMETRY: (
        "X-averaged negative electrode stoichiometry", "-"),
    Signal.POSITIVE_STOICHIOMETRY: (
        "X-averaged positive electrode stoichiometry", "-"),
    Signal.NEGATIVE_SOLID_POTENTIAL: (
        "X-averaged negative electrode potential [V]", "V"),
    Signal.POSITIVE_SOLID_POTENTIAL: (
        "X-averaged positive electrode potential [V]", "V"),

    # Degradation signals (available when degradation sub-models are active)
    Signal.SEI_THICKNESS: ("X-averaged negative SEI thickness [m]", "m"),
    Signal.SEI_FILM_RESISTANCE: ("X-averaged SEI film resistance [ohm.m2]", "Ω·m²"),
    Signal.LITHIUM_PLATING_CAPACITY: ("Loss of capacity to negative lithium plating [A.h]", "A.h"),
    Signal.LITHIUM_PLATING_THICKNESS: ("X-averaged lithium plating thickness [m]", "m"),
    Signal.LOSS_OF_ACTIVE_MATERIAL: ("Loss of active material in negative electrode [%]", "%"),
    Signal.TOTAL_CAPACITY_LOSS: ("Total capacity lost to side reactions [A.h]", "A.h"),
    Signal.NEGATIVE_PARTICLE_CRACK_LENGTH: ("X-averaged negative particle crack length [m]", "m"),
}

# Alternative PyBaMM signal names for some canonical runtime signals.
# PyBaMM may use different names depending on the model and discharge.
PYBAMM_SIGNAL_ALIASES = {
    Signal.SOC: [
        "State of charge",
        "X-averaged state of charge",
        "State of charge [1]",
        "X-averaged state of charge [1]"
    ],
    Signal.CELL_TEMPERATURE: [
        "X-averaged cell temperature [K]",
        "Cell temperature [K]",
        "Volume-averaged cell temperature [K]",
    ],
    Signal.NEGATIVE_OCV: [
        "X-averaged negative electrode open-circuit potential [V]",
        "Negative electrode open-circuit potential [V]",
    ],
    Signal.POSITIVE_OCV: [
        "X-averaged positive electrode open-circuit potential [V]",
        "Positive electrode open-circuit potential [V]",
    ],
    Signal.ELECTROLYTE_POTENTIAL: [
        "X-averaged electrolyte potential [V]",
        "Electrolyte potential [V]",
    ],
    Signal.NEGATIVE_REACTION_OVERPOTENTIAL: [
        "X-averaged negative electrode reaction overpotential [V]",
        "Negative electrode reaction overpotential [V]",
    ],
    Signal.POSITIVE_REACTION_OVERPOTENTIAL: [
        "X-averaged positive electrode reaction overpotential [V]",
        "Positive electrode reaction overpotential [V]",
    ],
}

# Derived runtime signals calculated from the canonical extracted traces.
DERIVED_SIGNALS = {
    Signal.POWER: ("power", "W"),  # V * I
    Signal.ENERGY: ("energy", "Wh"),  # integral of power
    Signal.CAPACITY: ("capacity", "Ah"),  # integral of abs(current)
    Signal.CAPACITY_FADE: ("capacity_fade", "%"),  # relative to initial
    Signal.INTERNAL_RESISTANCE: ("internal_resistance", "Ω"),  # V / I
    Signal.EFFICIENCY: ("efficiency", "%"),  # round-trip
    # Cycling signals (per-cycle, time axis = cycle number)
    Signal.CYCLE_DISCHARGE_CAPACITY: ("cycle_discharge_capacity", "Ah"),
    Signal.CYCLE_CHARGE_CAPACITY: ("cycle_charge_capacity", "Ah"),
    Signal.CYCLE_COULOMBIC_EFFICIENCY: ("cycle_coulombic_efficiency", "%"),
    Signal.CYCLE_CAPACITY_RETENTION: ("cycle_capacity_retention", "%"),
}
