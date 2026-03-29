# battery_sim/core/degradation.py
from dataclasses import dataclass


@dataclass(frozen=True)
class DegradationConfig:
    """Domain-level degradation settings (backend-agnostic).

    Each flag enables a degradation mechanism during cycling simulations.
    The backend is responsible for translating these booleans into the
    correct solver/model options.
    """

    sei_growth: bool = False
    lithium_plating: bool = False
    active_material_loss: bool = False

    def any_enabled(self) -> bool:
        """Return True if at least one degradation mechanism is active."""
        return self.sei_growth or self.lithium_plating or self.active_material_loss

    def validate(self) -> None:
        """Validate the configuration (all-false is valid — no degradation)."""
        pass
