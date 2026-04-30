"""Groups section - manage comparison groups."""

import asyncio
import flet as ft
from dasmixer.api.project.project import Project
from .base_section import BaseSection
from .shared_state import SamplesTabState
from dasmixer.utils import logger
from .dialogs.group_dialog import GroupDialog


class GroupsSection(BaseSection):
    """Section for managing comparison groups."""
    
    def __init__(self, project: Project, state: SamplesTabState, parent_tab):
        """Initialize groups section."""
        self.groups_list = ft.Column(spacing=5)
        super().__init__(project, state, parent_tab)
    
    def _build_content(self) -> ft.Control:
        """Build section content."""
        return ft.Column([
            ft.Text("Comparison Groups", size=18, weight=ft.FontWeight.BOLD),
            self.groups_list,
            ft.Container(height=10),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Text("Add Group"),
                    icon=ft.Icons.ADD,
                    on_click=lambda e: self.page.run_task(self._show_add_group_dialog, e)
                )
            ], spacing=10)
        ], spacing=10)
    
    async def load_data(self):
        """Load groups list using a single batch query for sample counts."""
        logger.debug("Loading groups...")
        # Single query for groups + single query for counts — no per-group queries
        groups, counts_by_subset = await asyncio.gather(
            self.project.get_subsets(),
            self.project.get_sample_counts_by_subset(),
        )

        self.groups_list.controls.clear()

        for group in groups:
            count = counts_by_subset.get(group.id, 0)
            self.groups_list.controls.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(ft.Icons.FOLDER, color=group.display_color or ft.Colors.PRIMARY),
                        width=40,
                    ),
                    title=ft.Text(group.name, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(
                        f"{count} samples" + (f" • {group.details}" if group.details else "")
                    ),
                    trailing=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_color=ft.Colors.BLUE_400,
                                tooltip="Edit group",
                                on_click=lambda e, g=group: self.page.run_task(self._show_edit_group_dialog, e, g),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                tooltip="Delete group",
                                on_click=lambda e, g=group: self.page.run_task(self._delete_group, e, g),
                            ),
                        ],
                        tight=True,
                        spacing=0,
                    ),
                    data=group.id,
                )
            )

        if not groups:
            self.groups_list.controls.append(
                ft.Text("No groups. Click 'Add Group' to create one.", italic=True)
            )

        logger.debug(f"Groups loaded: {len(groups)}")
        self.state.groups_count = len(groups)

        if self.groups_list.page:
            self.groups_list.update()
    
    async def _show_add_group_dialog(self, e):
        """Show dialog for adding new group."""
        dialog = GroupDialog(
            self.project,
            self.page,
            on_success_callback=self._on_group_saved
        )
        await dialog.show()
    
    async def _show_edit_group_dialog(self, e, group):
        """Show dialog for editing group."""
        dialog = GroupDialog(
            self.project,
            self.page,
            on_success_callback=self._on_group_saved,
            group=group
        )
        await dialog.show()
    
    async def _on_group_saved(self):
        """Callback after group is saved."""
        await self.load_data()
        # Notify other sections to refresh
        self.state.needs_refresh_samples = True
    
    async def _delete_group(self, e, group):
        """Delete a comparison group with confirmation."""
        async def confirm_delete(e):
            try:
                await self.project.delete_subset(group.id)
                
                # Close dialog
                confirm_dialog.open = False
                self.page.update()
                
                # Refresh
                await self.load_data()
                self.state.needs_refresh_samples = True
                
                # Show success
                self.show_success(f"Deleted group: {group.name}")
                
            except ValueError as ex:
                # Handle case where group has samples
                confirm_dialog.open = False
                self.page.update()
                
                self.show_warning(f"Cannot delete: {str(ex)}")
            except Exception as ex:
                logger.exception(ex)
                confirm_dialog.open = False
                self.page.update()
                
                self.show_error(f"Error: {str(ex)}")
        
        confirm_dialog = ft.AlertDialog(
            title=ft.Text("Delete Group?"),
            content=ft.Text(
                f"Are you sure you want to delete group '{group.name}'?\n\n"
                "This action cannot be undone. The group can only be deleted "
                "if no samples are assigned to it."
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
