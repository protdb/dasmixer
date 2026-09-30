"""GUI form for Median Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import (
    ReportForm, MultiSubsetSelector, LFQSelector, BoolSelector,
)
from .params import MedianReportParams


class MedianReportForm(ReportForm):
    params_class = MedianReportParams
    subsets = MultiSubsetSelector(label="Comparison groups")
    lfq = LFQSelector(label="LFQ", default_method="emPAI", default_value_type="rel")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")
