"""EV drive cycle profiles and utilities.

Standard cycles (WLTP, US06, UDDS) are normalized power profiles
that can be scaled by vehicle parameters at runtime.

Each profile consists of:
- time_s: list of time points (seconds)
- power_normalized: normalized power at each time point (0.0 = idle, 1.0 = peak)

These are discretized into short constant-power segments for simulation.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DriveCycleProfile:
    """Standard EV drive cycle profile.
    
    Attributes:
        name: Human-readable name (e.g. "WLTP Class 3")
        time_s: List of time points in seconds
        power_normalized: Normalized power at each time point (0.0 to 1.0)
        description: Physical description of the cycle
    """
    name: str
    time_s: list[float]
    power_normalized: list[float]
    description: str

    def __post_init__(self):
        """Validate profile consistency."""
        if len(self.time_s) != len(self.power_normalized):
            raise ValueError(
                f"Mismatch: {len(self.time_s)} time points vs "
                f"{len(self.power_normalized)} power values"
            )
        
        if len(self.time_s) < 2:
            raise ValueError("Drive cycle must have at least 2 time points")
        
        # Check monotonic time
        for i in range(len(self.time_s) - 1):
            if self.time_s[i] >= self.time_s[i + 1]:
                raise ValueError(f"Time not monotonic: {self.time_s[i]} >= {self.time_s[i + 1]}")
        
        # Check power in valid range
        for p in self.power_normalized:
            if not (0.0 <= p <= 1.0):
                raise ValueError(f"Power out of range [0, 1]: {p}")


# ==============================================================================
# Built-in Drive Cycle Profiles
# ==============================================================================

WLTP_CLASS3 = DriveCycleProfile(
    name="WLTP Class 3",
    description=(
        "Worldwide harmonized Light-duty vehicle Test Procedure (WLTP) Class 3. "
        "~1800s mixed driving: urban (Phase 1), rural (Phase 2), "
        "motorway (Phase 3), extra-high speed (Phase 4). "
        "Representative of European mixed-mode driving."
    ),
    time_s=[
        # Phase 1: Low intensity urban (0-590s)
        0, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 590,
        # Phase 2: Medium intensity rural (591-1023s)
        591, 650, 710, 770, 830, 890, 950, 1000, 1023,
        # Phase 3: High intensity motorway (1024-1411s)
        1024, 1080, 1140, 1200, 1260, 1320, 1380, 1411,
        # Phase 4: Extra-high speed (1412-1800s)
        1412, 1470, 1530, 1590, 1650, 1710, 1770, 1800,
    ],
    power_normalized=[
        # Phase 1 (urban): low power, frequent stops
        0.0, 0.10, 0.15, 0.12, 0.08, 0.20, 0.10, 0.15, 0.12, 0.10, 0.05, 0.0,
        # Phase 2 (rural): medium power, fewer stops
        0.0, 0.25, 0.40, 0.35, 0.30, 0.45, 0.38, 0.35, 0.0,
        # Phase 3 (motorway): high power, sustained
        0.0, 0.55, 0.65, 0.60, 0.70, 0.62, 0.58, 0.50,
        # Phase 4 (extra-high): very high power
        0.50, 0.70, 0.75, 0.80, 0.75, 0.70, 0.65, 0.0,
    ],
)

US06 = DriveCycleProfile(
    name="US06",
    description=(
        "EPA Supplemental Federal Test Procedure (US06). "
        "~600s aggressive driving with rapid acceleration/deceleration. "
        "Represents real-world highway and city driving with higher speeds "
        "and more aggressive acceleration than UDDS."
    ),
    time_s=[
        0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300,
        330, 360, 390, 420, 450, 480, 510, 540, 570, 600,
    ],
    power_normalized=[
        0.0, 0.40, 0.65, 0.80, 0.85, 0.75, 0.60, 0.70, 0.80, 0.65, 0.50,
        0.60, 0.70, 0.75, 0.70, 0.60, 0.65, 0.55, 0.40, 0.20, 0.0,
    ],
)

UDDS = DriveCycleProfile(
    name="UDDS",
    description=(
        "Urban Dynamometer Driving Schedule (UDDS). "
        "~1370s city driving with frequent acceleration/deceleration cycles. "
        "Represents typical urban traffic with many stops and starts. "
        "Lower average power than highway cycles."
    ),
    time_s=[
        0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200,
        220, 240, 260, 280, 300, 320, 340, 360, 380, 400,
        420, 450, 480, 510, 540, 570, 600, 640, 680, 720,
        760, 800, 850, 900, 950, 1000, 1050, 1100, 1150, 1200,
        1250, 1300, 1350, 1370,
    ],
    power_normalized=[
        0.0, 0.15, 0.25, 0.30, 0.25, 0.20, 0.0, 0.10, 0.20, 0.30, 0.35,
        0.30, 0.20, 0.10, 0.0, 0.15, 0.25, 0.32, 0.28, 0.18, 0.08,
        0.0, 0.20, 0.35, 0.40, 0.35, 0.20, 0.0, 0.15, 0.30, 0.35,
        0.32, 0.25, 0.38, 0.42, 0.35, 0.25, 0.15, 0.05, 0.0, 0.10,
        0.25, 0.30, 0.15, 0.0,
    ],
)

# Registry of all available profiles
_PROFILES = {
    "WLTP": WLTP_CLASS3,
    "WLTP_CLASS3": WLTP_CLASS3,
    "US06": US06,
    "UDDS": UDDS,
}


def list_drive_cycles() -> list[str]:
    """Return list of available drive cycle names."""
    return sorted(list(_PROFILES.keys()))


def get_drive_cycle(name: str) -> DriveCycleProfile:
    """Load a drive cycle profile by name.
    
    Args:
        name: Profile name (case-insensitive), e.g. "WLTP", "US06", "UDDS"
    
    Returns:
        DriveCycleProfile instance
    
    Raises:
        KeyError: If cycle name not found
    """
    normalized_name = name.upper()
    if normalized_name not in _PROFILES:
        available = ", ".join(list_drive_cycles())
        raise KeyError(
            f"Drive cycle '{name}' not found. Available: {available}"
        )
    return _PROFILES[normalized_name]


def scale_drive_cycle(
    profile: DriveCycleProfile,
    vehicle_mass_kg: float = 1800.0,
    peak_power_kW: float = 150.0,
) -> list[tuple[float, float]]:
    """Scale a normalized drive cycle to actual power and duration segments.
    
    Discretizes the cycle into constant-power steps by converting time points
    into power-duration pairs (power_W, duration_s).
    
    Args:
        profile: DriveCycleProfile (with normalized power 0.0–1.0)
        vehicle_mass_kg: Vehicle mass used for a simple linear scaling relative
            to the 1800 kg reference profile
        peak_power_kW: Peak demand of the normalized reference profile
    
    Returns:
        List of (power_W, duration_s) tuples representing constant-power segments
    
    Example:
        >>> profile = get_drive_cycle("WLTP")
        >>> segments = scale_drive_cycle(profile, peak_power_kW=150.0)
        >>> # segments = [(30000, 30), (45000, 30), ...]
    """
    if vehicle_mass_kg <= 0:
        raise ValueError("vehicle_mass_kg must be positive")
    if peak_power_kW <= 0:
        raise ValueError("peak_power_kW must be positive")

    # These bundled profiles are normalized load shapes, not speed traces.
    # Linear mass scaling is therefore an explicit screening assumption; a
    # longitudinal vehicle model is required for a predictive power trace.
    reference_mass_kg = 1800.0
    mass_scale = vehicle_mass_kg / reference_mass_kg
    peak_power_W = peak_power_kW * mass_scale * 1000.0
    segments: list[tuple[float, float]] = []
    
    for i in range(len(profile.time_s) - 1):
        time_start = float(profile.time_s[i])
        time_end = float(profile.time_s[i + 1])
        power_normalized = float(profile.power_normalized[i])
        
        duration_s = float(time_end - time_start)
        power_W = power_normalized * peak_power_W
        
        segments.append((power_W, duration_s))
    
    return segments
