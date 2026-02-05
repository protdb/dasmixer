"""Base class for report modules."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import pandas as pd
import plotly.graph_objects as go
import gzip
import pickle
import json
from datetime import datetime


class BaseReport(ABC):
    """
    Base class for all report modules.
    
    Each report can produce:
    - Plots: list of (name, go.Figure)
    - Tables: list of (name, pd.DataFrame, show_in_ui)
    
    Reports can be:
    1. Generated from scratch via generate()
    2. Loaded from database via load_from_db()
    """
    
    # Report metadata (must be overridden in subclasses)
    name: str = "Base Report"
    description: str = "Base report class"
    icon: str = "assessment"  # flet.Icons name
    
    def __init__(
        self,
        project: 'Project',
        plots: Optional[list[tuple[str, go.Figure]]] = None,
        tables: Optional[list[tuple[str, pd.DataFrame, bool]]] = None,
        project_settings: Optional[dict] = None,
        tools_settings: Optional[list[dict]] = None,
        report_settings: Optional[dict] = None
    ):
        """
        Initialize report.
        
        Args:
            project: Project instance
            plots: Pre-loaded plots (for loading from DB)
            tables: Pre-loaded tables (for loading from DB)
            project_settings: Project settings at generation time
            tools_settings: Tools settings at generation time
            report_settings: Report parameters at generation time
        """
        self.project = project
        self._plots = plots
        self._tables = tables
        self._project_settings = project_settings
        self._tools_settings = tools_settings
        self._report_settings = report_settings
    
    @staticmethod
    def get_parameter_defaults() -> dict[str, tuple[type, str]]:
        """
        Get report parameters with defaults.
        
        Returns:
            dict: {
                'param_name': (type, 'default_value_as_string'),
                ...
            }
            
        Example:
            {
                'tool1': (str, 'PN2'),
                'tool2': (str, 'MQ'),
                'max_values': (int, '42'),
                'include_plots': (str, 'Y')
            }
        """
        return {}
    
    @abstractmethod
    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        """
        Internal implementation of report generation.
        
        Must be overridden in subclasses.
        
        Args:
            params: Validated parameters
            
        Returns:
            tuple: (plots, tables)
                - plots: list[tuple[name, figure]]
                - tables: list[tuple[name, dataframe, show_in_ui]]
        """
        pass
    
    async def generate(self, params: dict) -> None:
        """
        Generate report with validation and saving.
        
        Wrapper around _generate_impl() that:
        1. Validates parameters
        2. Collects context (project/tools settings)
        3. Calls _generate_impl()
        4. Applies settings to figures
        5. Saves to database
        
        Args:
            params: Parameters dict (raw from UI)
            
        Raises:
            ValueError: If parameters are invalid
        """
        # 1. Validate parameters
        validated_params = self._validate_parameters(params)
        
        # 2. Collect context
        self._project_settings = await self._collect_project_settings()
        self._tools_settings = await self._collect_tools_settings()
        self._report_settings = validated_params
        
        # 3. Generate
        plots, tables = await self._generate_impl(validated_params)
        
        # 4. Apply settings to figures
        plots_with_settings = [
            (name, self._apply_settings_to_figure(fig))
            for name, fig in plots
        ]
        
        # 5. Save to memory
        self._plots = plots_with_settings
        self._tables = tables
        
        # 6. Save to database
        await self._save_to_db()
    
    def _validate_parameters(self, params: dict) -> dict:
        """
        Validate and convert parameter types.
        
        Args:
            params: Raw parameters (all values as strings)
            
        Returns:
            dict: Validated parameters with correct types
            
        Raises:
            ValueError: If parameter cannot be converted
        """
        defaults = self.get_parameter_defaults()
        validated = {}
        
        for param_name, (param_type, default_value) in defaults.items():
            # Get value from params or use default
            raw_value = params.get(param_name, default_value)
            
            try:
                # Type conversion
                if param_type == int:
                    validated[param_name] = int(raw_value)
                elif param_type == float:
                    validated[param_name] = float(raw_value)
                elif param_type == str:
                    validated[param_name] = str(raw_value)
                elif param_type == bool:
                    validated[param_name] = str(raw_value).lower() in ('true', '1', 'yes', 'y')
                else:
                    validated[param_name] = raw_value
            except (ValueError, AttributeError) as e:
                raise ValueError(
                    f"Parameter '{param_name}': cannot convert '{raw_value}' to {param_type.__name__}"
                ) from e
        
        return validated
    
    async def _collect_project_settings(self) -> dict:
        """Collect project settings."""
        font_size = await self.project.get_setting('plot_font_size', '12')
        plot_width = await self.project.get_setting('plot_width', '1200')
        plot_height = await self.project.get_setting('plot_height', '800')
        
        return {
            'plot_font_size': int(font_size),
            'plot_width': int(plot_width),
            'plot_height': int(plot_height)
        }
    
    async def _collect_tools_settings(self) -> list[dict]:
        """Collect tools settings."""
        tools = await self.project.get_tools()
        return [
            {
                'name': tool.name,
                'type': tool.type,
                'settings': json.loads(tool.settings) if tool.settings else {}
            }
            for tool in tools
        ]
    
    def _apply_settings_to_figure(self, fig: go.Figure) -> go.Figure:
        """
        Apply global settings to figure.
        
        Args:
            fig: Original figure
            
        Returns:
            Modified figure
        """
        if not self._project_settings:
            return fig
        
        fig.update_layout(
            font=dict(size=self._project_settings['plot_font_size']),
            width=self._project_settings['plot_width'],
            height=self._project_settings['plot_height']
        )
        
        return fig
    
    async def _save_to_db(self) -> int:
        """
        Save report results to database.
        
        Returns:
            int: ID of created record
        """
        # Serialize plots
        plots_blob = None
        if self._plots:
            plots_blob = gzip.compress(pickle.dumps(self._plots))
        
        # Serialize tables
        tables_blob = None
        if self._tables:
            tables_blob = gzip.compress(pickle.dumps(self._tables))
        
        # JSON settings
        project_settings_json = json.dumps(self._project_settings) if self._project_settings else None
        tools_settings_json = json.dumps(self._tools_settings) if self._tools_settings else None
        report_settings_json = json.dumps(self._report_settings) if self._report_settings else None
        
        # Current time
        now = datetime.now().isoformat()
        
        # Insert into DB
        cursor = await self.project._execute(
            """
            INSERT INTO generated_reports 
            (report_name, created_at, plots, tables, project_settings, tools_settings, report_settings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.name,
                now,
                plots_blob,
                tables_blob,
                project_settings_json,
                tools_settings_json,
                report_settings_json
            )
        )
        await self.project.save()
        
        return cursor.lastrowid
    
    @classmethod
    async def load_from_db(
        cls,
        project: 'Project',
        report_id: int
    ) -> 'BaseReport':
        """
        Load report from database by ID.
        
        Args:
            project: Project instance
            report_id: ID in generated_reports table
            
        Returns:
            Report instance with loaded data
            
        Raises:
            ValueError: If record not found
        """
        row = await project._fetchone(
            "SELECT * FROM generated_reports WHERE id = ?",
            (report_id,)
        )
        
        if not row:
            raise ValueError(f"Report with id={report_id} not found")
        
        # Deserialize
        plots = None
        if row['plots']:
            plots = pickle.loads(gzip.decompress(row['plots']))
        
        tables = None
        if row['tables']:
            tables = pickle.loads(gzip.decompress(row['tables']))
        
        project_settings = json.loads(row['project_settings']) if row['project_settings'] else None
        tools_settings = json.loads(row['tools_settings']) if row['tools_settings'] else None
        report_settings = json.loads(row['report_settings']) if row['report_settings'] else None
        
        # Create instance
        return cls(
            project=project,
            plots=plots,
            tables=tables,
            project_settings=project_settings,
            tools_settings=tools_settings,
            report_settings=report_settings
        )
    
    def get_context(self, show_parameters: bool = True) -> dict:
        """
        Get context for export (HTML/Word).
        
        Args:
            show_parameters: Include parameters in context
            
        Returns:
            dict: Context for jinja2/docxtpl
            
        Raises:
            ValueError: If report has no data
        """
        if not self._plots and not self._tables:
            raise ValueError("Report has no data. Call generate() first or load from DB.")
        
        context = {
            "report_name": self.name,
            "show_parameters": show_parameters,
            "settings": self._build_settings_context(),
            "report_parameters": self._build_report_params_context(),
            "tables": self._build_tables_context(),
            "figures": self._build_figures_context()
        }
        
        return context
    
    def _build_settings_context(self) -> dict:
        """Build settings section."""
        project_params = []
        if self._project_settings:
            for key, value in self._project_settings.items():
                project_params.append({"key": key, "value": str(value)})
        
        tools = []
        if self._tools_settings:
            for tool_dict in self._tools_settings:
                settings_list = []
                for key, value in tool_dict.get('settings', {}).items():
                    settings_list.append({"key": key, "value": str(value)})
                
                tools.append({
                    "name": tool_dict['name'],
                    "type": tool_dict['type'],
                    "settings": settings_list
                })
        
        return {
            "project_parameters": project_params,
            "tools": tools
        }
    
    def _build_report_params_context(self) -> list[dict]:
        """Build report parameters list."""
        params = []
        if self._report_settings:
            for key, value in self._report_settings.items():
                params.append({"key": key, "value": str(value)})
        return params
    
    def _build_tables_context(self) -> list[dict]:
        """Build tables for context."""
        tables = []
        if self._tables:
            for name, df, show_in_ui in self._tables:
                if show_in_ui:  # Export only visible tables
                    tables.append({
                        "name": name,
                        "data": {
                            "headers": df.columns.tolist(),
                            "rows": df.values.tolist()
                        }
                    })
        return tables
    
    def _build_figures_context(self) -> list[dict]:
        """Build figures for context."""
        figures = []
        if self._plots:
            for name, fig in self._plots:
                # PNG for Word
                png_bytes = fig.to_image(format='png')
                
                # JSON for HTML
                plotly_json = fig.to_json()
                
                figures.append({
                    "name": name,
                    "png": png_bytes,
                    "json": plotly_json
                })
        
        return figures
    
    async def export(self, output_path: Path | str) -> None:
        """
        Export report to files.
        
        Args:
            output_path: Path to folder for saving
            
        Creates:
            - report_name.html
            - report_name.docx (stub)
            - report_name.xlsx (stub)
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # HTML - functional implementation
        await self._export_html(output_path)
        
        # Word - stub
        await self._export_word(output_path)
        
        # Excel - stub
        await self._export_excel(output_path)
    
    async def _export_html(self, output_path: Path) -> None:
        """Export to HTML."""
        from jinja2 import Environment, FileSystemLoader
        
        # Load template
        template_dir = Path(__file__).parent / 'templates'
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template('report.html.j2')
        
        # Render
        context = self.get_context()
        html = template.render(**context)
        
        # Save
        output_file = output_path / f"{self.name}.html"
        output_file.write_text(html, encoding='utf-8')
    
    async def _export_word(self, output_path: Path) -> None:
        """
        Export to Word (stub).
        
        TODO: Implement using docxtpl
        """
        pass
    
    async def _export_excel(self, output_path: Path) -> None:
        """
        Export to Excel (stub).
        
        TODO: Implement table export to separate sheets
        """
        pass
