# battery_sim/core/simulation_error.py
"""
SimulationError: Detect and categorize simulation failures.

**Purpose**: During simulation, various things can go wrong:
  - Voltage goes negative (unphysical)
  - Solver diverges (numerical instability)
  - Resistance becomes negative (model inconsistency)
  - Concentrations go out of bounds (chemistry violation)

SimulationError categorizes these systematically so we know what happened.

**Error Categories**:
  PHYSICAL_VIOLATION: Battery physics violated (e.g., V < 0)
  NUMERICAL_ISSUE: Numerical instability (NaN, Inf, divergence)
  CONVERGENCE_FAILURE: Solver failed to converge
  CONSTRAINT_VIOLATION: Protocol constraint violated
  MODEL_INCONSISTENCY: Internal model inconsistency detected
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorType(Enum):
    """Categorization of simulation errors."""
    
    # Physical constraint violations
    VOLTAGE_OUT_OF_BOUNDS = "voltage_out_of_bounds"
    """Voltage outside physical bounds (e.g., < 2.5V or > 4.2V for Li-ion)"""
    
    CONCENTRATION_OUT_OF_BOUNDS = "concentration_out_of_bounds"
    """Active material concentration outside [0, 1]"""
    
    TEMPERATURE_OUT_OF_BOUNDS = "temperature_out_of_bounds"
    """Temperature outside operating range"""
    
    RESISTANCE_NEGATIVE = "resistance_negative"
    """Internal resistance is negative (unphysical)"""
    
    # Numerical issues
    NAN_DETECTED = "nan_detected"
    """NaN (Not a Number) value in results"""
    
    INF_DETECTED = "inf_detected"
    """Inf (Infinity) value in results"""
    
    DIVERGENCE = "divergence"
    """Solution diverges (e.g., voltage growing unbounded)"""
    
    # Solver failures
    CONVERGENCE_FAILURE = "convergence_failure"
    """Solver failed to converge within tolerance"""
    
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    """Solver exceeded iteration limit"""
    
    SINGULAR_JACOBIAN = "singular_jacobian"
    """Jacobian matrix singular (solver cannot invert)"""
    
    # Constraint violations
    CURRENT_LIMIT_EXCEEDED = "current_limit_exceeded"
    """Current exceeds cell rating"""
    
    PROTOCOL_INFEASIBLE = "protocol_infeasible"
    """Protocol demands impossible operation (e.g., discharge empty battery)"""
    
    # Model issues
    INCOMPATIBLE_MODEL = "incompatible_model"
    """Selected model cannot handle specified parameters"""
    
    UNRECOGNIZED = "unrecognized"
    """Unknown error type (for future compatibility)"""


@dataclass(frozen=True)
class SimulationError:
    """
    Represents one error that occurred during simulation.
    
    **Fields**:
        error_type: Category of error (from ErrorType enum)
        severity: "critical" (stop simulation), "warning" (continue), "info" (log only)
        message: Human-readable error description
        location: Where did it happen? (e.g., "protocol step 3", "at 45 seconds")
        value: The problematic value (e.g., voltage = -0.5V)
        bounds: Safe bounds if applicable (e.g., "[2.5V, 4.2V]")
    
    **Example**:
        error = SimulationError(
            error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
            severity="critical",
            message="Voltage dropped below minimum safe voltage",
            location="at 120.5 seconds (discharge protocol step 2)",
            value=-0.15,
            bounds="[2.5V, 4.2V]"
        )
    """
    
    error_type: ErrorType
    """Category of error"""
    
    severity: str
    """Severity level: 'critical', 'warning', or 'info'"""
    
    message: str
    """Human-readable description of the error"""
    
    location: str = ""
    """Where the error occurred (e.g., step 3, time 120.5s)"""
    
    value: Optional[float] = None
    """The problematic value (if numeric)"""
    
    bounds: str = ""
    """Safe bounds description (if applicable)"""
    
    def is_critical(self) -> bool:
        """True if this error stopped the simulation."""
        return self.severity == "critical"
    
    def is_warning(self) -> bool:
        """True if this is a non-fatal warning."""
        return self.severity == "warning"
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            "error_type": self.error_type.value,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "value": self.value,
            "bounds": self.bounds,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SimulationError":
        """Deserialize from dictionary."""
        data_copy = data.copy()
        data_copy["error_type"] = ErrorType(data_copy["error_type"])
        return cls(**data_copy)
    
    def summary(self) -> str:
        """
        Human-readable single-line summary.
        
        Example:
            "CRITICAL: Voltage dropped below minimum (value=-0.15V, bounds=[2.5V, 4.2V], at 120.5s)"
        """
        severity_str = self.severity.upper()
        msg = f"{severity_str}: {self.message}"
        
        if self.value is not None and self.bounds:
            msg += f" (value={self.value}, bounds={self.bounds})"
        elif self.value is not None:
            msg += f" (value={self.value})"
        
        if self.location:
            msg += f" @ {self.location}"
        
        return msg


class ErrorDetector:
    """
    Utility class to detect and categorize simulation errors.
    
    **Purpose**: Check results for physical/numerical violations.
    
    **Usage**:
        errors = ErrorDetector.detect_all(result, cell, model)
        for error in errors:
            print(error.summary())
    """
    
    @staticmethod
    def detect_voltage_violations(
        result,
        min_voltage_v: float = 2.5,
        max_voltage_v: float = 4.2,
        numerical_tolerance_v: float = 1e-5,
    ) -> list[SimulationError]:
        """
        Detect voltage out-of-bounds violations.
        
        **Parameters**:
            result: Result object with Signal.VOLTAGE data
            min_voltage_v: Minimum safe voltage
            max_voltage_v: Maximum safe voltage
        
        **Returns**:
            List of SimulationError objects (empty if no violations)
        """
        errors = []
        
        from battery_sim.types.signal import Signal
        
        if Signal.VOLTAGE not in result._data:
            return errors
        
        voltage_data = result._data[Signal.VOLTAGE]
        voltage_values = voltage_data.values
        time_values = voltage_data.time_s
        
        low_indices = [
            index
            for index, value in enumerate(voltage_values)
            if value < min_voltage_v - numerical_tolerance_v
        ]
        high_indices = [
            index
            for index, value in enumerate(voltage_values)
            if value > max_voltage_v + numerical_tolerance_v
        ]

        if low_indices:
            first_index = low_indices[0]
            errors.append(SimulationError(
                error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
                severity="critical",
                message=f"Voltage below minimum safe voltage ({len(low_indices)} samples)",
                location=f"first at {time_values[first_index]:.1f} seconds (index {first_index})",
                value=min(voltage_values[index] for index in low_indices),
                bounds=f"[{min_voltage_v}V, {max_voltage_v}V]"
            ))

        if high_indices:
            first_index = high_indices[0]
            errors.append(SimulationError(
                error_type=ErrorType.VOLTAGE_OUT_OF_BOUNDS,
                severity="critical",
                message=f"Voltage above maximum safe voltage ({len(high_indices)} samples)",
                location=f"first at {time_values[first_index]:.1f} seconds (index {first_index})",
                value=max(voltage_values[index] for index in high_indices),
                bounds=f"[{min_voltage_v}V, {max_voltage_v}V]"
            ))
        
        return errors
    
    @staticmethod
    def detect_numerical_issues(result) -> list[SimulationError]:
        """
        Detect NaN, Inf, and other numerical problems.
        
        **Returns**:
            List of SimulationError objects for any numerical issues
        """
        import numpy as np
        from battery_sim.types.signal import Signal
        
        errors = []
        
        # Check each signal for NaN/Inf
        for signal, timeseries in result._data.items():
            values = np.array(timeseries.values)
            
            nan_indices = np.where(np.isnan(values))[0]
            inf_indices = np.where(np.isinf(values))[0]
            
            if len(nan_indices) > 0:
                idx = int(nan_indices[0])
                errors.append(SimulationError(
                    error_type=ErrorType.NAN_DETECTED,
                    severity="critical",
                    message=f"NaN detected in {signal.value} ({len(nan_indices)} samples)",
                    location=f"first at sample {idx} (time {timeseries.time_s[idx]:.1f}s)",
                    value=None,
                ))
            
            if len(inf_indices) > 0:
                idx = int(inf_indices[0])
                errors.append(SimulationError(
                    error_type=ErrorType.INF_DETECTED,
                    severity="critical",
                    message=f"Infinity detected in {signal.value} ({len(inf_indices)} samples)",
                    location=f"first at sample {idx} (time {timeseries.time_s[idx]:.1f}s)",
                    value=None,
                ))
        
        return errors
    
    @staticmethod
    def detect_divergence(result, growth_threshold: float = 2.0) -> list[SimulationError]:
        """
        Detect if simulation is diverging (values growing unbounded).
        
        **Parameters**:
            result: Result object
            growth_threshold: If end value > start value * threshold, call it divergence
        
        **Returns**:
            List of SimulationError objects
        """
        import numpy as np
        from battery_sim.types.signal import Signal
        
        errors = []
        
        if Signal.VOLTAGE not in result._data:
            return errors
        
        voltage_values = np.array(result._data[Signal.VOLTAGE].values)
        
        # Check for unbounded growth
        if len(voltage_values) > 1:
            start_val = abs(voltage_values[0])
            end_val = abs(voltage_values[-1])
            
            if start_val > 0.1 and (end_val / start_val) > growth_threshold:
                errors.append(SimulationError(
                    error_type=ErrorType.DIVERGENCE,
                    severity="warning",
                    message="Solution appears to be diverging",
                    location="over entire simulation",
                    value=end_val,
                    bounds=f"[0, {start_val * growth_threshold:.2f}]"
                ))
        
        return errors
    
    @staticmethod
    def detect_all(result, cell=None, model=None) -> list[SimulationError]:
        """
        Run all error detection checks.
        
        **Returns**:
            Combined list of all detected errors
        """
        errors = []
        
        # Use the selected cell's declared operating window when available.
        min_voltage_v = 2.5
        max_voltage_v = 4.2
        if cell is not None:
            min_voltage_v = float(cell.metadata.get("min_voltage_v", min_voltage_v))
            max_voltage_v = float(cell.metadata.get("max_voltage_v", max_voltage_v))
        errors.extend(
            ErrorDetector.detect_voltage_violations(
                result,
                min_voltage_v=min_voltage_v,
                max_voltage_v=max_voltage_v,
            )
        )
        
        # Check for numerical issues
        errors.extend(ErrorDetector.detect_numerical_issues(result))
        
        # Check for divergence
        errors.extend(ErrorDetector.detect_divergence(result))
        
        return errors
