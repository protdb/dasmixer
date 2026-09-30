"""GUI form for Tool Coverage Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import ReportForm
from .params import ToolCoverageReportParams


class ToolCoverageReportForm(ReportForm):
    params_class = ToolCoverageReportParams
    # No configurable fields — report uses all identified proteins automatically.
