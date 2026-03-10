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
    
    # Internal states (DFN model specifics)
    Signal.ANODE_POTENTIAL: ("Negative electrode potential [V]", "V"),
    Signal.CATHODE_POTENTIAL: ("Positive electrode potential [V]", "V"),
    Signal.OVERPOTENTIAL: ("Overpotential [V]", "V"),
    Signal.ELECTROLYTE_CONCENTRATION: ("Electrolyte concentration [mol.m-3]", "mol.m-3"),
}

# Alternative PyBaMM signal names for some canonical runtime signals.
# PyBaMM may use different names depending on the model and discharge.
PYBAMM_SIGNAL_ALIASES = {
    Signal.SOC: [
        "State of charge",
        "X-averaged state of charge",
        "State of charge [1]",
        "X-averaged state of charge [1]"
    ]
}

# Derived runtime signals calculated from the canonical extracted traces.
DERIVED_SIGNALS = {
    Signal.POWER: ("power", "W"),  # V * I
    Signal.ENERGY: ("energy", "Wh"),  # integral of power
    Signal.CAPACITY: ("capacity", "Ah"),  # integral of abs(current)
    Signal.CAPACITY_FADE: ("capacity_fade", "%"),  # relative to initial
    Signal.INTERNAL_RESISTANCE: ("internal_resistance", "Ω"),  # V / I
    Signal.EFFICIENCY: ("efficiency", "%"),  # round-trip
}