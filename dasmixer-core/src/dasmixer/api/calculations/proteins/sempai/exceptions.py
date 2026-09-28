"""
Custom exceptions for semPAI library.
"""


class SemPAIError(Exception):
    """Base exception class for semPAI library."""


class ValidationError(SemPAIError):
    """Raised when input validation fails."""


class CalibrationError(SemPAIError):
    """Raised when calibration process fails."""


class DataError(SemPAIError):
    """Raised when data retrieval or processing fails."""


class ModelError(SemPAIError):
    """Raised when machine learning model fails."""


class ParameterError(SemPAIError):
    """Raised when parameters are invalid or incompatible."""
