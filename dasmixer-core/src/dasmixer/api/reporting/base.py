"""Base class for report modules."""

from __future__ import annotations

import base64
import gzip
import json
import pickle
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from dataclasses import asdict as _dataclass_asdict
from typing import TYPE_CHECKING

import pandas as pd
from dasmixer.api.reporting._icons import Icons

from ..project import Project

if TYPE_CHECKING:
    import plotly.graph_objects as go
    from dasmixer.api.reporting.report_form import ReportForm
    from dasmixer.api.reporting.report_params import ReportParams


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
    icon: str = Icons.REPORT  # flet.Icons name

    # Typed parameter form class (set in subclasses to a ReportForm subclass).
    # When set, ReportItem will render a Parameters dialog instead of TextArea.
    parameters: type[ReportForm] | None = None

    # Typed dataclass for report parameters (set in subclasses)
    params_class: type[ReportParams] | None = None

    # Default name template, e.g. "{date} {time}" (overridable in subclasses)
    name_template: str = "{date} {time}"
    
    def __init__(
        self,
        project: Project,
        plots: list[tuple[str, go.Figure]] | None = None,
        tables: list[tuple[str, pd.DataFrame, bool]] | None = None,
        project_settings: dict | None = None,
        tools_settings: list[dict] | None = None,
        report_settings: dict | None = None,
        report_display_name: str | None = None,
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
        self._report_display_name = report_display_name

    @abstractmethod
    async def _generate_impl(
        self,
        params: ReportParams
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
    
    async def generate(self, params: ReportParams) -> int:
        """
        Generate report and save to database.
        
        Args:
            params: Typed parameters dataclass (from form.get_params())
            
        Returns:
            int: ID of created record in generated_reports
        """
        # 1. Compute display name
        self._report_display_name = self.get_report_name(params)
        
        # 2. Collect context
        self._project_settings = await self._collect_project_settings()
        self._tools_settings = await self._collect_tools_settings()
        
        # 3. Serialise report_settings from dataclass
        from dataclasses import asdict as _asdict
        self._report_settings = _asdict(params)
        
        # 4. Generate
        plots, tables = await self._generate_impl(params)
        
        # 5. Apply settings to figures
        plots_with_settings = [
            (name, self._apply_settings_to_figure(fig))
            for name, fig in plots
        ]
        
        # 6. Save to memory
        self._plots = plots_with_settings
        self._tables = tables
        
        # 7. Save to database (returns report_id)
        report_id = await self._save_to_db()
        return report_id

    async def _collect_project_settings(self) -> dict:
        """Collect project settings."""
        settings = await self.project.get_all_settings()
        return settings
        # font_size = await self.project.get_setting('plot_font_size', '12')
        # plot_width = await self.project.get_setting('plot_width', '1200')
        # plot_height = await self.project.get_setting('plot_height', '800')
        #
        # return {
        #     'plot_font_size': int(font_size),
        #     'plot_width': int(plot_width),
        #     'plot_height': int(plot_height)
        # }
    
    async def _collect_tools_settings(self) -> list[dict]:
        """Collect tools settings."""
        tools = await self.project.get_tools()
        return [
            {
                'name': tool.name,
                'type': tool.type,
                'settings': tool.settings
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

        font_size = int(self._project_settings.get('plot_font_size', 12))
        fig.update_layout(
            template='plotly_white',
            font={"size": font_size},
            width=int(self._project_settings.get('plot_width', 1200)),
            height=int(self._project_settings.get('plot_height', 800)),
        )
        fig.update_annotations(font_size=font_size)
        
        return fig

    def get_report_name(self, params: ReportParams) -> str:
        """Compute report display name from template and dataclass fields.

        Substitutes ``{field_name}``, ``{date}`` (YYMMDD), and ``{time}`` (HH:MM)
        placeholders from the current datetime and all fields of *params*.
        The template is taken from ``params.name_template``, falling back to
        ``self.name_template``.
        """
        from dataclasses import asdict
        from datetime import datetime
        from dasmixer.utils.logger import logger

        now = datetime.now()
        subst: dict[str, str] = {}
        for k, v in asdict(params).items():
            if isinstance(v, (list, tuple)):
                v = "_".join(str(x) for x in v)
            subst[k] = str(v) if v is not None else ""
        subst['date'] = now.strftime('%y%m%d')
        subst['time'] = now.strftime('%H:%M')
        template = (
            getattr(params, 'name_template', None)
            or self.name_template
        )
        try:
            return template.format(**subst)
        except (KeyError, IndexError):
            logger.warning(
                "Invalid name_template %r for report %r",
                template, self.name,
            )
            return template

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
            (report_name, name, created_at, plots, tables, project_settings, tools_settings, report_settings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.name,
                self._report_display_name,
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
        project: Project,
        report_id: int
    ) -> BaseReport:
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
        report_display_name = row['name'] if 'name' in row.keys() else None
        
        # Create instance
        return cls(
            project=project,
            plots=plots,
            tables=tables,
            project_settings=project_settings,
            tools_settings=tools_settings,
            report_settings=report_settings,
            report_display_name=report_display_name,
        )
    
    def get_context(self, show_parameters: bool = True) -> dict:
        """
        Get context for export (HTML/Word).
        
        Args:
            show_parameters: Include parameters in context
            
        Returns:
            dict: Context for jinja2/html4docx
            
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
    
    PROJECT_PARAMS_WHITELIST = [
        'max_blast_accept', 'max_blast_reject', 'ion_types', 'water_loss',
        'nh3_loss', 'ion_ppm_threshold', 'fragment_charges',
        'ignore_spectre_charges', 'min_precursor_charge', 'max_precursor_charge',
        'force_isotope_offset', 'max_isotope_offset', 'seq_criteria',
        'proteins_min_peptides', 'proteins_min_unique_evidence', 'lfq_enzyme',
        'lfq_min_peptide_length', 'lfq_max_peptide_length',
        'lfq_max_cleavage_sites',
    ]

    def _build_settings_context(self) -> dict:
        """Build settings section."""
        project_params = []
        if self._project_settings:
            for key, value in self._project_settings.items():
                if key in self.PROJECT_PARAMS_WHITELIST:
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
                # PNG for Word and noscript
                png_bytes = fig.to_image(format='png')
                png_base64 = base64.b64encode(png_bytes).decode('utf-8')
                
                # JSON for HTML
                plotly_json = fig.to_json()
                
                figures.append({
                    "name": name,
                    "png": png_bytes,
                    "png_base64": png_base64,
                    "json": plotly_json
                })
        
        return figures
    
    def _render_html(self, is_interactive=True) -> str:
        """
        Render report to HTML string.
        
        Returns:
            str: HTML content
        """
        from jinja2 import Environment, FileSystemLoader
        
        # Load template
        template_dir = Path(__file__).parent / 'templates'
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template('report.html.j2')
        
        # Render
        context = self.get_context()
        context['is_interactive'] = is_interactive
        html = template.render(**context)
        
        return html
    
    async def export(
        self,
        output_path: Path | str,
        formats: set[str] | frozenset[str] = frozenset({'html', 'docx', 'xlsx'}),
        xlsx_mode: str = 'all',
    ) -> dict[str, Path]:
        """
        Export report to files.
        
        Args:
            output_path: Path to folder for saving
            formats: set of formats to export ('html', 'docx', 'xlsx')
            xlsx_mode: 'all' for all tables, 'large_only' for non-UI tables only
            
        Returns:
            dict: Paths to created files
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Use the saved display name for filename (without timestamp)
        report_name = self._report_display_name or self.name
        base_filename = self._sanitize_filename(f"{self.name}_{report_name}")
        
        result: dict[str, Path] = {}
        
        if 'html' in formats:
            result['html'] = await self._export_html(output_path, base_filename)
        if 'docx' in formats:
            result['docx'] = await self._export_word(output_path, base_filename)
        if 'xlsx' in formats:
            result['xlsx'] = await self._export_excel(output_path, base_filename, mode=xlsx_mode)
        
        return result
    
    async def _export_html(self, output_path: Path, base_filename: str) -> Path:
        """
        Export to HTML.
        
        Args:
            output_path: Output directory
            base_filename: Base filename without extension
            
        Returns:
            Path to created file
        """
        html = self._render_html()
        
        # Save
        output_file = output_path / f"{base_filename}.html"
        output_file.write_text(html, encoding='utf-8')
        
        return output_file
    
    async def _export_word(self, output_path: Path, base_filename: str) -> Path:
        """
        Export to Word using html4docx.
        
        Args:
            output_path: Output directory
            base_filename: Base filename without extension
            
        Returns:
            Path to created file
        """
        from docx import Document
        from html4docx import HtmlToDocx
        
        # Render HTML
        html = self._render_html(is_interactive=False)
        
        # Create Word document
        doc = Document()
        html_converter = HtmlToDocx()
        html_converter.add_html_to_document(html, doc)

        # Resize documents
        text_width = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin

        for i, image in enumerate(doc.inline_shapes):
            original_width, original_height = image.width, image.height

            new_height = int(original_height * text_width / original_width)

            image.width = text_width
            image.height = new_height
        # Save
        output_file = output_path / f"{base_filename}.docx"
        doc.save(str(output_file))
        
        return output_file
    
    async def _export_excel(self, output_path: Path, base_filename: str, mode: str = 'all') -> Path:
        """
        Export tables to Excel with each table on separate sheet.
        
        Args:
            output_path: Output directory
            base_filename: Base filename without extension
            
        Returns:
            Path to created file
        """
        if not self._tables:
            # Create empty file if no tables
            output_file = output_path / f"{base_filename}.xlsx"
            pd.DataFrame().to_excel(output_file, index=False)
            return output_file
        
        output_file = output_path / f"{base_filename}.xlsx"
        
        # Create Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for name, df, show_in_ui in self._tables:
                if mode == 'large_only' and show_in_ui:
                    continue  # Skip UI-visible tables; export only large/background tables
                sheet_name = self._sanitize_sheet_name(name)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return output_file
    
    @staticmethod
    def _sanitize_sheet_name(name: str) -> str:
        """
        Sanitize sheet name for Excel.
        
        Excel sheet names:
        - Max 31 characters
        - Cannot contain: \\ / * ? : [ ]
        
        Args:
            name: Original name
            
        Returns:
            Sanitized name
        """
        # Remove invalid characters
        invalid_chars = ['\\', '/', '*', '?', ':', '[', ']']
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Trim to 31 characters
        if len(sanitized) > 31:
            sanitized = sanitized[:31]
        
        return sanitized

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        Sanitize filename for NTFS/Windows.
        
        Removes characters invalid in NTFS filenames:
        \\ / : * ? " < > |
        Also replaces ':' with '-' before filtering for readability.
        
        Args:
            name: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace colon with dash first for readability
        sanitized = name.replace(':', '-')
        # Remove remaining invalid characters
        invalid_chars = '\\/*?"<>|'
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        # Collapse multiple underscores
        import re
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip()
