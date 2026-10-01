"""Parameters for Volcano Report."""
from __future__ import annotations
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class VolcanoReportParams(ReportParams):
    control_subset: str = ""
    exptl_subsets: list[str] = field(default_factory=list)
    lfq: tuple[str, str] = ("emPAI", "rel_value")
    stats_method: str = "Mann-Whitney"
    fdc: str = "BH"
    percent_to_calculate: int = 20
    fc_threshold: float = 1.5
    p_threshold: float = 0.05
    include_outliers: bool = False
    name_template: str = field(default='{exptl_subsets} {lfq} {stats_method} {date} {time}')
