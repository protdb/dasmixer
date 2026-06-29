"""Abstract base for report parameter forms (no flet dependency).

Core-side: handles values only (no flet builds).
GUI-side subclass adds build() and get_container().
"""

import json
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dasmixer.api.project.project import Project


class ReportParamBase:
    """Abstract base for a single report parameter widget.

    Core-side: stores label, default, and provides get/set value.
    GUI-side: subclass adds build() returning ft.Control.
    """

    def __init__(self, label: str | None = None, default=None):
        self.label = label
        self.default = default
        self._attr_name: str | None = None

    def get_value(self):
        """Return current value in native Python type."""
        return self.default

    def set_value(self, value) -> None:
        """Restore value from stored data."""
        self.default = value


class ReportFormMeta(type):
    """Metaclass: collects ReportParamBase fields declared in the class body.

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
    """Base class for typed report parameter forms.

    Core-side: handles values only (no flet builds).
    GUI-side subclass adds build() and get_container().

    Usage::

        class MyForm(ReportForm):
            tool = ToolSelector()
            threshold = FloatSelector(default=0.05)
            use_correction = BoolSelector(default=True)

    Instance usage::

        form = MyForm(project)
        values = form.get_values()        # dict for _generate_impl
    """

    _field_defs: dict[str, ReportParamBase]  # Populated by metaclass

    def __init__(self, project: "Project"):
        self.project = project

        # Create a fresh copy of each field descriptor per instance
        self._fields: dict[str, ReportParamBase] = {}
        for attr_name, field_def in self._field_defs.items():
            field_copy = copy.copy(field_def)
            field_copy._attr_name = attr_name
            if field_copy.label is None:
                field_copy.label = attr_name.replace('_', ' ').title()
            self._fields[attr_name] = field_copy

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
            for name, val in values.items():
                if name in instance._fields:
                    instance._fields[name].default = val
        except Exception:
            pass
        return instance
