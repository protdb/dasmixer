"""Dialog for configuring project merge/import options."""

import asyncio
import flet as ft


class MergeOptionsDialog(ft.AlertDialog):
    """
    Modal dialog for configuring merge/import options.
    
    Presents radio groups for tool matching, subset merging, sample merging,
    and project settings, plus a text field for conflict suffix.
    
    Usage:
        dialog = MergeOptionsDialog()
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
        result = await dialog.wait_for_result()
        # result is dict or None if cancelled
    """
    
    def __init__(self):
        self._event = asyncio.Event()
        self._result = None
        
        # Tool match radio group
        self.tool_match_group = ft.RadioGroup(
            content=ft.Column([
                ft.Text("Tools:", weight=ft.FontWeight.BOLD, size=16),
                ft.Radio(value="by_parser", label="By parser (match tools with same parser)"),
                ft.Radio(value="by_name", label="By name"),
                ft.Radio(value="add_all", label="Do not merge (add all as new)"),
            ]),
            value="by_parser",
        )
        
        # Subset match radio group
        self.subset_match_group = ft.RadioGroup(
            content=ft.Column([
                ft.Text("Subsets:", weight=ft.FontWeight.BOLD, size=16),
                ft.Radio(value="yes", label="Merge subsets by name"),
                ft.Radio(value="no", label="Add all as new"),
            ]),
            value="yes",
        )
        
        # Sample match radio group
        self.sample_match_group = ft.RadioGroup(
            content=ft.Column([
                ft.Text("Samples:", weight=ft.FontWeight.BOLD, size=16),
                ft.Radio(value="yes", label="Merge samples by name"),
                ft.Radio(value="no", label="Add all as new"),
            ]),
            value="yes",
        )
        
        # Project settings radio group
        self.settings_match_group = ft.RadioGroup(
            content=ft.Column([
                ft.Text("Project Settings:", weight=ft.FontWeight.BOLD, size=16),
                ft.Radio(value="no", label="Keep current settings"),
                ft.Radio(value="yes", label="Update from imported project"),
            ]),
            value="no",
        )
        
        # Conflict suffix text field
        self.suffix_field = ft.TextField(
            value="_1",
            label="Suffix for conflicting names",
            width=200,
        )
        
        super().__init__(
            modal=True,
            title=ft.Text("Merge Project Options", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    self.tool_match_group,
                    ft.Divider(height=10),
                    self.subset_match_group,
                    ft.Divider(height=10),
                    self.sample_match_group,
                    ft.Divider(height=10),
                    self.settings_match_group,
                    ft.Divider(height=10),
                    self.suffix_field,
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=500,
                padding=10,
            ),
            actions=[
                ft.ElevatedButton(
                    content=ft.Text("Cancel"),
                    on_click=self._on_cancel,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Merge"),
                    on_click=self._on_merge,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _on_cancel(self, e=None):
        """Handle Cancel button click."""
        self._result = None
        self.open = False
        self._event.set()
        try:
            self.update()
        except Exception:
            pass
    
    def _on_merge(self, e=None):
        """Handle Merge button click."""
        tool_value = self.tool_match_group.value
        if tool_value == "add_all":
            tool_match = None
        elif tool_value == "by_name":
            tool_match = "name"
        else:  # by_parser
            tool_match = "parser"
        
        self._result = {
            "tool_match": tool_match,
            "subset_match": self.subset_match_group.value == "yes",
            "sample_match": self.sample_match_group.value == "yes",
            "project_settings_match": self.settings_match_group.value == "yes",
            "conflict_suffix": self.suffix_field.value or "_1",
        }
        self.open = False
        self._event.set()
        try:
            self.update()
        except Exception:
            pass
    
    async def wait_for_result(self) -> dict | None:
        """
        Wait for user to click Cancel or Merge.
        
        Returns:
            dict with merge options, or None if cancelled.
        """
        await self._event.wait()
        return self._result
