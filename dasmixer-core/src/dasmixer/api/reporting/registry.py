"""Registry for report modules."""

from typing import Type
from .base import BaseReport


class ReportRegistry:
    """
    Registry for available reports.
    
    Similar to InputTypesRegistry, allows registering
    and retrieving report classes.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._reports: dict[str, Type[BaseReport]] = {}
    
    def register(self, report_class: Type[BaseReport]) -> None:
        """
        Register a report.
        
        Args:
            report_class: Report class (not instance)
            
        Raises:
            KeyError: If report with this name already registered
        """
        name = report_class.name
        if name in self._reports:
            raise KeyError(f'Report "{name}" already registered')
        self._reports[name] = report_class
    
    def get_all(self) -> dict[str, Type[BaseReport]]:
        """
        Get all registered reports.
        
        Returns:
            dict: {report_name: report_class}
        """
        return self._reports.copy()
    
    def get(self, name: str) -> Type[BaseReport]:
        """
        Get report class by name.
        
        Args:
            name: Report name
            
        Returns:
            Report class
            
        Raises:
            KeyError: If report not found
        """
        if name not in self._reports:
            available = list(self._reports.keys())
            raise KeyError(
                f'Report "{name}" not found. Available: {available}'
            )
        return self._reports[name]


# Global registry instance
# Reports register themselves when their modules are imported
registry = ReportRegistry()
