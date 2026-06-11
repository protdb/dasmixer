"""Reporting module."""

from .base import BaseReport
from .registry import registry

# Import all reports to trigger registration
from .reports import *

__all__ = [
    'BaseReport',
    'registry',
]
