"""Shared state for Peptides tab components."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PeptidesTabState:
    """
    Shared state container for Peptides tab.
    
    Managed by PeptidesTab and accessible by all sections.
    """
    
    # Tools data
    tools_list: list = field(default_factory=list)
    tool_settings_controls: dict = field(default_factory=dict)
    
    # Ion settings (loaded from project)
    ion_types: list[str] = field(default_factory=lambda: ['b', 'y'])
    water_loss: bool = False
    nh3_loss: bool = False
    ion_ppm_threshold: float = 20.0
    fragment_charges: list[int] = field(default_factory=lambda: [1, 2])
    
    # FASTA/Protein data
    protein_count: int = 0
    fasta_file_path: str | None = None
    
    # Search filters
    samples_list: list = field(default_factory=list)
    
    # Current search results
    search_results: Any = None
    selected_spectrum_id: int | None = None
    
    # UI update flags
    needs_tool_refresh: bool = False
    needs_filter_refresh: bool = False
    
    def mark_tools_dirty(self):
        """Mark tools as needing refresh."""
        self.needs_tool_refresh = True
    
    def mark_filters_dirty(self):
        """Mark search filters as needing refresh."""
        self.needs_filter_refresh = True
    
    def clear_search(self):
        """Clear search results."""
        self.search_results = None
        self.selected_spectrum_id = None
