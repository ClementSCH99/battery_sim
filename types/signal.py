# battery_sim/types/signal.py

from enum import Enum

class Signal(Enum):
    TIME = "time"
    VOLTAGE = "voltage"
    CURRENT = "current"
    SOC = "soc"
    TEMPERATURE = "temperature"
    POWER = "power"
    HEAT_GENERATION = "heat_generation"