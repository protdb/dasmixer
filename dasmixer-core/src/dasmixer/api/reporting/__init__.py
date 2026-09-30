"""Reporting module — base classes and registry.

Built-in report implementations are auto-registered via
``import dasmixer.reports`` (triggered by GUI and CLI entry points).
"""

from .base import BaseReport
from .registry import registry

__all__ = [
    'BaseReport',
    'registry',
]
