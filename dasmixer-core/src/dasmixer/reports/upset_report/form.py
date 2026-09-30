"""GUI form for UpSet Plot Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import ReportForm, MultiSubsetSelector, IntSelector
from .params import UpsetReportParams


class UpsetReportForm(ReportForm):
    params_class = UpsetReportParams
    subsets = MultiSubsetSelector(label="Comparison groups")
    min_proteins = IntSelector(default=1, label="Min proteins per intersection")
