"""Dialog for creating and editing identification tools."""

import flet as ft
from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Tool
from dasmixer.api.inputs.registry import registry
from ..constants import get_default_color
from dasmixer.gui.utils import show_snack


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
        """Show the dialog."""
        # Get available identification parsers
        parsers = registry.get_identification_parsers()
        parser_options = [
            ft.dropdown.Option(key=name, text=name)
            for name in parsers.keys()
        ]
        
        if not parser_options:
            show_snack(self.page, "No identification parsers available", ft.Colors.RED_400)
            self.page.update()
            return
        
        # Get default color for new tools
        if not self.is_edit_mode:
            tools = await self.project.get_tools()
            default_color = get_default_color(len(tools))
        else:
            default_color = self.tool.display_color or "#9333EA"
        
        # Remove # from color for display
        if default_color.startswith('#'):
            default_color = default_color[1:]
        
        # Create fields
        self.name_field = ft.TextField(
            label="Tool Name",
            value=self.tool.name if self.is_edit_mode else "",
            hint_text="e.g., PowerNovo2, MaxQuant",
            autofocus=True
        )
        
        # Tool type selector
        self.tool_type_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="Library", label="Library Search"),
                ft.Radio(value="De Novo", label="De Novo Sequencing")
            ]),
            value=self.tool.type if self.is_edit_mode else "Library"
        )
        
        # Parser dropdown
        self.parser_dropdown = ft.Dropdown(
            label="Parser / Format",
            options=parser_options,
            value=self.tool.parser if self.is_edit_mode else parser_options[0].key,
            width=300
        )
        
        self.color_field = ft.TextField(
            label="Color (hex)",
            value=default_color,
            max_length=6,
            hint_text="e.g., 9333EA for purple"
        )
        
        # Color preview
        color_preview = ft.Container(
            width=50,
            height=50,
            border_radius=5,
            bgcolor=f"#{default_color}"
        )
        
        def update_color_preview(e):
            """Update color preview when color field changes."""
            color_value = self.color_field.value
            if color_value:
                if not color_value.startswith('#'):
                    color_value = '#' + color_value
                try:
                    color_preview.bgcolor = color_value
                    color_preview.update()
                except:
                    pass
        
        self.color_field.on_change = update_color_preview
        
        # Create dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text("Edit Tool" if self.is_edit_mode else "Add Identification Tool"),
            content=ft.Column([
                self.name_field,
                ft.Text("Tool Type:", weight=ft.FontWeight.W_500),
                self.tool_type_group,
                self.parser_dropdown,
                ft.Row([
                    self.color_field,
                    color_preview
                ], alignment=ft.MainAxisAlignment.START, spacing=10),
                ft.Container(height=5),
                ft.Text(
                    "Tool represents an identification method (e.g., de novo, database search)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self._close
                ),
                ft.ElevatedButton(
                    "Save" if self.is_edit_mode else "Add",
                    on_click=lambda e: self.page.run_task(self._save, e)
                )
            ]
        )
        
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
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
            # Prepare color
            color = self.color_field.value
            if not color.startswith('#'):
                color = '#' + color
            
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
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()
