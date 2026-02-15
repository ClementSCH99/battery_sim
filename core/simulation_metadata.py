# battery_sim/core/simulation_metadata.py
"""
SimulationMetadata: Capture timing, configuration, and convergence details.

**Purpose**: Track WHEN a simulation ran, HOW LONG it took, and WHAT configuration was used.
This enables reproducibility and performance analysis.

**Example**:
    metadata = SimulationMetadata(
        timestamp_utc="2026-02-15T10:30:15.123456Z",
        duration_s=2.45,
        solver_type="CasADi",
        solver_iterations=18,
        success=True,
        convergence_reason="Converged"
    )
    print(f"Simulation took {metadata.duration_s:.2f}s with {metadata.solver_iterations} iterations")
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from battery_sim.core.solver import SolverConfig, Solver


@dataclass(frozen=True)
class SimulationMetadata:
    """
    Metadata captured from a simulation run.
    
    **Metadata Categories**:
    1. Timing Information
       - timestamp_utc: When did the simulation start?
       - duration_s: How long did it take?
    
    2. Solver Configuration
       - solver_type: Which solver? (CasADi, SciPy)
       - rtol/atol: Tolerances used
       - solver_iterations: How many time steps/iterations?
    
    3. Convergence Status
       - success: Did it converge successfully?
       - convergence_reason: Why? ("Converged", "Diverged", etc.)
    
    4. Problem Characteristics
       - initial_soc: Starting battery state
       - protocol_steps: How many protocol steps?
    """
    
    timestamp_utc: str
    """ISO 8601 timestamp of when simulation started (e.g., "2026-02-15T10:30:15.123456Z")"""
    
    duration_s: float
    """Wall clock time for simulation in seconds"""
    
    solver_type: str
    """Solver name: "CasADi" or "SciPy" or similar"""
    
    solver_iterations: int = 0
    """Number of solver time steps or Newton iterations"""
    
    success: bool = True
    """True if simulation converged successfully"""
    
    convergence_reason: str = "Converged"
    """Human-readable reason: "Converged", "Diverged", "Max iterations exceeded", etc."""
    
    # Solver configuration snapshot
    rtol: float = 1e-6
    """Relative tolerance used"""
    
    atol: float = 1e-9
    """Absolute tolerance used"""
    
    initial_soc: float = 1.0
    """Battery state of charge at start (0.0 = empty, 1.0 = full)"""
    
    protocol_steps: int = 0
    """Number of protocol steps (charge/discharge/rest cycles) in the simulation"""
    
    @classmethod
    def create(
        cls,
        solver_config: SolverConfig,
        solver_iterations: int = 0,
        success: bool = True,
        convergence_reason: str = "Converged",
        duration_s: float = 0.0,
        protocol_steps: int = 0,
    ) -> "SimulationMetadata":
        """
        Factory method to create metadata from SolverConfig and runtime data.
        
        **Usage**:
            metadata = SimulationMetadata.create(
                solver_config=sim.solver_config,
                solver_iterations=backend_solution.n_steps,
                success=True,
                duration_s=elapsed_time,
                protocol_steps=len(sim.protocol.steps)
            )
        
        **Parameters**:
            solver_config: SolverConfig from simulation
            solver_iterations: Number of time steps/iterations from solver
            success: Did solver converge?
            convergence_reason: Text explanation (for debugging)
            duration_s: Wall-clock time in seconds
            protocol_steps: Number of charge/discharge steps
        """
        return cls(
            timestamp_utc=datetime.utcnow().isoformat() + "Z",
            duration_s=duration_s,
            solver_type=solver_config.solver.value,
            solver_iterations=solver_iterations,
            success=success,
            convergence_reason=convergence_reason,
            rtol=solver_config.rtol,
            atol=solver_config.atol,
            initial_soc=solver_config.initial_soc,
            protocol_steps=protocol_steps,
        )
    
    def to_dict(self) -> dict:
        """
        Serialize to JSON-compatible dictionary.
        
        **Usage**:
            import json
            json_str = json.dumps(metadata.to_dict())
        """
        return {
            "timestamp_utc": self.timestamp_utc,
            "duration_s": self.duration_s,
            "solver_type": self.solver_type,
            "solver_iterations": self.solver_iterations,
            "success": self.success,
            "convergence_reason": self.convergence_reason,
            "rtol": self.rtol,
            "atol": self.atol,
            "initial_soc": self.initial_soc,
            "protocol_steps": self.protocol_steps,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SimulationMetadata":
        """
        Deserialize from dictionary.
        
        **Usage**:
            metadata = SimulationMetadata.from_dict(json_data)
        """
        return cls(**data)
    
    def summary(self) -> str:
        """
        Human-readable summary for logging/debugging.
        
        **Example Output**:
            Simulation Metadata:
              Timestamp: 2026-02-15T10:30:15.123456Z
              Duration: 2.45 seconds
              Solver: CasADi (18 iterations)
              Convergence: Converged
              Configuration: rtol=1e-6, atol=1e-9, initial_soc=1.0
        """
        status_text = "Converged" if self.success else "Failed"
        return f"""Simulation Metadata:
  Timestamp: {self.timestamp_utc}
  Duration: {self.duration_s:.3f} seconds
  Solver: {self.solver_type} ({self.solver_iterations} iterations)
  Convergence: {status_text}
  Configuration: rtol={self.rtol:.0e}, atol={self.atol:.0e}, initial_soc={self.initial_soc:.2f}"""
