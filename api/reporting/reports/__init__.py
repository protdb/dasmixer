"""Import all report implementations to trigger registration."""

from .sample_report import SampleReport
from .toolmatch_report import ToolMatchReport

__all__ = ['SampleReport', 'ToolMatchReport']
