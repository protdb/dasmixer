"""Parameters for Median Report."""
from __future__ import annotations
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class MedianReportParams(ReportParams):
    subsets: list[str] = field(default_factory=list)
    lfq: tuple[str, str] = ("emPAI", "rel_value")
    include_outliers: bool = False
    name_template: str = field(default="{subsets} {lfq} {date} {time}")
