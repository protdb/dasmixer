"""Reporting module."""

from .base import BaseReport
from .registry import registry

try:
    from .reports import *
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Report modules not loaded: {e}")

__all__ = [
    'BaseReport',
    'registry',
]
