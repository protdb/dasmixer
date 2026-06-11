"""Mock for flet.Icons when flet is not installed.

Reports use Icons.* constants for their icon attribute.
When flet is not available (e.g. dasmixer-core without dasmixer-gui),
this module provides a mock that returns the attribute name as a lowercase string.
"""

try:
    from flet import Icons
except ImportError:
    class _IconsMock:
        """Returns attribute name as lowercase string for any Icons.CONSTANT."""

        def __getattr__(self, name: str) -> str:
            return name.lower()

    Icons = _IconsMock()