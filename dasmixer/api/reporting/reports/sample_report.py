"""Sample report implementation."""

import pandas as pd
import plotly.graph_objects as go
from typing import Optional
from flet import Icons

from ..base import BaseReport


class SampleReport(BaseReport):
    """
    Sample report demonstrating the report system architecture.
    
    Generates a simple chart and table based on project data.
    """
    
    name = "Sample Report"
    description = "Demonstrates report system with sample data"
    icon = Icons.BAR_CHART
    
    @staticmethod
    def get_parameter_defaults() -> dict[str, tuple[type, str]]:
        """Report parameters."""
        return {
            'max_samples': (int, '10'),
            'include_table': (str, 'Y'),
            'chart_type': (str, 'bar')
        }
    
    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        """Generate report."""
        max_samples = params['max_samples']
        include_table = params['include_table'].upper() == 'Y'
        chart_type = params['chart_type']
        
        # Get data from project
        samples = await self.project.get_samples()
        
        # Limit count
        samples_list = samples[:max_samples]
        
        # Create DataFrame
        samples_df = pd.DataFrame([
            {
                'id': s.id,
                'name': s.name,
                'subset': s.subset_id if s.subset_id else 'N/A'
            }
            for s in samples_list
        ])
        
        # Create plot
        if chart_type == 'bar':
            fig = go.Figure(data=[
                go.Bar(
                    x=samples_df['name'],
                    y=samples_df['id'],
                    name='Sample IDs'
                )
            ])
        else:
            fig = go.Figure(data=[
                go.Scatter(
                    x=samples_df['name'],
                    y=samples_df['id'],
                    mode='lines+markers',
                    name='Sample IDs'
                )
            ])
        
        fig.update_layout(
            title="Sample Distribution",
            xaxis_title="Sample Name",
            yaxis_title="Sample ID"
        )
        
        plots = [("Sample Distribution", fig)]
        
        # Table (if enabled)
        tables = []
        if include_table:
            tables.append(("Samples Table", samples_df, True))
        
        return plots, tables


# Register on import
from ..registry import registry
registry.register(SampleReport)
