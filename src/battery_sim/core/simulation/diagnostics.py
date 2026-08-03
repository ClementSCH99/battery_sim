# battery_sim/core/convergence_diagnostics.py
"""
ConvergenceDiagnostics: Extract and analyze solver statistics.

**Purpose**: During solver execution, PyBaMM's Newton solver runs iterations.
This class extracts statistics about:
  - How many Newton iterations per time step?
  - How fast did residuals decline?
  - Did the time step adapt (for stiff ODEs)?
  - What were the final tolerances achieved?

**Key Metrics**:
  - convergence_rate: Linear (slow) vs quadratic (Newton is working)
  - avg_newton_iterations: How stiff is the problem?
  - max_newton_iterations: Worst-case difficulty
  - total_time_steps: How fine was the time discretization?

**Example Use**:
    If avg_newton_iterations > 50, the model is VERY stiff.
    If max_newton_iterations > 200, something is numerically difficult.
    
    These hint at which parameters cause solver challenges.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class ConvergenceRate(Enum):
    """Classification of solver convergence behavior."""
    
    LINEAR = "linear"
    """Residual decreases ~constant factor each iteration (slower, R^n behavior)"""
    
    SUPERLINEAR = "superlinear"
    """Faster than linear but not quadratic"""
    
    QUADRATIC = "quadratic"
    """Newton method working well, residual ~ R^(2^n) (ideal)"""
    
    UNKNOWN = "unknown"
    """Cannot determine from available data"""


@dataclass(frozen=True)
class ConvergenceDiagnostics:
    """
    Solver convergence statistics extracted from simulation.
    
    **Fields**:
        total_time_steps: How many time steps in the solution?
        avg_newton_iterations: Average Newton iterations per step
        max_newton_iterations: Peak iterations (identification of stiff regions)
        min_newton_iterations: Minimum iterations (easy regions)
        convergence_rate: Linear vs quadratic convergence
        
        final_tolerance_achieved_time: Did we meet time tolerance?
        final_tolerance_achieved_space: Did we meet spatial tolerance?
        
        time_step_rejections: How many time steps had to be redone?
        jacobian_updates: How often was Jacobian recomputed?
        
        problem_description: Text classification (stiff, well-conditioned, etc.)
    
    **Interpretation**:
        avg_newton_iterations < 10: Well-behaved, fast problem
        avg_newton_iterations 10-30: Moderately stiff
        avg_newton_iterations > 50: Very stiff (convergence challenges)
    """
    
    total_time_steps: int = 0
    """Total number of time steps computed"""
    
    avg_newton_iterations: Optional[float] = None
    """Average Newton iterations per step when available from solver telemetry"""
    
    max_newton_iterations: Optional[int] = None
    """Maximum Newton iterations for any single step when available"""
    
    min_newton_iterations: Optional[int] = None
    """Minimum Newton iterations for any single step when available"""
    
    convergence_rate: ConvergenceRate = ConvergenceRate.UNKNOWN
    """Is convergence linear, superlinear, or quadratic?"""
    
    final_tolerance_achieved_time: Optional[bool] = None
    """Did solver meet time-stepping tolerance when this telemetry is available?"""
    
    final_tolerance_achieved_space: Optional[bool] = None
    """Did solver meet spatial discretization tolerance when available?"""
    
    time_step_rejections: Optional[int] = None
    """Number of rejected time steps when exposed by the backend"""
    
    jacobian_updates: Optional[int] = None
    """How many times the Jacobian was recomputed when exposed by the backend"""
    
    problem_description: str = ""
    """Human-readable classification: 'well-conditioned', 'moderately stiff', 'very stiff', etc."""

    telemetry_status: str = "unavailable"
    """Whether solver diagnostics are measured, estimated, or unavailable."""
    
    # Advanced diagnostics (optional)
    residual_history: List[float] = field(default_factory=list)
    """Optional: residuals from each Newton iteration (for plotting)"""
    
    time_per_step_ms: List[float] = field(default_factory=list)
    """Optional: wall-clock ms per time step (for timing analysis)"""
    
    @classmethod
    def create(
        cls,
        total_time_steps: int,
        avg_newton_iterations: Optional[float] = None,
        max_newton_iterations: Optional[int] = None,
        min_newton_iterations: Optional[int] = None,
        problem_description: Optional[str] = None,
        telemetry_status: str = "measured",
    ) -> "ConvergenceDiagnostics":
        """
        Factory method to create diagnostics with automatic classification.
        
        **Usage**:
            diagnostics = ConvergenceDiagnostics.create(
                total_time_steps=n_steps,
                avg_newton_iterations=average_iterations,
                max_newton_iterations=peak_iterations,
            )
        """
        if problem_description is not None:
            problem_desc = problem_description
        elif avg_newton_iterations is None:
            problem_desc = "solver telemetry unavailable in current backend"
        elif avg_newton_iterations < 10:
            problem_desc = "well-conditioned (fast solve)"
        elif avg_newton_iterations < 30:
            problem_desc = "moderately stiff"
        else:
            problem_desc = "very stiff (convergence challenges)"
        
        # Classify convergence rate (requires detailed residual data, default to UNKNOWN)
        convergence = ConvergenceRate.UNKNOWN
        
        return cls(
            total_time_steps=total_time_steps,
            avg_newton_iterations=avg_newton_iterations,
            max_newton_iterations=max_newton_iterations,
            min_newton_iterations=min_newton_iterations,
            convergence_rate=convergence,
            problem_description=problem_desc,
            telemetry_status=telemetry_status,
        )
    
    def is_well_behaved(self) -> bool:
        """
        True if solver had no trouble.
        
        Well-behaved = avg iterations < 20, no rejections.
        """
        if self.avg_newton_iterations is None or self.time_step_rejections is None:
            return False
        return self.avg_newton_iterations < 20 and self.time_step_rejections == 0
    
    def is_stiff(self) -> bool:
        """
        True if solver found the problem numerically stiff.
        
        Stiff = avg iterations > 30 OR max iterations > 100.
        """
        if self.avg_newton_iterations is None and self.max_newton_iterations is None:
            return False
        return (
            (self.avg_newton_iterations is not None and self.avg_newton_iterations > 30)
            or (self.max_newton_iterations is not None and self.max_newton_iterations > 100)
        )
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            "total_time_steps": self.total_time_steps,
            "avg_newton_iterations": self.avg_newton_iterations,
            "max_newton_iterations": self.max_newton_iterations,
            "min_newton_iterations": self.min_newton_iterations,
            "convergence_rate": self.convergence_rate.value,
            "final_tolerance_achieved_time": self.final_tolerance_achieved_time,
            "final_tolerance_achieved_space": self.final_tolerance_achieved_space,
            "time_step_rejections": self.time_step_rejections,
            "jacobian_updates": self.jacobian_updates,
            "problem_description": self.problem_description,
            "telemetry_status": self.telemetry_status,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConvergenceDiagnostics":
        """Deserialize from dictionary."""
        data_copy = data.copy()
        if "convergence_rate" in data_copy:
            data_copy["convergence_rate"] = ConvergenceRate(data_copy["convergence_rate"])
        return cls(**data_copy)
    
    def summary(self) -> str:
        """
        Human-readable summary for logging.
        
        Example Output:
            Convergence Diagnostics:
              Time Steps: 500
              Newton Iterations: avg=12 (range: 8-25)
              Problem: well-conditioned (fast solve)
              Convergence: QUADRATIC
              Status: No issues
        """
        if self.telemetry_status != "measured":
            status_msg = f"Telemetry {self.telemetry_status}"
            avg_iterations = "unavailable"
            iters_range = "unavailable"
        else:
            status_msg = "No issues" if self.is_well_behaved() else "Convergence challenges detected"
            avg_iterations = f"{self.avg_newton_iterations:.1f}"
            iters_range = f"{self.min_newton_iterations}-{self.max_newton_iterations}"
        
        return f"""Convergence Diagnostics:
  Time Steps: {self.total_time_steps}
  Newton Iterations: avg={avg_iterations} (range: {iters_range})
  Problem: {self.problem_description}
  Convergence: {self.convergence_rate.value.upper()}
  Status: {status_msg}"""


class DiagnosticsAnalyzer:
    """
    Utility to analyze convergence diagnostics.
    
    **Usage**:
        diagnostics = get_diagnostics_from_result(result)
        insights = DiagnosticsAnalyzer.analyze(diagnostics)
        for issue in insights:
            print(issue)
    """
    
    @staticmethod
    def analyze(diag: ConvergenceDiagnostics) -> List[str]:
        """
        Generate insights from diagnostics.
        
        Returns:
            List of actionable messages for users
        """
        insights = []

        if diag.telemetry_status != "measured":
            insights.append(
                "Detailed Newton iteration telemetry is unavailable in the current PyBaMM integration."
            )
            return insights
        
        # Check for stiffness
        if diag.is_stiff():
            insights.append(
                f"Problem is numerically stiff: avg {diag.avg_newton_iterations:.1f} "
                f"Newton iterations per step (normal: < 20)"
            )
            insights.append(
                "Recommendation: Consider tighter tolerances (rtol=1e-8, atol=1e-11) "
                "or implicit time stepping"
            )
        
        # Check for rejections
        if diag.time_step_rejections > 0:
            insights.append(
                f"Time stepping had {diag.time_step_rejections} rejections "
                f"(expensive re-solves)"
            )
            insights.append(
                "Recommendation: Your protocol or model parameters may be causing stiffness. "
                "Check temperature, current profiles."
            )
        
        # Check for divergence
        if diag.max_newton_iterations is not None and diag.max_newton_iterations > 200:
            insights.append(
                f"Severe convergence issue: {diag.max_newton_iterations} iterations "
                f"in worst case step"
            )
            insights.append(
                "Recommendation: Simulation may be near failure. Check protocol feasibility."
            )
        
        # Positive messages
        if diag.is_well_behaved():
            insights.append(
                f"Excellent convergence performance: "
                f"avg {diag.avg_newton_iterations:.1f} iterations/step"
            )
        
        return insights
