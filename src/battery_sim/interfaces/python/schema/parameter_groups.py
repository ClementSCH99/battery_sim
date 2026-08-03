"""Human-readable parameter group descriptions."""

_DERIVED_METRIC_METADATA: dict = {
    "peak_voltage_V": {
        "unit": "V",
        "interpretation": "Derived summary metric: maximum voltage reached during operation.",
        "use_cases": ["charger_design", "electronics_protection", "overcharge_detection"],
        "typical_range": "≤ 4.2V for lithium safety",
    },
    "peak_current_A": {
        "unit": "A",
        "interpretation": "Derived summary metric: maximum current magnitude during operation.",
        "use_cases": ["pack_design", "connector_sizing", "thermal_design"],
        "typical_range": "Depends on capacity and load profile",
    },
    "peak_power_W": {
        "unit": "W",
        "interpretation": "Derived summary metric: maximum instantaneous power.",
        "use_cases": ["ev_design", "power_tool_specs", "fast_charging"],
        "typical_range": "10W - 10kW depending on chemistry",
    },
}
