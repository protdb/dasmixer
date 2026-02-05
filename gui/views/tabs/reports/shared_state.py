"""Shared state for Reports tab."""

from dataclasses import dataclass, field


@dataclass
class ReportsTabState:
    """
    Shared state for Reports tab.
    
    Attributes:
        plot_font_size: Font size for plots
        plot_width: Plot width in pixels
        plot_height: Plot height in pixels
        selected_reports: Reports selected for batch generation
    """
    plot_font_size: int = 12
    plot_width: int = 1200
    plot_height: int = 800
    selected_reports: set[str] = field(default_factory=set)
