"""Parameters for UpSet Plot Report."""
from __future__ import annotations

from dataclasses import dataclass, field

from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class UpsetReportParams(ReportParams):
    subsets: list[str] = field(default_factory=list)
    min_proteins: int = 1
    name_template: str = field(default="{date} {time}")
