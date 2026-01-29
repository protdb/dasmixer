"""Input parsers package with automatic registration."""

from .registry import registry
from .base import BaseImporter

# Import base classes for external use
try:
    from .spectra.base import SpectralDataParser
except ImportError:
    SpectralDataParser = None

try:
    from .peptides.base import IdentificationParser
except ImportError:
    IdentificationParser = None


def register_parsers():
    """
    Register all available parsers.
    
    This function is called automatically on module import.
    Parsers that fail to import are silently skipped.
    
    Future plugin system will scan additional directories
    and call register() function from plugin modules.
    """
    # Spectra parsers
    try:
        from .spectra.mgf import MGFParser
        registry.add_spectra_parser("MGF", MGFParser)
    except ImportError as e:
        pass  # Parser not available or dependencies missing
    
    # Additional spectra parsers can be added here
    # try:
    #     from .spectra.mzml import MZMLParser
    #     registry.add_spectra_parser("MZML", MZMLParser)
    # except ImportError:
    #     pass
    
    # Identification parsers
    # try:
    #     from .peptides.powernovo2 import PowerNovo2Parser
    #     registry.add_identification_parser("PowerNovo2", PowerNovo2Parser)
    # except ImportError:
    #     pass
    
    # try:
    #     from .peptides.maxquant import MaxQuantParser
    #     registry.add_identification_parser("MaxQuant", MaxQuantParser)
    # except ImportError:
    #     pass


# Auto-register on import
register_parsers()

__all__ = [
    'registry',
    'BaseImporter',
    'SpectralDataParser',
    'IdentificationParser'
]
