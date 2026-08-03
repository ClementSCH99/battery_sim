"""Documented cell preset and its engineering metadata."""

from dataclasses import dataclass

from battery_sim.core.cell.model import Cell


@dataclass
class CellPreset:
    """
    A preset battery cell configuration with documentation and EV-relevant metadata.
    
    Physical metadata fields (weight, volume, cost) enable computation of EV-relevant
    metrics like energy density and cost per kWh critical for vehicle design tradeoffs.
    """
    name: str
    chemistry: str
    description: str
    cell: Cell
    weight_kg: float = 0.0                          # Cell weight in kg
    volume_L: float = 0.0                           # Cell volume in liters
    cost_usd: float = 0.0                           # Estimated cell cost in USD
    max_charge_c_rate: float = 1.0                  # Max recommended charge C-rate
    max_discharge_c_rate: float = 2.0               # Max recommended discharge C-rate
    
    @property
    def nominal_energy_Wh(self) -> float:
        """Nominal energy in Wh: capacity × voltage."""
        return self.cell.nominal_capacity_Ah * self.cell.nominal_voltage_V
    
    @property
    def energy_density_Wh_per_kg(self) -> float:
        """Gravimetric energy density (Wh/kg) — critical for weight-sensitive EVs."""
        if self.weight_kg <= 0:
            return 0.0
        return self.nominal_energy_Wh / self.weight_kg
    
    @property
    def energy_density_Wh_per_L(self) -> float:
        """Volumetric energy density (Wh/L) — critical for space-constrained EVs."""
        if self.volume_L <= 0:
            return 0.0
        return self.nominal_energy_Wh / self.volume_L
    
    @property
    def cost_per_kWh(self) -> float:
        """Cost per kWh ($/kWh) — critical for EV affordability."""
        if self.nominal_energy_Wh <= 0:
            return 0.0
        return (self.cost_usd / self.nominal_energy_Wh) * 1000
    
    @property
    def cycle_life_cycles(self) -> int:
        """Extract cycle life from metadata if available."""
        if "cycle_life" not in self.cell.metadata:
            return 0
        cycle_str = self.cell.metadata["cycle_life"]
        # Parse "3000-5000" format, return lower bound
        if "-" in cycle_str:
            return int(cycle_str.split("-")[0])
        try:
            return int(cycle_str)
        except (ValueError, TypeError):
            return 0

