# battery_sim/core/model.py
from enum import Enum

class Model(Enum):
    SPM = "single_particule"
    DFN = "doyle_fuller_newman"