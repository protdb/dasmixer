"""Spectral data parsers."""

from .base import SpectralDataParser
from .mgf import MGFParser

# Note: Parser registration is now handled in api/inputs/__init__.py
# to avoid circular imports

__all__ = ['SpectralDataParser', 'MGFParser']
