"""GUI form for Sample Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import ReportForm, IntSelector, BoolSelector, EnumSelector
from .params import SampleReportParams


class SampleReportForm(ReportForm):
    params_class = SampleReportParams
    max_samples = IntSelector(default=10, label="Max samples to show")
    include_table = BoolSelector(default=True, label="Include data table")
    chart_type = EnumSelector(values=["bar", "scatter"], label="Chart type", default="bar")
