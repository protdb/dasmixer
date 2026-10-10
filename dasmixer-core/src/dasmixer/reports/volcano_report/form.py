"""GUI form for Volcano Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import (
    BoolSelector,
    EnumSelector,
    FloatSelector,
    IntSelector,
    LFQSelector,
    MultiSubsetSelector,
    ReportForm,
    SubsetSelector,
)

from .params import VolcanoReportParams


class VolcanoReportForm(ReportForm):
    params_class = VolcanoReportParams

    control_subset = SubsetSelector(label="Control subset")
    exptl_subsets = MultiSubsetSelector(label="Experimental subsets")
    lfq = LFQSelector(label="LFQ", default_method="emPAI", default_value_type="rel")
    stats_method = EnumSelector(values=["Mann-Whitney", "T-test"], label="Statistical method", default="Mann-Whitney")
    fdc = EnumSelector(values=["BH", "BY", "Bonferroni"], label="FDR correction", default="BH")
    percent_to_calculate = IntSelector(default=20, label="Min % samples with value")
    fc_threshold = FloatSelector(default=1.5, label="FC threshold")
    p_threshold = FloatSelector(default=0.05, label="p-value threshold")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")
