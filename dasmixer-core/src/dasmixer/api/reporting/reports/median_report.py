import numpy as np
import pandas as pd
from dasmixer.api.reporting._icons import Icons
from scipy.stats import false_discovery_control, mannwhitneyu, ttest_ind
import plotly.graph_objects as go
from ..base import BaseReport
from dasmixer.utils.logger import logger
from smart_round import format_dataframe

class MedianReport(BaseReport):
    """Median Report class."""

    name = "Medians report"
    description = "Creates the table with medians and other basic stats for each protein in each group"

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        pass