"""Composed high-level engineering API."""

from typing import Dict, List, Any, Optional
from battery_sim.application.services import (
    ComparisonService,
    SensitivityService,
)
from battery_sim.interfaces.python.schema import APISchema
from battery_sim.interfaces.presenters.result import (
    DualFormatResult,
    InsightExtractor,
)
from battery_sim.application.session import SimulationSession
from battery_sim.core.experiment import Model
from battery_sim.core.experiment import Protocol, ConstantCurrent
from battery_sim.core.simulation import SimulationBackend
from battery_sim.core.experiment import SolverConfig
from battery_sim.interfaces.python.simulation_tool import SimulationToolHandler
from battery_sim.interfaces.python.cell_tools import CellToolHandler
from battery_sim.interfaces.python.charging_tools import ChargingToolHandler
from battery_sim.interfaces.python.degradation_tools import DegradationToolHandler
from battery_sim.interfaces.python.discovery_tools import DiscoveryToolHandler, discover_agent_tools
from battery_sim.interfaces.python.investigation_tools import EVAssumptions, InvestigationToolHandler
from battery_sim.interfaces.python.operating_tools import OperatingToolHandler
from battery_sim.interfaces.python.planning_tools import ExperimentPlanningToolHandler
from battery_sim.interfaces.python.session_tools import SessionToolHandler
from battery_sim.interfaces.python.test_comparison_tools import ModelTestComparisonToolHandler
from battery_sim.interfaces.python.vehicle_tools import VehicleToolHandler
from battery_sim.interfaces.python.tool_registry.comparison import ComparisonToolsMixin
from battery_sim.interfaces.python.tool_registry.discovery import DiscoveryToolsMixin
from battery_sim.interfaces.python.tool_registry.limits import LimitsToolsMixin
from battery_sim.interfaces.python.tool_registry.simulation import SimulationToolsMixin

class AgentAPI(
    DiscoveryToolsMixin,
    ComparisonToolsMixin,
    SimulationToolsMixin,
    LimitsToolsMixin,
):
    """High-level, LLM-friendly battery investigation API."""

    def __init__(
        self,
        session_name: str = "Battery Investigation",
        default_protocol: Optional[Protocol] = None,
        default_model: Model = Model.SPM,
        default_solver_config: Optional[SolverConfig] = None,
        backend: Optional[SimulationBackend] = None,
    ):
        """
        Initialize AgentAPI with configuration.

        Args:
            session_name: Name for tracking this investigation
            default_protocol: Default discharge protocol (if None, uses standard)
            default_model: Battery model (SPM or DFN)
            default_solver_config: Solver configuration (if None, uses defaults)
            backend: Simulation engine adapter. Defaults to PyBaMM. Supplying a
                backend keeps the agent facade testable and independent from a
                particular simulation engine.
        """

        # Infrastructure
        self.schema = APISchema()
        self.session = SimulationSession(name=session_name)

        # Configuration
        self.default_protocol = default_protocol or Protocol(steps=[
            ConstantCurrent(current_A=5.0, _duration_s=3600),  # 1-hour discharge
        ])
        self.default_model = default_model
        self.default_solver_config = default_solver_config or SolverConfig()
        from battery_sim.composition import create_backend
        self._backend = backend if backend is not None else create_backend()
        self.comparison_service = ComparisonService(backend=self._backend)
        self.sensitivity_service = SensitivityService(backend=self._backend)
        self._cell_tools = CellToolHandler(schema=self.schema)
        self._discovery_tools = DiscoveryToolHandler(
            schema=self.schema,
            catalog_provider=self.get_available_tools,
        )
        self._degradation_tools = DegradationToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._charging_tools = ChargingToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._operating_tools = OperatingToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
        )
        self._session_tools = SessionToolHandler(session=self.session)
        self._planning_tools = ExperimentPlanningToolHandler(
            execution_model=self.default_model,
        )
        self._test_comparison_tools = ModelTestComparisonToolHandler(
            backend=self._backend,
            session=self.session,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
        )
        self._vehicle_tools = VehicleToolHandler(
            session=self.session,
        )
        self._investigation_tools = InvestigationToolHandler(
            backend=self._backend,
            session=self.session,
            default_protocol=self.default_protocol,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
            comparison_service=self.comparison_service,
            sensitivity_service=self.sensitivity_service,
        )
        self._simulation_tool = SimulationToolHandler(
            backend=self._backend,
            session=self.session,
            default_protocol=self.default_protocol,
            default_model=self.default_model,
            default_solver_config=self.default_solver_config,
        )


# Publish decorated tools directly on the facade so introspection sees
# the stable public surface without knowing about implementation mixins.
AgentAPI.describe_api = DiscoveryToolsMixin.describe_api
AgentAPI.plan_experiment = DiscoveryToolsMixin.plan_experiment
AgentAPI.compare_test_data = DiscoveryToolsMixin.compare_test_data
AgentAPI.list_presets = ComparisonToolsMixin.list_presets
AgentAPI.compare_presets = ComparisonToolsMixin.compare_presets
AgentAPI.sensitivity_analysis = ComparisonToolsMixin.sensitivity_analysis
AgentAPI.check_feasibility = ComparisonToolsMixin.check_feasibility
AgentAPI.run_simulation = SimulationToolsMixin.run_simulation
AgentAPI.predict_lifetime = SimulationToolsMixin.predict_lifetime
AgentAPI.pack_sizing = SimulationToolsMixin.pack_sizing
AgentAPI.cell_selection_wizard = SimulationToolsMixin.cell_selection_wizard
AgentAPI.warranty_analysis = SimulationToolsMixin.warranty_analysis
AgentAPI.optimize_charging = SimulationToolsMixin.optimize_charging
AgentAPI.operating_window = LimitsToolsMixin.operating_window
AgentAPI.derating_curves = LimitsToolsMixin.derating_curves
AgentAPI.estimate_range = LimitsToolsMixin.estimate_range
AgentAPI.compare_charging_strategies = LimitsToolsMixin.compare_charging_strategies
AgentAPI.get_session_summary = LimitsToolsMixin.get_session_summary
