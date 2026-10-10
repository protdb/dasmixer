"""Marker base dataclass for report parameters (no-flet, core-side)."""
from dataclasses import dataclass


@dataclass
class ReportParams:
    """Marker base class for typed report parameter dataclasses.

    Subclasses must declare `name_template: str = "{date} {time}"` as one
    of their fields (see 0.7.4a1 report overhaul spec, section 4).
    """
