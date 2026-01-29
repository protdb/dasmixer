"""Spectral data parsers."""

from .base import SpectralDataParser
from .mgf import MGFParser
from ..registry import registry

# Register parsers
registry.add_spectra_parser("MGF", MGFParser)

__all__ = ['SpectralDataParser', 'MGFParser']
