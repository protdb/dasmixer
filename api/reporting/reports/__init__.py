"""Import all report implementations to trigger registration."""

from .sample_report import SampleReport
from .toolmatch_report import ToolMatchReport
from .volcano_report import VolcanoReport

__all__ = ['SampleReport', 'ToolMatchReport', 'VolcanoReport']
