"""Import all report implementations to trigger auto-registration."""

from .sample_report import SampleReport
from .toolmatch_report import ToolMatchReport
from .volcano_report import VolcanoReport
from .upset import UpsetReport
from .pca_report import PCAReport
from .coverage_report import ToolCoverageReport, ToolCoverageReportForm

__all__ = [
    'SampleReport',
    'ToolMatchReport',
    'VolcanoReport',
    'UpsetReport',
    'PCAReport',
    'ToolCoverageReport',
    'ToolCoverageReportForm',
]
