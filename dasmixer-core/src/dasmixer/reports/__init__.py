"""Import all built-in report implementations to trigger auto-registration.

This module is imported by dasmixer.gui.main (GUI) and dasmixer.cli.main (CLI)
to ensure that all report implementations are registered in the registry before
the Reports tab or CLI commands need them.
"""

from .coverage_report import ToolCoverageReport
from .median_report import MedianReport
from .pca_report import PCAReport
from .sample_report import SampleReport
from .toolmatch_report import ToolMatchReport
from .upset_report import UpsetReport
from .volcano_report import VolcanoReport

__all__ = [
    'MedianReport', 'PCAReport', 'SampleReport', 'ToolCoverageReport',
    'ToolMatchReport', 'UpsetReport', 'VolcanoReport',
]
