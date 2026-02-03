"""Comparison groups management section."""

import flet as ft

from .base_section import BaseSection
from .dialogs.add_group_dialog import AddGroupDialog


class GroupsSection(BaseSection):
    """Comparison groups (subsets) management."""
    
    def _build_content(self) -> ft.Control:
        """Build groups section UI."""
        self.groups_list = ft.Column(spacing=5)
        
        self.add_group_btn = ft.ElevatedButton(
            content=ft.Text("Add Group"),
            icon=ft.Icons.ADD,
            on_click=lambda e: self.page.run_task(self.show_add_group_dialog, e)
        )
        
        return ft.Column([
            ft.Text("Comparison Groups", size=18, weight=ft.FontWeight.BOLD),
            self.groups_list,
            ft.Container(height=10),
            ft.Row([self.add_group_btn], spacing=10)
        ], spacing=10)
    
    async def load_data(self):
        """Load groups."""
        await self.refresh_groups()
    
    async def refresh_groups(self):
        """Refresh groups list."""
        print("Refreshing groups...")
        try:
            groups = await self.project.get_subsets()
            self.state.groups_list = groups
            
            self.groups_list.controls.clear()
            
            for group in groups:
                # Count samples in group
                samples = await self.project.get_samples(subset_id=group.id)
                
                self.groups_list.controls.append(
                    ft.ListTile(
                        leading=ft.Container(
                            content=ft.Icon(
                                ft.Icons.FOLDER,
                                color=group.display_color or ft.Colors.PRIMARY
                            ),
                            width=40
                        ),
                        title=ft.Text(group.name, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(
                            f"{len(samples)} samples" + 
                            (f" • {group.details}" if group.details else "")
                        ),
                        trailing=ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            tooltip="Delete group",
                            on_click=lambda e, g=group: self.page.run_task(
                                self.delete_group, e, g
                            )
                        ),
                        data=group.id
                    )
                )
            
            if not groups:
                self.groups_list.controls.append(
                    ft.Text(
                        "No groups. Click 'Add Group' to create one.",
                        italic=True
                    )
                )
            
            print(f"Groups loaded: {len(groups)}")
            self.groups_list.update()
            self.state.needs_groups_refresh = False
            
        except Exception as ex:
            print(f"Error refreshing groups: {ex}")
            self.show_error(f"Error loading groups: {str(ex)}")
    
    async def show_add_group_dialog(self, e):
        """Show add group dialog."""
        dialog = AddGroupDialog(self.page, self.project)
        
        async def on_success():
            await self.refresh_groups()
            # Mark samples dirty (need to update group dropdowns)
            self.state.mark_samples_dirty()
        
        await dialog.show(on_success=on_success)
    
    async def delete_group(self, e, group):
        """Delete a comparison group with confirmation."""
        async def confirm_delete(e):
            try:
                await self.project.delete_subset(group.id)
                
                # Close dialog
                confirm_dialog.open = False
                self.page.update()
                
                # Refresh groups
                await self.refresh_groups()
                
                # Mark samples dirty
                self.state.mark_samples_dirty()
                
                self.show_success(f"Deleted group: {group.name}")
                
            except ValueError as ex:
                confirm_dialog.open = False
                self.page.update()
                self.show_warning(f"Cannot delete: {str(ex)}")
                
            except Exception as ex:
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
                    content="Cancel",
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
