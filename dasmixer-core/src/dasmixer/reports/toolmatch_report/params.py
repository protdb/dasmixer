"""Parameters for Tool Match Report."""
from __future__ import annotations
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class ToolMatchReportParams(ReportParams):
    tool1: str = ""
    tool2: str = ""
    name_template: str = field(default='{tool1}vs{tool2} {date} {time}')
