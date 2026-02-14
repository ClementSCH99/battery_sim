# battery_sim/backend/pybamm_signal
from battery_sim.types.signal import Signal

PYBAMM_SIGNAL_MAP = {
    Signal.TIME: ("Time [s]", "s"),
    Signal.VOLTAGE: ("Terminal voltage [V]", "V"),
    Signal.CURRENT: ("Current [A]", "A"),
    # Signal.SOC: ("X-averaged state of charge", "%"),
    Signal.TEMPERATURE: ("Cell temperature [K]", "K"),
    # Signal.HEAT_GENERATION: ("Heat generation [W]", "W")
}

# TODO: Add PyBaMM signals