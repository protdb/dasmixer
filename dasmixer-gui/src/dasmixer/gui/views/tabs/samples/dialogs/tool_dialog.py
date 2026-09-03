"""Dialog for creating and editing identification tools."""

import flet as ft
from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Tool
from dasmixer.api.inputs.registry import registry
from ..constants import get_default_color
from dasmixer.gui.components.color_picker import ColorPickerField
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ToolDialog:
    """Dialog for adding or editing an identification tool."""
    
    def __init__(self, project: Project, page: ft.Page, on_success_callback=None, tool: Tool = None):
        """
        Initialize tool dialog.
        
        Args:
            project: Project instance
            page: Flet page
            on_success_callback: Callback to execute after successful save
            tool: Existing tool to edit (None for creating new)
        """
        self.project = project
        self.page = page
        self.on_success_callback = on_success_callback
        self.tool = tool
        self.is_edit_mode = tool is not None
        
        # Dialog controls
        self.name_field = None
        self.tool_type_group = None
        self.parser_dropdown = None
        self.color_field = None
        self.dialog = None
    
    async def show(self):
        """Show dialog immediately, then load data and fill fields."""
        dlg_title = "Edit Tool" if self.is_edit_mode else "Add Identification Tool"

        # Open spinner dialog right away
        self.dialog = ft.AlertDialog(
            title=ft.Text(dlg_title),
            content=ft.Container(
                content=ft.ProgressRing(width=28, height=28, stroke_width=3),
                alignment=ft.Alignment.CENTER,
                width=400,
                height=80,
            ),
            actions=[ft.TextButton("Cancel", on_click=self._close)],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

        # Load data
        parsers = registry.get_identification_parsers()
        parser_options = [
            ft.dropdown.Option(key=name, text=name)
            for name in parsers.keys()
        ]

        if not parser_options:
            self.dialog.open = False
            self.page.update()
            show_snack(self.page, "No identification parsers available", ft.Colors.RED_400)
            self.page.update()
            return

        if not self.is_edit_mode:
            tools = await self.project.get_tools()
            default_color = get_default_color(len(tools))
        else:
            default_color = self.tool.display_color or "#9333EA"

        # Build form fields
        self.name_field = ft.TextField(
            label="Tool Name",
            value=self.tool.name if self.is_edit_mode else "",
            hint_text="e.g., PowerNovo2, MaxQuant",
            autofocus=True,
        )
        self.tool_type_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="Library", label="Library Search"),
                ft.Radio(value="De Novo", label="De Novo Sequencing"),
            ]),
            value=self.tool.type if self.is_edit_mode else "Library",
        )
        self.parser_dropdown = ft.Dropdown(
            label="Parser / Format",
            options=parser_options,
            value=self.tool.parser if self.is_edit_mode else parser_options[0].key,
            width=300,
        )
        self.color_field = ColorPickerField(
            value=default_color,
            label="Color (hex)",
            compact=False,                # full-режим
        )

        # Replace spinner with real form
        self.dialog.content = ft.Column(
            [
                self.name_field,
                ft.Text("Tool Type:", weight=ft.FontWeight.W_500),
                self.tool_type_group,
                self.parser_dropdown,
                self.color_field,
                ft.Container(height=5),
                ft.Text(
                    "Tool represents an identification method (e.g., de novo, database search)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600,
                ),
            ],
            tight=True,
            width=460,
            scroll=ft.ScrollMode.AUTO,
        )
        self.dialog.actions = [
            ft.TextButton("Cancel", on_click=self._close),
            ft.ElevatedButton(
                "Save" if self.is_edit_mode else "Add",
                on_click=lambda e: self.page.run_task(self._save, e),
            ),
        ]
        self.page.update()
    
    def _close(self, e=None):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()
    
    async def _save(self, e):
        """Save the tool."""
        # Validate
        if not self.name_field.value:
            self.name_field.error_text = "Name is required"
            self.name_field.update()
            return
        
        try:
            # Prepare color (component returns '#RRGGBB')
            if not self.color_field.is_valid:
                self.color_field.set_error("Invalid color")
                self.page.update()
                return
            color = self.color_field.value
            
            if self.is_edit_mode:
                # Update existing tool
                self.tool.name = self.name_field.value
                self.tool.type = self.tool_type_group.value
                self.tool.parser = self.parser_dropdown.value
                self.tool.display_color = color
                
                await self.project.update_tool(self.tool)
                
                success_message = f"Updated tool: {self.tool.name}"
            else:
                # Create new tool
                await self.project.add_tool(
                    name=self.name_field.value,
                    type=self.tool_type_group.value,
                    parser=self.parser_dropdown.value,
                    display_color=color
                )
                
                success_message = f"Added tool: {self.name_field.value}"
            
            # Close dialog
            self._close()
            
            # Show success
            show_snack(self.page, success_message, ft.Colors.GREEN_400)
            self.page.update()
            
            # Call success callback
            if self.on_success_callback:
                await self.on_success_callback()
        
        except Exception as ex:
            logger.exception(ex)
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()
