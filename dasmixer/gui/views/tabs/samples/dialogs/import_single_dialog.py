"""Dialog for importing individual files."""

import flet as ft
from pathlib import Path
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ImportSingleDialog:
    """Dialog for importing individually selected files.
    
    Supports fixed-sample mode (when called from a sample panel):
    - fixed_sample_name: sample name is pre-filled and read-only
    - fixed_spectra_file_id: spectra file is pre-selected (for ident import from panel)
    - lock_group: group dropdown is disabled/hidden
    """

    def __init__(
        self,
        project: Project,
        page: ft.Page,
        import_type: str,
        tool_id: int = None,
        on_import_callback=None,
        fixed_sample_name: str | None = None,
        fixed_spectra_file_id: int | None = None,
        lock_group: bool = False,
    ):
        """
        Initialize single file import dialog.

        Args:
            project: Project instance
            page: Flet page
            import_type: "spectra" or "identifications"
            tool_id: Tool ID (required for identifications)
            on_import_callback: Callback for import execution
            fixed_sample_name: If set, sample name field is pre-filled and read-only
            fixed_spectra_file_id: If set, this spectra file ID is used directly
                                   (bypasses sample-name-based lookup for ident import)
            lock_group: If True, group dropdown is disabled
        """
        self.project = project
        self.page = page
        self.import_type = import_type
        self.tool_id = tool_id
        self.on_import_callback = on_import_callback
        self.fixed_sample_name = fixed_sample_name
        self.fixed_spectra_file_id = fixed_spectra_file_id
        self.lock_group = lock_group

    async def show(self):
        """Show file picker and then configuration dialog."""
        try:
            result = await ft.FilePicker().pick_files(
                dialog_title=f"Select {self.import_type.title()} Files",
                allow_multiple=True
            )

            if not result:
                return  # User cancelled

            # If fixed_sample_name, override stem with that name
            if self.fixed_sample_name:
                file_list = [(Path(f.path or ''), self.fixed_sample_name) for f in result if f.path]
            else:
                file_list = [(Path(f.path or ''), Path(f.name or '').stem) for f in result if f.path]

            await self._show_config_dialog(file_list)

        except Exception as ex:
            logger.exception(ex)
            import traceback
            traceback.print_exc()
            show_snack(self.page, f"Error opening file picker: {ex}", ft.Colors.RED_400)
            self.page.update()

    async def _show_config_dialog(self, file_list):
        """Show configuration dialog for selected files.

        The dialog opens immediately with a spinner; data is fetched
        asynchronously and the content is replaced once ready.
        """
        dlg_title = f"Configure {self.import_type.title()} Import"

        # Open spinner immediately
        config_dialog = ft.AlertDialog(
            title=ft.Text(dlg_title),
            content=ft.Container(
                content=ft.ProgressRing(width=28, height=28, stroke_width=3),
                alignment=ft.Alignment.CENTER,
                width=600,
                height=80,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(config_dialog))
            ],
        )
        self.page.overlay.append(config_dialog)
        config_dialog.open = True
        self.page.update()

        # Fetch data
        if self.import_type == "spectra":
            parsers = registry.get_spectra_parsers()
            parser_type_label = "Spectra Format / Parser"

            groups = await self.project.get_subsets()
            group_options = [
                ft.DropdownOption(key=str(g.id), text=g.name) for g in groups
            ]

            if not group_options and not self.lock_group:
                config_dialog.open = False
                self.page.update()
                show_snack(self.page, "Please create at least one comparison group first", ft.Colors.ORANGE_400)
                self.page.update()
                return

            parser_options = [
                ft.DropdownOption(key=name, text=name)
                for name in parsers.keys()
            ]

            if not parser_options:
                config_dialog.open = False
                self.page.update()
                show_snack(self.page, "No spectra parsers available", ft.Colors.RED_400)
                self.page.update()
                return

            parser_dropdown = ft.Dropdown(
                label=parser_type_label,
                options=parser_options,
                value=parser_options[0].key,
                width=200,
            )
        else:
            tool = await self.project.get_tool(self.tool_id)
            parser_type_label = f"Format: {tool.parser}"
            parser_dropdown = None
            group_options = []

            if not self.fixed_sample_name:
                samples = await self.project.get_samples()
                if not samples:
                    config_dialog.open = False
                    self.page.update()
                    show_snack(self.page, "Please import spectra first", ft.Colors.ORANGE_400)
                    self.page.update()
                    return

        # Build file-config rows
        file_configs = []
        for file_path, sample_id_stem in file_list:
            sample_name = ft.TextField(
                label="Sample Name",
                value=sample_id_stem,
                width=300,
                read_only=bool(self.fixed_sample_name),
            )
            if self.import_type == "spectra" and not self.lock_group:
                group_dropdown = ft.Dropdown(
                    label="Comparison Group",
                    options=group_options,
                    value=group_options[0].key if group_options else None,
                    width=200,
                )
            else:
                group_dropdown = None

            file_configs.append({
                'file_path': file_path,
                'sample_name': sample_name,
                'group_dropdown': group_dropdown,
            })

        # Build content controls
        config_controls = []
        if parser_dropdown:
            config_controls.append(
                ft.Container(
                    content=ft.Row([ft.Text("Parser:", weight=ft.FontWeight.BOLD), parser_dropdown]),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLUE_300),
                    border_radius=5,
                    bgcolor=ft.Colors.BLUE_50,
                )
            )
        else:
            config_controls.append(
                ft.Container(
                    content=ft.Text(parser_type_label, weight=ft.FontWeight.BOLD),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLUE_300),
                    border_radius=5,
                    bgcolor=ft.Colors.BLUE_50,
                )
            )

        for cfg in file_configs:
            row_controls = [cfg['sample_name']]
            if cfg['group_dropdown']:
                row_controls.append(cfg['group_dropdown'])
            config_controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"File: {cfg['file_path'].name}", weight=ft.FontWeight.BOLD, size=12),
                            ft.Row(row_controls, spacing=10),
                        ],
                        spacing=5,
                    ),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                )
            )

        async def start_import(e):
            try:
                config_dialog.open = False
                self.page.update()

                files_to_import = [(cfg['file_path'], cfg['sample_name'].value) for cfg in file_configs]

                if self.on_import_callback:
                    if self.import_type == "spectra":
                        if self.lock_group or not file_configs[0]['group_dropdown']:
                            subset_id = None
                        else:
                            subset_id = int(file_configs[0]['group_dropdown'].value)
                        await self.on_import_callback(
                            files_to_import,
                            subset_id,
                            parser_dropdown.value,
                            fixed_sample_name=self.fixed_sample_name,
                        )
                    else:
                        await self.on_import_callback(
                            files_to_import,
                            self.tool_id,
                            fixed_spectra_file_id=self.fixed_spectra_file_id,
                        )
            except Exception as ex:
                logger.exception(ex)
                show_snack(self.page, f"Import error: {ex}", ft.Colors.RED_400)
                self.page.update()

        # Replace spinner with real content
        config_dialog.content = ft.Column(
            config_controls,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
            width=600,
            height=min(450, len(config_controls) * 100 + 80),
        )
        config_dialog.actions = [
            ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(config_dialog)),
            ft.ElevatedButton("Import", on_click=lambda e: self.page.run_task(start_import, e)),
        ]
        self.page.update()

    def _close_dialog(self, dialog):
        """Close a dialog."""
        dialog.open = False
        self.page.update()
