"""ReportForm: typed parameter forms for reports."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from dasmixer.api.project.project import Project


# ---------------------------------------------------------------------------
# Base parameter class
# ---------------------------------------------------------------------------

class ReportParamBase:
    """Abstract base for a single report parameter widget."""

    def __init__(self, label: str | None = None, default=None):
        self.label = label      # If None — set by metaclass from attr name
        self.default = default
        self._attr_name: str | None = None   # Set by ReportFormMeta
        self._control: ft.Control | None = None  # Created in build()

    async def build(self, project: "Project") -> ft.Control:
        """Build flet control. Must be called once before get_value/set_value."""
        raise NotImplementedError

    def get_value(self):
        """Return current value in native Python type."""
        raise NotImplementedError

    def set_value(self, value) -> None:
        """Restore value from stored data."""
        raise NotImplementedError


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

    def get_value(self) -> str | None:
        return self._control.value if self._control else self.default

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = value
        else:
            self.default = value


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

    def get_value(self) -> str | None:
        return self._control.value if self._control else self.default

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = value
        else:
            self.default = value


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

    def get_value(self) -> bool:
        return bool(self._control.value) if self._control else bool(self.default)

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = bool(value)
        else:
            self.default = bool(value)


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

    def get_value(self) -> float:
        try:
            return float(self._control.value) if self._control else float(self.default)
        except (ValueError, TypeError):
            return float(self.default)

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = str(value)
        else:
            self.default = value


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

    def get_value(self) -> int:
        try:
            return int(self._control.value) if self._control else int(self.default)
        except (ValueError, TypeError):
            return int(self.default)

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = str(value)
        else:
            self.default = value


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

    def get_value(self) -> str | None:
        return self._control.value if self._control else self.default

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = value
        else:
            self.default = value


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

    def get_value(self) -> str:
        return self._control.value if self._control else str(self.default)

    def set_value(self, value) -> None:
        if self._control:
            self._control.value = str(value)
        else:
            self.default = value


# ---------------------------------------------------------------------------
# Metaclass and ReportForm
# ---------------------------------------------------------------------------

class ReportFormMeta(type):
    """
    Metaclass: collects ReportParamBase fields declared in the class body.

    Each field instance is shared across all instances of the form class,
    so the form must create *copies* of the field descriptors per instance.
    The metaclass only records the field definitions; actual copies are made
    in ReportForm.__init__.
    """

    def __new__(mcs, name, bases, namespace):
        field_defs: dict[str, ReportParamBase] = {}
        for key, val in list(namespace.items()):
            if isinstance(val, ReportParamBase):
                field_defs[key] = val
        namespace['_field_defs'] = field_defs
        return super().__new__(mcs, name, bases, namespace)


class ReportForm(metaclass=ReportFormMeta):
    """
    Base class for typed report parameter forms.

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

    _field_defs: dict[str, ReportParamBase]  # Populated by metaclass

    def __init__(self, project: "Project"):
        self.project = project
        self._built = False

        # Create a fresh copy of each field descriptor per instance
        import copy
        self._fields: dict[str, ReportParamBase] = {}
        for attr_name, field_def in self._field_defs.items():
            field_copy = copy.copy(field_def)
            field_copy._attr_name = attr_name
            if field_copy.label is None:
                field_copy.label = attr_name.replace('_', ' ').title()
            # Copy nested mutable defaults
            if isinstance(field_copy, MultiSubsetSelector):
                field_copy._checkboxes = {}
                field_copy.default = list(field_def.default) if field_def.default else []
            field_copy._control = None
            self._fields[attr_name] = field_copy

    async def build(self) -> None:
        """Build all controls (must be called before get_container)."""
        for field in self._fields.values():
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
            content=ft.Column(rows, spacing=12),
            padding=ft.padding.all(10),
        )

    def get_values(self) -> dict:
        """Return dict of current values keyed by field name."""
        return {name: field.get_value() for name, field in self._fields.items()}

    def set_values(self, values: dict) -> None:
        """Restore values from stored dict."""
        for name, val in values.items():
            if name in self._fields:
                self._fields[name].set_value(val)

    def to_json(self) -> str:
        """Serialize current values to JSON string."""
        return json.dumps(self.get_values())

    @classmethod
    def from_json_str(cls, json_str: str, project: "Project") -> "ReportForm":
        """Create instance and pre-populate values from stored JSON (before build)."""
        instance = cls(project)
        try:
            values = json.loads(json_str)
            # Pre-set defaults so they appear when build() is called
            for name, val in values.items():
                if name in instance._fields:
                    instance._fields[name].default = val
                    if isinstance(instance._fields[name], MultiSubsetSelector):
                        instance._fields[name].default = val if isinstance(val, list) else []
        except Exception:
            pass
        return instance
