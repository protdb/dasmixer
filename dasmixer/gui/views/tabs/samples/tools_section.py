"""Tools section - manage identification tools."""

import flet as ft
from dasmixer.api.project.project import Project
from .base_section import BaseSection
from .shared_state import SamplesTabState
from .dialogs.tool_dialog import ToolDialog


class ToolsSection(BaseSection):
    """Section for managing identification tools."""
    
    def __init__(self, project: Project, state: SamplesTabState, parent_tab):
        """Initialize tools section."""
        self.tools_list = ft.Column(spacing=5)
        super().__init__(project, state, parent_tab)
    
    def _build_content(self) -> ft.Control:
        """Build section content."""
        return ft.Column([
            ft.Text("Identification Tools", size=18, weight=ft.FontWeight.BOLD),
            self.tools_list,
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Add Tool"),
                icon=ft.Icons.ADD,
                on_click=lambda e: self.page.run_task(self._show_add_tool_dialog, e)
            )
        ], spacing=10)
    
    async def load_data(self):
        """Load tools list."""
        print("Loading tools...")
        tools = await self.project.get_tools()
        
        self.tools_list.controls.clear()
        
        for tool in tools:
            # Count identification files for this tool
            ident_files = await self.project.get_identification_files(tool_id=tool.id)
            
            self.tools_list.controls.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(ft.Icons.BIOTECH, color=tool.display_color or ft.Colors.SECONDARY),
                        width=40
                    ),
                    title=ft.Text(tool.name, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(
                        f"{len(ident_files)} identification file(s) • {tool.type} ({tool.parser})"
                    ),
                    trailing=ft.Row([
                        ft.ElevatedButton(
                            content=ft.Text("Import Identifications"),
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=lambda e, t=tool: self.parent_tab.show_import_identifications(t.id)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_color=ft.Colors.BLUE_400,
                            tooltip="Edit tool",
                            on_click=lambda e, t=tool: self.page.run_task(self._show_edit_tool_dialog, e, t)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            tooltip="Delete tool",
                            on_click=lambda e, t=tool: self.page.run_task(self._delete_tool, e, t)
                        )
                    ], tight=True, spacing=5),
                    data=tool.id
                )
            )
        
        if not tools:
            self.tools_list.controls.append(
                ft.Text("No tools. Click 'Add Tool' to create one.", italic=True)
            )
        
        print(f"Tools loaded: {len(tools)}")
        self.state.tools_count = len(tools)
        
        if self.tools_list.page:
            self.tools_list.update()
    
    async def _show_add_tool_dialog(self, e):
        """Show dialog for adding new tool."""
        dialog = ToolDialog(
            self.project,
            self.page,
            on_success_callback=self._on_tool_saved
        )
        await dialog.show()
    
    async def _show_edit_tool_dialog(self, e, tool):
        """Show dialog for editing tool."""
        dialog = ToolDialog(
            self.project,
            self.page,
            on_success_callback=self._on_tool_saved,
            tool=tool
        )
        await dialog.show()
    
    async def _on_tool_saved(self):
        """Callback after tool is saved."""
        await self.load_data()
        # Notify other sections to refresh
        self.state.needs_refresh_samples = True
    
    async def _delete_tool(self, e, tool):
        """Delete an identification tool with confirmation."""
        async def confirm_delete(e):
            try:
                await self.project.delete_tool(tool.id)
                
                # Close dialog
                confirm_dialog.open = False
                self.page.update()
                
                # Refresh
                await self.load_data()
                
                # Show success
                self.show_success(f"Deleted tool: {tool.name}")
                
            except ValueError as ex:
                # Handle case where tool has identifications
                confirm_dialog.open = False
                self.page.update()
                
                self.show_warning(f"Cannot delete: {str(ex)}")
            except Exception as ex:
                confirm_dialog.open = False
                self.page.update()
                
                self.show_error(f"Error: {str(ex)}")
        
        confirm_dialog = ft.AlertDialog(
            title=ft.Text("Delete Tool?"),
            content=ft.Text(
                f"Are you sure you want to delete tool '{tool.name}'?\n\n"
                "This action cannot be undone. The tool can only be deleted "
                "if no identifications are associated with it."
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: self._close_dialog(confirm_dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Delete"),
                    bgcolor=ft.Colors.RED_400,
                    color=ft.Colors.WHITE,
                    on_click=lambda e: self.page.run_task(confirm_delete, e)
                )
            ]
        )
        
        self.page.overlay.append(confirm_dialog)
        confirm_dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """Close dialog helper."""
        dialog.open = False
        self.page.update()
