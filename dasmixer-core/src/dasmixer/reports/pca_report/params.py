"""Parameters for PCA ROC-AUC Report."""
from __future__ import annotations

from dataclasses import dataclass, field

from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class PCAReportParams(ReportParams):
    subsets: list[str] = field(default_factory=list)
    group_by: str = "Sample"
    lfq: tuple[str, str] = ("emPAI", "rel_value")
    show_labels: bool = True
    top_n_proteins: int = 100
    include_outliers: bool = False
    name_template: str = field(default="{subset} {lfq} {date} {time}")
