"""
Custom exceptions for semPAI library.
"""


class SemPAIError(Exception):
    """Base exception class for semPAI library."""
    pass


class ValidationError(SemPAIError):
    """Raised when input validation fails."""
    pass


class CalibrationError(SemPAIError):
    """Raised when calibration process fails."""
    pass


class DataError(SemPAIError):
    """Raised when data retrieval or processing fails."""
    pass


class ModelError(SemPAIError):
    """Raised when machine learning model fails."""
    pass


class ParameterError(SemPAIError):
    """Raised when parameters are invalid or incompatible."""
    pass