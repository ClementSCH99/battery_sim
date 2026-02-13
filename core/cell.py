# battery_sim/core/cell.py
from dataclasses import dataclass, field
from battery_sim.core.exceptions import CellValidationError
from typing import Optional, Dict


@dataclass(frozen=True)
class Cell:
    chemistry: str

    # Electical parameters
    nominal_capacity_Ah: Optional[float] = None
    nominal_voltage_V: Optional[float] = None
    internal_resistance_Ohm: Optional[float] = None

    # Geometry parameters
    geometry: Optional[str] = None
    electrode_area_m2: Optional[float] = None
    electrode_thickness_m: Optional[float] = None

    # Thermal parameters
    density_kg_per_m3: Optional[float] = None
    specific_heat_J_per_kgK: Optional[float] = None
    thermal_conductivity_W_per_mK: Optional[float] = None

    # Metadata
    metadata: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.nominal_capacity_Ah is not None and self.nominal_capacity_Ah <= 0:
            raise CellValidationError(
                "Cell nominal capacity must be positive - Cell not valide"
                )
            
        if self.nominal_voltage_V is not None and self.nominal_voltage_V <= 0:
            raise CellValidationError(
                "Cell nominal voltage must be positive - Cell not valide"
                )
