# battery_sim/backend/pybamm_signal
from battery_sim.types.signal import Signal

PYBAMM_SIGNAL_MAP = {
    Signal.TIME: ("Time [s]", "s"),
    Signal.VOLTAGE: ("Terminal voltage [V]", "V"),
    Signal.CURRENT: ("Current [A]", "A"),
    Signal.SOC: ("State of charge", "-"),
    Signal.TEMPERATURE: ("Cell temperature [K]", "K"),
    Signal.HEAT_GENERATION: ("Total heat generation [W]", "W"),
    
    # Internal states (DFN model specifics)
    Signal.ANODE_POTENTIAL: ("Negative electrode potential [V]", "V"),
    Signal.CATHODE_POTENTIAL: ("Positive electrode potential [V]", "V"),
    Signal.OVERPOTENTIAL: ("Overpotential [V]", "V"),
    Signal.ELECTROLYTE_CONCENTRATION: ("Electrolyte concentration [mol.m-3]", "mol.m-3"),
}

# Derived signals (calculated, not directly from PyBaMM)
DERIVED_SIGNALS = {
    Signal.POWER: ("power", "W"),  # V * I
    Signal.ENERGY: ("energy", "Wh"),  # integral of power
    Signal.CAPACITY: ("capacity", "Ah"),  # integral of abs(current)
    Signal.CAPACITY_FADE: ("capacity_fade", "%"),  # relative to initial
    Signal.INTERNAL_RESISTANCE: ("internal_resistance", "Ω"),  # V / I
    Signal.EFFICIENCY: ("efficiency", "%"),  # round-trip
}