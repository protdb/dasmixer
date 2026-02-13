"""Shared state for samples tab sections."""

from dataclasses import dataclass, field


@dataclass
class SamplesTabState:
    """
    Shared state between samples tab sections.
    
    Holds counts and flags that multiple sections need to access.
    """
    
    # Counts
    groups_count: int = 0
    tools_count: int = 0
    samples_count: int = 0
    spectra_files_count: int = 0
    identification_files_count: int = 0
    
    # Flags for refresh coordination
    needs_refresh_groups: bool = False
    needs_refresh_tools: bool = False
    needs_refresh_samples: bool = False
    
    def reset_refresh_flags(self):
        """Reset all refresh flags."""
        self.needs_refresh_groups = False
        self.needs_refresh_tools = False
        self.needs_refresh_samples = False
