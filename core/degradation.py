# battery_sim/core/degradation.py
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UsageProfile:
    """Representative usage patterns for battery lifetime prediction.
    
    Used by predict_lifetime() to convert from cycles to calendar years,
    and to configure storage/rest conditions for calendar aging modeling.
    """
    daily_km: float = 40.0                # Average daily driving distance (km)
    daily_charge_cycles: float = 1.0      # How many charge cycles per day
    storage_temperature_C: float = 25.0   # Temperature when parked (°C)
    storage_soc: float = 0.5              # Typical SOC when parked (0-1)
    fast_charge_ratio: float = 0.1        # Fraction of charges that are fast (DC)


_VALID_SEI_MODELS = frozenset({
    "ec reaction limited",
    "solvent-diffusion limited",
    "electron-migration limited",
    "interstitial-diffusion limited",
    "reaction limited",
})

_VALID_LITHIUM_PLATING_MODELS = frozenset({
    "irreversible",
    "reversible",
    "partially reversible",
})

_VALID_AM_LOSS_MODELS = frozenset({
    "stress-driven",
    "reaction-driven",
    "stress and reaction-driven",
})

_VALID_PARTICLE_MECHANICS = frozenset({
    "swelling only",
    "swelling and cracking",
})


@dataclass(frozen=True)
class ResolvedDegradation:
    """Resolved degradation options ready for backend consumption."""
    sei: Optional[str] = None
    lithium_plating: Optional[str] = None
    am_loss: Optional[str] = None
    sei_on_cracks: bool = False
    particle_mechanics: Optional[str] = None


@dataclass(frozen=True)
class DegradationConfig:
    """Domain-level degradation settings (backend-agnostic).

    Supports both the legacy boolean API and explicit sub-model selectors.
    When a sub-model selector is set, it takes priority over the boolean flag.
    Calendar aging is modeled when both sei_growth and calendar_aging are True.
    """

    # --- Legacy boolean API (backward compatible) ---
    sei_growth: bool = False
    lithium_plating: bool = False
    active_material_loss: bool = False

    # --- Calendar aging ---
    calendar_aging: bool = False                # Enable SEI growth during rest
    storage_temperature_C: float = 25.0         # Storage temperature (°C)
    storage_soc: float = 0.5                    # Storage SOC (0-1)

    # --- Sub-model selectors (take priority when set) ---
    sei_model: Optional[str] = None
    lithium_plating_model: Optional[str] = None
    am_loss_model: Optional[str] = None

    # --- Cross-coupling options ---
    sei_on_cracks: bool = False
    particle_mechanics: Optional[str] = None

    def any_enabled(self) -> bool:
        """Return True if at least one degradation mechanism is active."""
        return (
            self.sei_growth
            or self.lithium_plating
            or self.active_material_loss
            or self.calendar_aging
            or self.sei_model is not None
            or self.lithium_plating_model is not None
            or self.am_loss_model is not None
            or self.sei_on_cracks
            or self.particle_mechanics is not None
        )

    def validate(self) -> None:
        """Validate that all sub-model strings are in the allowed sets."""
        if self.sei_model is not None and self.sei_model not in _VALID_SEI_MODELS:
            raise ValueError(
                f"Invalid SEI model '{self.sei_model}'. "
                f"Valid options: {sorted(_VALID_SEI_MODELS)}"
            )
        if self.lithium_plating_model is not None and self.lithium_plating_model not in _VALID_LITHIUM_PLATING_MODELS:
            raise ValueError(
                f"Invalid lithium plating model '{self.lithium_plating_model}'. "
                f"Valid options: {sorted(_VALID_LITHIUM_PLATING_MODELS)}"
            )
        if self.am_loss_model is not None and self.am_loss_model not in _VALID_AM_LOSS_MODELS:
            raise ValueError(
                f"Invalid AM loss model '{self.am_loss_model}'. "
                f"Valid options: {sorted(_VALID_AM_LOSS_MODELS)}"
            )
        if self.particle_mechanics is not None and self.particle_mechanics not in _VALID_PARTICLE_MECHANICS:
            raise ValueError(
                f"Invalid particle mechanics model '{self.particle_mechanics}'. "
                f"Valid options: {sorted(_VALID_PARTICLE_MECHANICS)}"
            )

    def resolve(self) -> ResolvedDegradation:
        """Resolve the configuration into concrete sub-model strings.

        Explicit sub-model selectors take priority over legacy booleans.
        """
        self.validate()

        sei = self.sei_model
        if sei is None and self.sei_growth:
            sei = "ec reaction limited"

        lp = self.lithium_plating_model
        if lp is None and self.lithium_plating:
            lp = "irreversible"

        am = self.am_loss_model
        if am is None and self.active_material_loss:
            am = "stress-driven"

        return ResolvedDegradation(
            sei=sei,
            lithium_plating=lp,
            am_loss=am,
            sei_on_cracks=self.sei_on_cracks,
            particle_mechanics=self.particle_mechanics,
        )
