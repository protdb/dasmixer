"""ReportForm: typed parameter forms for reports (GUI-side).

Extends core-side abstract classes with flet-specific build() and get_container().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from dasmixer.api.reporting.report_form import (
    ReportParamBase as _CoreReportParamBase,
    ReportFormMeta as _CoreReportFormMeta,
    ReportForm as _CoreReportForm,
)

if TYPE_CHECKING:
    from dasmixer.api.project.project import Project


# ---------------------------------------------------------------------------
# Base parameter class (GUI extension)
# ---------------------------------------------------------------------------

class ReportParamBase(_CoreReportParamBase):
    """Abstract base for a single report parameter widget (GUI-side).

    Adds _control field and build() method returning ft.Control.
    """

    def __init__(self, label: str | None = None, default=None):
        super().__init__(label=label, default=default)
        self._control: ft.Control | None = None  # Created in build()

    async def build(self, project: "Project") -> ft.Control:
        """Build flet control. Must be called once before get_value/set_value."""
        raise NotImplementedError

    def get_value(self):
        """Return current value in native Python type."""
        return self._control.value if self._control else self.default

    def set_value(self, value) -> None:
        """Restore value from stored data."""
        if self._control:
            self._control.value = value
        else:
            self.default = value


# ---------------------------------------------------------------------------
# Concrete parameter classes
# ---------------------------------------------------------------------------

class ToolSelector(ReportParamBase):
    """Dropdown for selecting a tool by name."""

    def __init__(self, label: str | None = None, default: str | None = None):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        tools = await project.get_tools()
        options = [ft.DropdownOption(key=t.name, text=t.name) for t in tools]
        initial = self.default
        if initial is None and options:
            initial = options[0].key
        self._control = ft.Dropdown(
            label=self.label,
            options=options,
            value=initial,
            expand=True,
        )
        return self._control


class EnumSelector(ReportParamBase):
    """Dropdown for selecting one value from a fixed list."""

    def __init__(self, values: list[str], label: str | None = None, default: str | None = None):
        super().__init__(label=label, default=default)
        self.values = values

    async def build(self, project: "Project") -> ft.Control:
        options = [ft.DropdownOption(key=v, text=v) for v in self.values]
        initial = self.default if self.default is not None and self.default in self.values else (
            self.values[0] if self.values else None
        )
        self._control = ft.Dropdown(
            label=self.label,
            options=options,
            value=initial,
            expand=True,
        )
        return self._control


class BoolSelector(ReportParamBase):
    """Checkbox for a boolean parameter."""

    def __init__(self, label: str | None = None, default: bool = False):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        self._control = ft.Checkbox(
            label=self.label,
            value=bool(self.default),
        )
        return self._control


class FloatSelector(ReportParamBase):
    """Text field for a float parameter."""

    def __init__(self, label: str | None = None, default: float = 0.0):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        self._control = ft.TextField(
            label=self.label,
            value=str(self.default),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        return self._control


class IntSelector(ReportParamBase):
    """Text field for an integer parameter."""

    def __init__(self, label: str | None = None, default: int = 0):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        self._control = ft.TextField(
            label=self.label,
            value=str(self.default),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        return self._control


class SubsetSelector(ReportParamBase):
    """Dropdown for selecting one comparison group."""

    def __init__(self, label: str | None = None, default: str | None = None):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        subsets = await project.get_subsets()
        options = [ft.DropdownOption(key=s.name, text=s.name) for s in subsets]
        initial = self.default
        if initial is None and options:
            initial = options[0].key
        self._control = ft.Dropdown(
            label=self.label,
            options=options,
            value=initial,
            expand=True,
        )
        return self._control


class MultiSubsetSelector(ReportParamBase):
    """
    A checkbox per comparison group.

    get_value() returns list[str] of selected subset names.
    set_value() accepts list[str].
    """

    def __init__(self, label: str | None = None, default: list[str] | None = None):
        super().__init__(label=label, default=default or [])
        self._checkboxes: dict[str, ft.Checkbox] = {}

    async def build(self, project: "Project") -> ft.Control:
        subsets = await project.get_subsets()
        self._checkboxes = {}
        checkboxes = []
        default_set = set(self.default) if self.default else set()
        for s in subsets:
            cb = ft.Checkbox(
                label=s.name,
                value=(s.name in default_set) if default_set else True,
            )
            self._checkboxes[s.name] = cb
            checkboxes.append(cb)
        self._control = ft.Column(checkboxes, spacing=4)
        return self._control

    def get_value(self) -> list[str]:
        return [name for name, cb in self._checkboxes.items() if cb.value]

    def set_value(self, value) -> None:
        if isinstance(value, list):
            value_set = set(value)
            if self._checkboxes:
                for name, cb in self._checkboxes.items():
                    cb.value = name in value_set
            else:
                self.default = value


class StringSelector(ReportParamBase):
    """Single-line text field."""

    def __init__(self, label: str | None = None, default: str = ""):
        super().__init__(label=label, default=default)

    async def build(self, project: "Project") -> ft.Control:
        self._control = ft.TextField(
            label=self.label,
            value=str(self.default),
            expand=True,
        )
        return self._control


# ---------------------------------------------------------------------------
# ReportForm (GUI extension)
# ---------------------------------------------------------------------------

class ReportForm(_CoreReportForm):
    """
    Base class for typed report parameter forms (GUI-side).

    Extends core ReportForm with build() and get_container().

    Usage::

        class MyForm(ReportForm):
            tool = ToolSelector()
            threshold = FloatSelector(default=0.05)
            use_correction = BoolSelector(default=True)

    Instance usage::

        form = MyForm(project)
        await form.build()
        container = form.get_container()  # put in UI
        values = form.get_values()        # dict for _generate_impl
    """

    def __init__(self, project: "Project"):
        super().__init__(project)
        self._built = False

        # Copy nested mutable defaults for GUI-specific fields
        for attr_name, field in self._fields.items():
            if isinstance(field, MultiSubsetSelector):
                field._checkboxes = {}
                field._control = None

    async def build(self) -> None:
        """Build all controls (must be called before get_container)."""
        for field in self._fields.values():
            if hasattr(field, 'build'):
                field._control = await field.build(self.project)
        self._built = True

    def get_container(self) -> ft.Container:
        """Return ft.Container with all controls laid out vertically."""
        if not self._built:
            raise RuntimeError("Call build() before get_container()")
        rows = []
        for field in self._fields.values():
            rows.append(field._control)
        return ft.Container(
            content=ft.Column(rows),
            padding=ft.padding.all(10),
        )