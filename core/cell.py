# battery_sim/core/cell.py
from dataclasses import dataclass, field
from battery_sim.core.exceptions import CellValidationError
from typing import Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from battery_sim.core.cell_presets import CellPresets


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

    @classmethod
    def preset(cls, preset_name: str) -> "Cell":
        """
        Create a Cell from a preset configuration.
        
        Args:
            preset_name: Name of preset (e.g., 'LFP_5AH', 'NMC_5AH')
            
        Returns:
            Cell with preset parameters
            
        Raises:
            ValueError: If preset not found
            
        Example:
            >>> cell = Cell.preset('LFP_5AH')
            >>> cell.chemistry
            'LFP'
            >>> cell.nominal_capacity_Ah
            5.0
        """
        # Lazy import to avoid circular dependency
        from battery_sim.core.cell_presets import CellPresets
        return CellPresets.get_cell(preset_name)

    @classmethod
    def list_presets(cls) -> list[str]:
        """List all available cell presets."""
        from battery_sim.core.cell_presets import CellPresets
        return CellPresets.list_all()

