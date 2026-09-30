"""GUI form for PCA ROC-AUC Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import (
    ReportForm, MultiSubsetSelector, EnumSelector, LFQSelector,
    BoolSelector, IntSelector,
)
from .params import PCAReportParams


class PCAReportForm(ReportForm):
    params_class = PCAReportParams
    subsets = MultiSubsetSelector(label="Comparison groups")
    group_by = EnumSelector(values=["Sample", "Protein"], label="Group by", default="Sample")
    lfq = LFQSelector(label="LFQ", default_method="emPAI", default_value_type="rel")
    show_labels = BoolSelector(default=True, label="Show point labels")
    top_n_proteins = IntSelector(default=100, label="Top N proteins (by variance)")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")
