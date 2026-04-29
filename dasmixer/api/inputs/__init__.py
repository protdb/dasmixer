"""Input parsers package with automatic registration."""

from .registry import registry
from .base import BaseImporter
from ...utils import logger

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
        logger.exception(e)
        pass  # Parser not available or dependencies missing
    try:
        from .spectra.plgs_mgf_with_leid import MGFParserPLGS
        registry.add_spectra_parser("MGF (PLGS Pseudo-DIA)", MGFParserPLGS)
    except ImportError as e:
        logger.exception(e)
        pass
    # Additional spectra parsers can be added here
    # try:
    #     from .spectra.mzml import MZMLParser
    #     registry.add_spectra_parser("MZML", MZMLParser)
    # except ImportError:
    #     pass
    
    # Identification parsers
    try:
        from .peptides.PowerNovo2 import PowerNovo2Importer
        registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
    except ImportError as e:
        logger.exception(e)
    pass
    
    try:
        from .peptides.MQ_Evidences import MaxQuantEvidenceParser
        registry.add_identification_parser("MaxQuant", MaxQuantEvidenceParser)
    except ImportError as e:
        logger.exception(e)
        pass

    try:
        from .peptides.PLGS import PLGSImporter
        registry.add_identification_parser("PLGS", PLGSImporter)
    except ImportError as e:
        logger.exception(e)
        pass


# Auto-register on import
register_parsers()

__all__ = [
    'registry',
    'BaseImporter',
    'SpectralDataParser',
    'IdentificationParser'
]
