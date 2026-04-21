import numpy as np
import pandas as pd
import plotly.express as px
from flet import Icons
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ..base import BaseReport

class UpsetReport(BaseReport):
    name = "Upset Plot"
    description = "Upset plot for protein identifications"
    icon = Icons.INSERT_CHART_ROUNDED

    @staticmethod
    def get_parameter_defaults() -> dict[str, tuple[type, str]]:
        return {}

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        pass