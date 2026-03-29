# battery_sim/core/simulation_run.py
"""
SimulationRun: Complete wrapper combining Result with Metadata, Errors, and Diagnostics.

**The Big Picture**:
    A SimulationRun is the COMPLETE OUTPUT of a single battery simulation.

    The canonical contract is:
        simulation.run() → SimulationRun
            ├─ result: Result (signal payload)
            ├─ metadata: SimulationMetadata (when, how long, what config)
            ├─ errors: List[SimulationError] (what went wrong?)
            └─ diagnostics: ConvergenceDiagnostics (solver performance)

    Result is part of SimulationRun, not a competing execution return type.

**Key Insight**: By bundling these together, we have FULL OBSERVABILITY.
Any simulation run can be fully debugged and reproduced.

**Example Usage**:
    run = simulation.run()
    
    # Access results like before (backward compatible)
    efficiency = run.result.charge_discharge_efficiency()
    
    # NEW: Access full simulation context
    print(f"Simulation took {run.metadata.duration_s:.2f}s")
    print(f"Solver used {run.diagnostics.avg_newton_iterations:.1f} iterations/step")
    
    if run.errors:
        for error in run.errors:
            print(f"ERROR: {error.summary()}")
    
    # NEW: Full reproducibility (for logging/database storage)
    json_data = json.dumps(run.to_dict())
"""

from dataclasses import dataclass
from typing import List
import json

from battery_sim.core.result import Result
from battery_sim.core.simulation_metadata import SimulationMetadata
from battery_sim.core.simulation_error import SimulationError
from battery_sim.core.convergence_diagnostics import ConvergenceDiagnostics


