"""Export tab container with four export sections."""

import flet as ft

from dasmixer.api.export.shared_state import ExportTabState
from dasmixer.api.project.project import Project


class ExportTab(ft.Column):

    _state: ExportTabState | None = None

    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO

        if ExportTab._state is None:
            ExportTab._state = ExportTabState()
        state = ExportTab._state

        self.sections = self._create_sections(state)
        self.controls = self._build_controls()

    def _create_sections(self, state: ExportTabState) -> dict:
        from dasmixer.gui.views.tabs.export.system_section import SystemDataSection
        from dasmixer.gui.views.tabs.export.joined_section import JoinedDataSection
        from dasmixer.gui.views.tabs.export.mgf_section import MgfExportSection
        from dasmixer.gui.views.tabs.export.mztab_section import MzTabExportSection

        return {
            "system": SystemDataSection(self.project, state, self),
            "joined": JoinedDataSection(self.project, state, self),
            "mgf": MgfExportSection(self.project, state, self),
            "mztab": MzTabExportSection(self.project, state, self),
        }

    def _build_controls(self) -> list:
        result = []
        section_order = ["system", "joined", "mgf", "mztab"]
        for i, key in enumerate(section_order):
            result.append(
                ft.Container(
                    content=self.sections[key],
                    padding=ft.padding.all(4),
                )
            )
            if i < len(section_order) - 1:
                result.append(ft.Divider())
        return result
