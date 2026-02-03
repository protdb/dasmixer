"""Shared state for Samples tab components."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SamplesTabState:
    """
    Shared state container for Samples tab.
    
    Managed by SamplesTab and accessible by all sections.
    """
    
    # Groups data
    groups_list: list = field(default_factory=list)
    
    # Tools data
    tools_list: list = field(default_factory=list)
    
    # Samples data
    samples_list: list = field(default_factory=list)
    
    # UI update flags
    needs_groups_refresh: bool = False
    needs_tools_refresh: bool = False
    needs_samples_refresh: bool = False
    updating: bool = False  # Prevent refresh loops
    
    def mark_groups_dirty(self):
        """Mark groups as needing refresh."""
        self.needs_groups_refresh = True
    
    def mark_tools_dirty(self):
        """Mark tools as needing refresh."""
        self.needs_tools_refresh = True
    
    def mark_samples_dirty(self):
        """Mark samples as needing refresh."""
        self.needs_samples_refresh = True
    
    def mark_all_dirty(self):
        """Mark all as needing refresh."""
        self.needs_groups_refresh = True
        self.needs_tools_refresh = True
        self.needs_samples_refresh = True
