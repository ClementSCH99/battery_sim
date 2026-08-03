"""Curated cell-level simulations used as scientific regression references.

Reference cases are intentionally small and literature-backed. They validate
conventions and conservation relationships; they are not calibrated digital
twins and must not be used as commercial-cell acceptance limits.
"""

from dataclasses import dataclass

from battery_sim.core.cell import Cell
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol
from battery_sim.core.simulation import Simulation
from battery_sim.core.solver import SolverConfig
from battery_sim.types.signal import Signal


@dataclass(frozen=True)
class ReferenceCase:
    """Definition and expected invariants of a reproducible simulation."""

    name: str
    purpose: str
    preset_name: str
    parameter_set: str
    model: Model
    c_rate: float
    duration_s: float
    initial_soc: float
    ambient_temperature_C: float
    lower_voltage_V: float
    upper_voltage_V: float
    required_signals: tuple[Signal, ...] = (
        Signal.TIME,
        Signal.VOLTAGE,
        Signal.CURRENT,
        Signal.POWER,
        Signal.ENERGY,
        Signal.CAPACITY,
    )

    @property
    def current_A(self) -> float:
        """Positive current following the discharge-positive convention."""
        capacity_Ah = Cell.preset(self.preset_name).nominal_capacity_Ah
        if capacity_Ah is None:
            raise ValueError(f"Reference preset {self.preset_name} has no capacity")
        return self.c_rate * capacity_Ah

    @property
    def expected_discharged_capacity_Ah(self) -> float:
        """Capacity imposed by constant current before any cut-off event."""
        return self.current_A * self.duration_s / 3600.0

    def build_simulation(self) -> Simulation:
        """Build the canonical request without selecting a concrete backend."""
        return Simulation(
            cell=Cell.preset(self.preset_name),
            model=self.model,
            protocol=Protocol.cc(current_A=self.current_A, duration_s=self.duration_s),
            environment=Environment(
                ambient_temperature_C=self.ambient_temperature_C,
                thermal_model="isothermal",
            ),
            solver_config=SolverConfig(initial_soc=self.initial_soc),
        )


@dataclass(frozen=True)
class RestReferenceCase:
    """Reference for an unforced cell whose voltage should remain stable."""

    name: str
    purpose: str
    preset_name: str
    parameter_set: str
    model: Model
    duration_s: float
    initial_soc: float
    ambient_temperature_C: float
    maximum_voltage_drift_V: float

    def build_simulation(self) -> Simulation:
        return Simulation(
            cell=Cell.preset(self.preset_name),
            model=self.model,
            protocol=Protocol.rest(self.duration_s),
            environment=Environment(
                ambient_temperature_C=self.ambient_temperature_C,
                thermal_model="isothermal",
            ),
            solver_config=SolverConfig(initial_soc=self.initial_soc),
        )


@dataclass(frozen=True)
class CCCVReferenceCase:
    """Reference for charge sign, voltage cut-off and taper behavior."""

    name: str
    purpose: str
    preset_name: str
    parameter_set: str
    model: Model
    charge_c_rate: float
    taper_c_rate: float
    initial_soc: float
    ambient_temperature_C: float
    upper_voltage_V: float

    @property
    def charge_current_A(self) -> float:
        capacity_Ah = Cell.preset(self.preset_name).nominal_capacity_Ah
        if capacity_Ah is None:
            raise ValueError(f"Reference preset {self.preset_name} has no capacity")
        return self.charge_c_rate * capacity_Ah

    @property
    def taper_current_A(self) -> float:
        capacity_Ah = Cell.preset(self.preset_name).nominal_capacity_Ah
        if capacity_Ah is None:
            raise ValueError(f"Reference preset {self.preset_name} has no capacity")
        return self.taper_c_rate * capacity_Ah

    def build_simulation(self) -> Simulation:
        return Simulation(
            cell=Cell.preset(self.preset_name),
            model=self.model,
            protocol=Protocol.cccv(
                charge_current_A=self.charge_current_A,
                cutoff_voltage_V=self.upper_voltage_V,
                taper_current_A=self.taper_current_A,
            ),
            environment=Environment(
                ambient_temperature_C=self.ambient_temperature_C,
                thermal_model="isothermal",
            ),
            solver_config=SolverConfig(initial_soc=self.initial_soc),
        )


LFP_PRADA_SPM_DISCHARGE = ReferenceCase(
    name="lfp_prada_spm_0p5c_discharge",
    purpose="Check an LFP discharge against the Prada2013 parameterization.",
    preset_name="LFP_PRADA_2P3AH",
    parameter_set="Prada2013",
    model=Model.SPM,
    c_rate=0.5,
    duration_s=300.0,
    initial_soc=0.8,
    ambient_temperature_C=25.0,
    lower_voltage_V=2.0,
    upper_voltage_V=3.6,
)

NMC_CHEN_SPM_DISCHARGE = ReferenceCase(
    name="nmc_chen_spm_0p5c_discharge",
    purpose="Check an NMC discharge against the Chen2020 LG M50 parameterization.",
    preset_name="NMC_CHEN_LGM50",
    parameter_set="Chen2020",
    model=Model.SPM,
    c_rate=0.5,
    duration_s=300.0,
    initial_soc=0.8,
    ambient_temperature_C=25.0,
    lower_voltage_V=2.5,
    upper_voltage_V=4.2,
)

REFERENCE_CASES: tuple[ReferenceCase, ...] = (
    LFP_PRADA_SPM_DISCHARGE,
    NMC_CHEN_SPM_DISCHARGE,
)

NMC_CHEN_SPM_REST = RestReferenceCase(
    name="nmc_chen_spm_rest",
    purpose="Check zero-current conservation during an isothermal rest.",
    preset_name="NMC_CHEN_LGM50",
    parameter_set="Chen2020",
    model=Model.SPM,
    duration_s=300.0,
    initial_soc=0.5,
    ambient_temperature_C=25.0,
    maximum_voltage_drift_V=1e-5,
)

NMC_CHEN_SPM_CCCV_CHARGE = CCCVReferenceCase(
    name="nmc_chen_spm_1c_cccv_charge",
    purpose="Check charge sign, voltage cut-off and current taper with Chen2020.",
    preset_name="NMC_CHEN_LGM50",
    parameter_set="Chen2020",
    model=Model.SPM,
    charge_c_rate=1.0,
    taper_c_rate=0.05,
    initial_soc=0.2,
    ambient_temperature_C=25.0,
    upper_voltage_V=4.2,
)

PROTOCOL_REFERENCE_CASES: tuple[RestReferenceCase | CCCVReferenceCase, ...] = (
    NMC_CHEN_SPM_REST,
    NMC_CHEN_SPM_CCCV_CHARGE,
)


def get_reference_case(name: str) -> ReferenceCase:
    """Return a reference case by stable name."""
    for case in REFERENCE_CASES:
        if case.name == name:
            return case
    available = ", ".join(case.name for case in REFERENCE_CASES)
    raise ValueError(f"Unknown reference case {name!r}. Available: {available}")
