"""Base classes for data importers."""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseImporter(ABC):
    """
    Base class for all data importers.
    
    Provides common functionality for file validation and metadata extraction.
    """

    file_path: Path

    def __init__(self, file_path: Path | str):
        """
        Initialize importer.
        
        Args:
            file_path: Path to file to import
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file
        """
        self.file_path = Path(file_path)
        self._validate_file()
    
    def _validate_file(self) -> None:
        """
        Validate that file exists and is readable.
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        if not self.file_path.is_file():
            raise ValueError(f"Not a file: {self.file_path}")
    
    @abstractmethod
    async def validate(self) -> bool:
        """
        Validate file format.
        
        Checks if the file can be parsed by this importer.
        Should perform quick validation (e.g., magic numbers, header check)
        without parsing the entire file.
        
        Returns:
            True if file is valid for this importer, False otherwise
        """
        pass
    
    async def get_metadata(self) -> dict:
        """
        Get file metadata.
        
        Base implementation returns empty dict.
        Override in subclasses if metadata extraction is needed.
        
        Returns:
            dict with metadata (empty by default)
        """
        return {}
