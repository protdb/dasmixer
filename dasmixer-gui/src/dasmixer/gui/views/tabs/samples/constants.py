"""Constants for samples tab."""

# Default colors for groups and tools
# Colors are selected by index: (count % 10)
DEFAULT_COLORS = [
    "#0000FF",  # Blue
    "#FF0000",  # Red
    "#008000",  # Green
    "#FF00FF",  # Magenta
    "#00FFFF",  # Cyan
    "#FFD700",  # Gold
    "#FF8000",  # Orange
    "#8000FF",  # Purple
    "#FF0080",  # Pink
    "#00FF80"   # Spring Green
]


def get_default_color(index: int) -> str:
    """
    Get default color by index.
    
    Args:
        index: Index (typically count of existing items)
        
    Returns:
        Color hex string (with #)
    """
    return DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
