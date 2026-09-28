"""Import all report implementations to trigger auto-registration."""

from .coverage_report import ToolCoverageReport
from .median_report import MedianReport
from .pca_report import PCAReport
from .sample_report import SampleReport
from .toolmatch_report import ToolMatchReport
from .upset import UpsetReport
from .volcano_report import VolcanoReport

__all__ = [
    'MedianReport',
    'PCAReport',
    'SampleReport',
    'ToolCoverageReport',
    'ToolMatchReport',
    'UpsetReport',
    'VolcanoReport'
]
