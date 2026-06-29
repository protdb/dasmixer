"""Registry for data parsers."""

from typing import Type
from .peptides import IdentificationParser
from .spectra import SpectralDataParser


class InputTypesRegistry:
    """
    Registry for data parsers available in the application.
    
    Parsers are registered at module import time to make them available
    in UI and CLI. This approach will facilitate future plugin system
    development.
    
    Usage:
        from api.inputs.registry import registry
        
        # Get all available parsers
        spectra_parsers = registry.get_spectra_parsers()
        ident_parsers = registry.get_identification_parsers()
        
        # Get specific parser class
        MGFParser = registry.get_parser("MGF", "spectra")
        parser = MGFParser("data.mgf")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._spectra_parsers: dict[str, Type[SpectralDataParser]] = {}
        self._identification_parsers: dict[str, Type[IdentificationParser]] = {}
    
    def add_spectra_parser(
        self,
        name: str,
        parser_class: Type[SpectralDataParser]
    ) -> None:
        """
        Register a spectral data parser.
        
        Args:
            name: Unique parser name (e.g., "MGF", "MZML")
            parser_class: Parser class (not instance)
            
        Raises:
            KeyError: If parser with this name already exists
            
        Example:
            >>> from api.inputs.spectra.mgf import MGFParser
            >>> registry.add_spectra_parser("MGF", MGFParser)
        """
        if name in self._spectra_parsers:
            raise KeyError(f'Spectral parser "{name}" already registered')
        self._spectra_parsers[name] = parser_class
    
    def add_identification_parser(
        self,
        name: str,
        parser_class: Type[IdentificationParser]
    ) -> None:
        """
        Register an identification parser.
        
        Args:
            name: Unique parser name (e.g., "PowerNovo2", "MaxQuant")
            parser_class: Parser class (not instance)
            
        Raises:
            KeyError: If parser with this name already exists
            
        Example:
            >>> from api.inputs.peptides.PowerNovo2 import PowerNovo2Importer
            >>> registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
        """
        if name in self._identification_parsers:
            raise KeyError(f'Identification parser "{name}" already registered')
        self._identification_parsers[name] = parser_class
    
    def get_spectra_parsers(self) -> dict[str, Type[SpectralDataParser]]:
        """
        Get all registered spectral parsers.
        
        Returns:
            Dict mapping parser names to parser classes
            
        Example:
            >>> parsers = registry.get_spectra_parsers()
            >>> print(list(parsers.keys()))
            ['MGF', 'MZML']
        """
        return self._spectra_parsers.copy()
    
    def get_identification_parsers(self) -> dict[str, Type[IdentificationParser]]:
        """
        Get all registered identification parsers.
        
        Returns:
            Dict mapping parser names to parser classes
            
        Example:
            >>> parsers = registry.get_identification_parsers()
            >>> print(list(parsers.keys()))
            ['PowerNovo2', 'MaxQuant', 'PLGS']
        """
        return self._identification_parsers.copy()
    
    def get_parser(
        self,
        name: str,
        parser_type: str
    ) -> Type[SpectralDataParser] | Type[IdentificationParser]:
        """
        Get parser class by name and type.
        
        Args:
            name: Parser name
            parser_type: "spectra" or "identification"
            
        Returns:
            Parser class
            
        Raises:
            ValueError: If parser type is invalid
            KeyError: If parser not found
            
        Example:
            >>> MGFParser = registry.get_parser("MGF", "spectra")
            >>> parser = MGFParser("/path/to/file.mgf")
        """
        if parser_type == "spectra":
            if name not in self._spectra_parsers:
                available = list(self._spectra_parsers.keys())
                raise KeyError(
                    f'Spectral parser "{name}" not found. '
                    f'Available: {available}'
                )
            return self._spectra_parsers[name]
        elif parser_type == "identification":
            if name not in self._identification_parsers:
                available = list(self._identification_parsers.keys())
                raise KeyError(
                    f'Identification parser "{name}" not found. '
                    f'Available: {available}'
                )
            return self._identification_parsers[name]
        else:
            raise ValueError(
                f'Invalid parser_type: "{parser_type}". '
                'Must be "spectra" or "identification"'
            )


# Global registry instance
# Parsers register themselves when their modules are imported
registry = InputTypesRegistry()
