"""Base class for report modules."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING
import pandas as pd
import plotly.graph_objects as go
from pydantic import BaseModel

if TYPE_CHECKING:
    from api.project.project import Project


class ReportParameters(BaseModel):
    """Base class for report parameters (for validation)."""
    pass


class BaseReport(ABC):
    """
    Base class for all report modules.
    
    Each report can produce:
    - Data table (DataFrame)
    - Visualization (Plotly Figure)
    - Or both
    """
    
    # Report metadata
    name: str = "Base Report"
    description: str = "Base report class"
    version: str = "1.0.0"
    
    @abstractmethod
    def get_parameters_schema(self) -> type[ReportParameters]:
        """
        Get Pydantic model for report parameters.
        
        Used for:
        - GUI form generation
        - CLI argument validation
        - API parameter validation
        
        Returns:
            Pydantic BaseModel subclass
        """
        pass
    
    @abstractmethod
    async def generate(
        self,
        project: 'Project',
        params: ReportParameters
    ) -> tuple[list[pd.DataFrame], list[go.Figure]]:
        """
        Generate report.
        
        Args:
            project: Project instance
            params: Validated parameters
            
        Returns:
            Tuple of (data_table, figure)
            Either can be None if not applicable
        """
        pass
    
    async def export_data(
        self,
        data: pd.DataFrame,
        output_path: Path | str,
        format: str = 'xlsx'
    ) -> None:
        """
        Export data table to file.
        
        Args:
            data: DataFrame to export
            output_path: Output file path
            format: Export format (xlsx, csv, tsv)
        """
        output_path = Path(output_path)
        
        if format == 'xlsx':
            data.to_excel(output_path, index=False)
        elif format == 'csv':
            data.to_csv(output_path, index=False)
        elif format == 'tsv':
            data.to_csv(output_path, sep='\t', index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    async def export_figure(
        self,
        figure: go.Figure,
        output_path: Path | str,
        format: str = 'png',
        width: int = 1200,
        height: int = 800
    ) -> None:
        """
        Export figure to file.
        
        Args:
            figure: Plotly figure
            output_path: Output file path
            format: Export format (png, svg, html, json)
            width: Image width in pixels
            height: Image height in pixels
        """
        output_path = Path(output_path)
        
        if format in ['png', 'svg', 'pdf']:
            figure.write_image(str(output_path), format=format, width=width, height=height)
        elif format == 'html':
            figure.write_html(str(output_path))
        elif format == 'json':
            figure.write_json(str(output_path))
        else:
            raise ValueError(f"Unsupported format: {format}")
