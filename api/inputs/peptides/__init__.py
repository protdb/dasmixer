"""Peptide identification parsers."""

from .base import IdentificationParser
from .table_importer import (
    TableImporter,
    SimpleTableImporter,
    LargeCSVImporter,
    ColumnRenames
)
from .PowerNovo2 import PowerNovo2Importer
from .MQ_Evidences import MaxQuantEvidenceParser
from ..registry import registry

# Register parsers
registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
registry.add_identification_parser("MaxQuant", MaxQuantEvidenceParser)

__all__ = [
    'IdentificationParser',
    'TableImporter',
    'SimpleTableImporter',
    'LargeCSVImporter',
    'ColumnRenames',
    'PowerNovo2Importer',
    'MaxQuantEvidenceParser'
]
