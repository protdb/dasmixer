"""Parameters for Tool Coverage Report."""
from __future__ import annotations
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class ToolCoverageReportParams(ReportParams):
    """Tool Coverage Report has no user-configurable parameters.

    The report uses all identified proteins and project LFQ settings
    (enzyme, min/max length, missed cleavages) automatically.
    """
    name_template: str = field(default="{date} {time}")
