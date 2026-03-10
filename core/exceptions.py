"""Canonical exception hierarchy for validation and simulation setup."""

class SimulationError(Exception):
    """
    Base exception for all battery_sim errors.
    """
    pass

class ValidationError(SimulationError):
    """
    Base class for all validation-related errors.
    Raised when an object is internally inconsistent.
    """
    pass

class CellValidationError(ValidationError):
    """
    Raised when a Cell is invalid or inconsistent.
    """
    pass

class ProtocolValidationError(ValidationError):
    """
    Raised when a Protocol is invalid or inconsistent.
    """
    pass

class SolverValidationError(ValidationError):
    """
    Raised when SolverConfig parameters are invalid or incompatible.
    """
    pass

class EnvironmentValidationError(ValidationError):
    """
    Raised when Environment parameters are outside acceptable bounds.
    """
    pass

class SimulationValidationError(ValidationError):
    """
    Raised when a Simulation configuration is invalid.
    """
    pass

class BackendValidationError(ValidationError):
    """
    Raised when a backend cannot support a given simulation configuration.
    """
    pass