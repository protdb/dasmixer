"""GUI form for Tool Match Report. Imported only when dasmixer-gui is installed."""
from dasmixer.gui.components.report_form import ReportForm, ToolSelector

from .params import ToolMatchReportParams


class ToolMatchReportForm(ReportForm):
    params_class = ToolMatchReportParams
    tool1 = ToolSelector(label="Tool 1")
    tool2 = ToolSelector(label="Tool 2")