@dataclass
class SimulationRun:
    """Complete output of a single battery simulation.

    Attributes:
        result: Signal payload (voltage, current, SOC, etc.).
        metadata: Timestamp, duration, solver config, convergence status.
        errors: Physical/numerical violations (empty if clean).
        diagnostics: Solver iteration statistics.

    Key methods:
        is_successful() — True when converged with no critical errors.
        summary() — Multi-section human-readable report.
        to_dict() — Serialise metadata, errors, and diagnostics to JSON.
    """
    
    result: Result
    """Embedded signal payload for the run."""
    
    metadata: SimulationMetadata
    """When did it run? How long? What config? Convergence status?"""
    
    errors: List[SimulationError]
    """What went wrong? (empty if successful)"""
    
    diagnostics: ConvergenceDiagnostics
    """How did the solver perform? (iterations, stiffness, etc.)"""
    
    def is_successful(self) -> bool:
        """
        True if simulation completed without critical errors.
        
        Success = metadata.success AND no critical errors
        """
        return self.metadata.success and not any(e.is_critical() for e in self.errors)
    
    def has_warnings(self) -> bool:
        """True if there are any non-critical errors/warnings."""
        return any(e.is_warning() for e in self.errors)
    
    def has_critical_errors(self) -> bool:
        """True if there are any critical errors."""
        return any(e.is_critical() for e in self.errors)
    
    def get_critical_errors(self) -> List[SimulationError]:
        """Returns list of critical errors (empty if none)."""
        return [e for e in self.errors if e.is_critical()]
    
    def get_warnings(self) -> List[SimulationError]:
        """Returns list of warnings (empty if none)."""
        return [e for e in self.errors if e.is_warning()]
    
    def summary(self) -> str:
        """
        Complete multi-part summary for logging/debugging.
        
        Example Output:
            ==================== SIMULATION RUN SUMMARY ====================
            
            Simulation Metadata:
              Timestamp: 2026-02-15T10:30:15.123456Z
              Duration: 2.45 seconds
              Solver: CasADi (18 iterations)
              Convergence: Converged
              Configuration: rtol=1e-6, atol=1e-9, initial_soc=1.0
            
            Convergence Diagnostics:
              Time Steps: 500
              Newton Iterations: avg=12 (range: 8-25)
              Problem: well-conditioned (fast solve)
              Status: No issues
            
            Errors/Warnings:
              No errors detected
            
            ================================================================
        """
        lines = []
        lines.append("=" * 66)
        lines.append("SIMULATION RUN SUMMARY")
        lines.append("=" * 66)
        lines.append("")
        
        # Metadata section
        lines.append(self.metadata.summary())
        lines.append("")
        
        # Diagnostics section
        lines.append(self.diagnostics.summary())
        lines.append("")
        
        # Errors section
        if self.errors:
            lines.append("Errors/Warnings:")
            for error in self.errors:
                lines.append(f"  {error.summary()}")
        else:
            lines.append("Errors/Warnings:")
            lines.append("  No errors detected")
        
        lines.append("")
        lines.append("=" * 66)
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """
        Serialize entire run to JSON-compatible dictionary.
        
        **Usage**:
            import json
            json_str = json.dumps(run.to_dict())
            
            # Save to database, log system, or file
            with open("simulation.json", "w") as f:
                json.dump(run.to_dict(), f, indent=2)
        
        **Note**: Result data is not included (preserve Result separate).
        Only metadata, errors, and diagnostics are serialized.
        """
        return {
            "metadata": self.metadata.to_dict(),
            "errors": [e.to_dict() for e in self.errors],
            "diagnostics": self.diagnostics.to_dict(),
            # Note: result is NOT serialized here (would be huge)
            # Results should be stored separately via Result.to_file() etc.
        }
    
    @classmethod
    def from_dict(cls, data: dict, result: Result) -> "SimulationRun":
        """
        Deserialize from dictionary.
        
        **Usage**:
            # Load metadata/errors from JSON
            with open("simulation.json") as f:
                data = json.load(f)
            
            # Reconstruct (need the Result separately)
            run = SimulationRun.from_dict(data, result)
        
        **Parameters**:
            data: Dictionary from to_dict()
            result: The Result object (must be loaded separately)
        """
        metadata = SimulationMetadata.from_dict(data["metadata"])
        errors = [SimulationError.from_dict(e) for e in data.get("errors", [])]
        diagnostics = ConvergenceDiagnostics.from_dict(data["diagnostics"])
        
        return cls(
            result=result,
            metadata=metadata,
            errors=errors,
            diagnostics=diagnostics,
        )
    
    # --- Backward-compatible Result delegates ---
    # These methods forward to self.result for migration convenience.
    # TODO: Deprecate in a future version once all callers use .result directly.

    def get(self, signal):
        """Delegate to result.get()"""
        return self.result.get(signal)
    
    def final(self, signal):
        """Delegate to result.final()"""
        return self.result.final(signal)
    
    def available_signals(self):
        """Delegate to result.available_signals()"""
        return self.result.available_signals()
    
    def soc(self):
        """Delegate to result.soc()"""
        return self.result.soc()
    
    def voltage(self):
        """Delegate to result.voltage()"""
        return self.result.voltage()
    
    def current(self):
        """Delegate to result.current()"""
        return self.result.current()
    
    def temperature(self):
        """Delegate to result.temperature()"""
        return self.result.temperature()
    
    def power(self):
        """Delegate to result.power()"""
        return self.result.power()
    
    def energy(self):
        """Delegate to result.energy()"""
        return self.result.energy()
    
    def capacity(self):
        """Delegate to result.capacity()"""
        return self.result.capacity()
    
    def total_energy(self):
        """Delegate to result.total_energy()"""
        return self.result.total_energy()
    
    def total_capacity_delivered(self):
        """Delegate to result.total_capacity_delivered()"""
        return self.result.total_capacity_delivered()
    
    def peak_power(self):
        """Delegate to result.peak_power()"""
        return self.result.peak_power()
    
    def average_power(self):
        """Delegate to result.average_power()"""
        return self.result.average_power()
    
    def min_voltage(self):
        """Delegate to result.min_voltage()"""
        return self.result.min_voltage()
    
    def max_voltage(self):
        """Delegate to result.max_voltage()"""
        return self.result.max_voltage()
    
    def final_soc(self):
        """Delegate to result.final_soc()"""
        return self.result.final_soc()
    
    def min_temperature(self):
        """Delegate to result.min_temperature()"""
        return self.result.min_temperature()
    
    def max_temperature(self):
        """Delegate to result.max_temperature()"""
        return self.result.max_temperature()
    
    def internal_resistance(self):
        """Delegate to result.internal_resistance()"""
        return self.result.internal_resistance()
    
    def average_internal_resistance(self):
        """Delegate to result.average_internal_resistance()"""
        return self.result.average_internal_resistance()
    
    def round_trip_efficiency(self):
        """Delegate to result.round_trip_efficiency()"""
        return self.result.round_trip_efficiency()
    
    def charged_capacity(self):
        """Delegate to result.charged_capacity()"""
        return self.result.charged_capacity()
    
    def discharged_capacity(self):
        """Delegate to result.discharged_capacity()"""
        return self.result.discharged_capacity()
    
    def net_capacity(self):
        """Delegate to result.net_capacity()"""
        return self.result.net_capacity()
    
    def charged_energy(self):
        """Delegate to result.charged_energy()"""
        return self.result.charged_energy()
    
    def discharged_energy(self):
        """Delegate to result.discharged_energy()"""
        return self.result.discharged_energy()
    
    def net_energy(self):
        """Delegate to result.net_energy()"""
        return self.result.net_energy()
    
    def charge_discharge_efficiency(self):
        """Delegate to result.charge_discharge_efficiency()"""
        return self.result.charge_discharge_efficiency()
    
    def state_variables_summary(self):
        """Delegate to result.state_variables_summary()"""
        return self.result.state_variables_summary()

    def signals(self):
        """Delegate to result.available_signals()"""
        return self.result.available_signals()
    
    def get_signal(self, signal):
        """Delegate to result.get()"""
        return self.result.get(signal)
    
    def plot(self, *args, **kwargs):
        """Delegate to result_plotting.plot_result()."""
        from battery_sim.core.result_plotting import plot_result
        return plot_result(self.result, *args, **kwargs)
    
    def to_file(self, filepath: str, include_metadata: bool = True):
        """
        Save simulation run to file.
        
        **Usage**:
            run.to_file("simulation_results/run_001.json")  # JSON with full metadata
        
        **Parameters**:
            filepath: Output file path (.json)
            include_metadata: If True (default), save complete metadata/errors/diagnostics
        """
        import json
        import os
        
        # Save complete simulation run to JSON
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# Convenience function for backwards compatibility
def ensure_simulation_run(obj) -> SimulationRun:
    """
    Convert Result to SimulationRun or pass through if already SimulationRun.

    **Purpose**: Support legacy call sites while keeping SimulationRun as the
    canonical execution contract.
    
    **Usage**:
        # Code that might receive either type
        run = ensure_simulation_run(obj)
        efficiency = run.result.charge_discharge_efficiency()
        print(f"Took {run.metadata.duration_s:.2f}s")
    """
    if isinstance(obj, SimulationRun):
        return obj
    elif isinstance(obj, Result):
        # Adapt legacy bare Result values into the canonical wrapper.
        from battery_sim.core.solver import SolverConfig
        return SimulationRun(
            result=obj,
            metadata=SimulationMetadata.create(
                solver_config=SolverConfig(),  # Use defaults
                success=True,
                convergence_reason="Unknown (legacy Result)"
            ),
            errors=[],
            diagnostics=ConvergenceDiagnostics(),
        )
    else:
        raise TypeError(f"Expected Result or SimulationRun, got {type(obj)}")
