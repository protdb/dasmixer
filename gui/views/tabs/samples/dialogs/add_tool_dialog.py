"""Add Tool dialog with type/parser selection."""

import flet as ft

from api.inputs.registry import registry


class AddToolDialog:
    """
    Dialog for adding new identification tool.
    
    NEW: Includes type selection (Library/De Novo) and parser selection.
    """
    
    def __init__(self, page: ft.Page, project):
        """
        Initialize dialog.
        
        Args:
            page: Flet page
            project: Project instance
        """
        self.page = page
        self.project = project
        self.on_success_callback = None
    
    async def show(self, on_success=None):
        """
        Show add tool dialog.
        
        Args:
            on_success: Callback to call after successful creation
        """
        self.on_success_callback = on_success
        
        # Get available identification parsers
        parsers = registry.get_identification_parsers()
        parser_options = [
            ft.dropdown.Option(key=name, text=name)
            for name in parsers.keys()
        ]
        
        if not parser_options:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("No identification parsers available"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        # Form fields
        name_field = ft.TextField(
            label="Tool Name",
            hint_text="e.g., PowerNovo2_Run1, MaxQuant_Trypsin",
            autofocus=True
        )
        
        # NEW: Tool type selector
        tool_type_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="Library", label="Library Search"),
                ft.Radio(value="De Novo", label="De Novo Sequencing")
            ]),
            value="Library"
        )
        
        # RENAMED: Parser dropdown (was "Type")
        parser_dropdown = ft.Dropdown(
            label="Parser / Format",
            options=parser_options,
            value=parser_options[0].key,
            width=300
        )
        
        color_field = ft.TextField(
            label="Color (hex)",
            value="9333EA",
            hint_text="Without #"
        )
        
        async def save_tool(e):
            if not name_field.value:
                name_field.error_text = "Name is required"
                name_field.update()
                return
            
            try:
                color = color_field.value
                if not color.startswith('#'):
                    color = '#' + color
                
                # NEW: Pass both type and parser
                await self.project.add_tool(
                    name=name_field.value,
                    type=tool_type_group.value,  # "Library" or "De Novo"
                    parser=parser_dropdown.value,  # Parser name
                    display_color=color
                )
                
                # Close dialog
                dialog.open = False
                self.page.update()
                
                # Show success
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Added tool: {name_field.value}"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
                # Call success callback
                if self.on_success_callback:
                    await self.on_success_callback()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Add Identification Tool"),
            content=ft.Column([
                name_field,
                ft.Container(height=10),
                ft.Text("Tool Type:", weight=ft.FontWeight.W_500),
                tool_type_group,
                ft.Container(height=10),
                parser_dropdown,
                ft.Container(height=10),
                color_field,
                ft.Container(height=5),
                ft.Text(
                    "Tool represents an identification method (library search or de novo sequencing)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    content="Cancel",
                    on_click=lambda e: self._close_dialog(dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Add"),
                    on_click=lambda e: self.page.run_task(save_tool, e)
                )
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """Close dialog."""
        dialog.open = False
        self.page.update()
