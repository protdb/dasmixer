"""
GUI-side form declarations for built-in reports.

Imported early during GUI startup to patch report classes
with their flet-based parameter forms.
"""

from dasmixer.api.reporting.reports.pca_report import PCAReport
from dasmixer.api.reporting.reports.volcano_report import VolcanoReport
from dasmixer.api.reporting.reports.median_report import MedianReport
from dasmixer.api.reporting.reports.toolmatch_report import ToolMatchReport
from dasmixer.api.reporting.reports.coverage_report import ToolCoverageReport
from dasmixer.api.reporting.reports.upset import UpsetReport
from dasmixer.api.reporting.reports.sample_report import SampleReport

from dasmixer.gui.components.report_form import (
    ReportForm,
    ToolSelector,
    BoolSelector,
    IntSelector,
    FloatSelector,
    SubsetSelector,
    MultiSubsetSelector,
    LFQSelector,
    EnumSelector,
)


# ---------------------------------------------------------------------------
# PCA Report Form
# ---------------------------------------------------------------------------

class PCAReportForm(ReportForm):
    subsets = MultiSubsetSelector(label="Subsets to include")
    lfq = LFQSelector(label="LFQ", default_method="emPAI", default_value_type="rel")
    show_labels = BoolSelector(default=True, label="Show sample labels")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")


# ---------------------------------------------------------------------------
# Volcano Report Form
# ---------------------------------------------------------------------------

class VolcanoReportForm(ReportForm):
    control_subset = SubsetSelector(label="Control subset")
    exptl_subsets = MultiSubsetSelector(label="Experimental subsets")
    lfq = LFQSelector(label="LFQ", default_method="emPAI", default_value_type="rel")
    stats_method = EnumSelector(values=["Mann-Whitney", "T-test"], label="Statistical method")
    fdc = EnumSelector(values=["BH", "BY", "Bonferroni"], label="FDR correction")
    percent_to_calculate = IntSelector(default=20, label="Min % samples with value")
    fc_threshold = FloatSelector(default=1.5, label="FC threshold")
    p_threshold = FloatSelector(default=0.05, label="p-value threshold")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")


# ---------------------------------------------------------------------------
# ToolMatch Report Form
# ---------------------------------------------------------------------------

class ToolMatchReportForm(ReportForm):
    tool1 = ToolSelector(label="Tool 1 (Library)")
    tool2 = ToolSelector(label="Tool 2 (De Novo)")
    min_psm = IntSelector(default=1, label="Min PSM count")
    min_unique_psm = IntSelector(default=1, label="Min unique PSM count")
    count_per_sample = BoolSelector(default=False, label="Count unique peptides per sample (matches UpSet/PIR logic)")


# ---------------------------------------------------------------------------
# Coverage Report Form (empty — uses project settings)
# ---------------------------------------------------------------------------

class ToolCoverageReportForm(ReportForm):
    pass


# ---------------------------------------------------------------------------
# UpSet Report Form
# ---------------------------------------------------------------------------

class UpSetReportForm(ReportForm):
    subsets = MultiSubsetSelector()
    min_proteins = IntSelector(default=1)


# ---------------------------------------------------------------------------
# Sample Report Form
# ---------------------------------------------------------------------------

class SampleReportForm(ReportForm):
    max_samples = IntSelector(default=10, label="Max samples")
    include_table = BoolSelector(default=True, label="Include table")
    chart_type = EnumSelector(values=["bar", "scatter"], label="Chart type")


class MedianReportForm(ReportForm):
    subsets = MultiSubsetSelector()
    lfq = LFQSelector(label="LFQ")
    include_outliers = BoolSelector(default=False, label="Include outlier samples")

# ---------------------------------------------------------------------------
# Monkey-patch: bind form classes to report classes
# ---------------------------------------------------------------------------

PCAReport.parameters = PCAReportForm
VolcanoReport.parameters = VolcanoReportForm
ToolMatchReport.parameters = ToolMatchReportForm
ToolCoverageReport.parameters = ToolCoverageReportForm
UpsetReport.parameters = UpSetReportForm
SampleReport.parameters = SampleReportForm
MedianReport.parameters = MedianReportForm