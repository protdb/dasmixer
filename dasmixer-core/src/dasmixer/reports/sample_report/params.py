"""Parameters for Sample Report."""
from __future__ import annotations
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class SampleReportParams(ReportParams):
    max_samples: int = 10
    include_table: bool = True
    chart_type: str = "bar"
    name_template: str = field(default="{date} {time}")
