"""Dataclasses for external interface to project entities."""

from dataclasses import dataclass, field
import json
import pickle
import gzip
from typing import Any, Literal
import numpy as np
from numpy import ndarray

from dasmixer.api.project.array_utils import decompress_array

# Import for type hints only
try:
    from uniprot_meta_tool import UniprotData
except ImportError:
    UniprotData = None


@dataclass
class Subset:
    """Comparison group/subset."""
    
    id: int | None = None
    name: str = ""
    details: str | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'details': self.details,
            'display_color': self.display_color
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Subset':
        """Create from database row."""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            details=data.get('details'),
            display_color=data.get('display_color')
        )


@dataclass
class Tool:
    """Identification tool (library or de novo)."""
    
    id: int | None = None
    name: str = ""
    type: Literal['Library', 'De Novo'] = "Library"  # NEW: Type of tool
    parser: str = "library"  # RENAMED: Parser name (was 'type')
    settings: dict | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'parser': self.parser,
            'settings': json.dumps(self.settings) if self.settings else None,
            'display_color': self.display_color
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Tool':
        """Create from database row."""
        settings = data.get('settings')
        if settings and isinstance(settings, str):
            settings = json.loads(settings)
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            type=data.get('type', 'Library'),
            parser=data.get('parser', 'library'),
            settings=settings,
            display_color=data.get('display_color')
        )


@dataclass
class Sample:
    """Sample with associated spectra files."""
    
    id: int | None = None
    name: str = ""
    subset_id: int | None = None
    additions: dict | None = None  # albumin, total_protein, etc.
    outlier: bool = False  # True if sample is marked as outlier
    
    # Computed fields (not stored in DB, filled on load)
    subset_name: str | None = field(default=None, repr=False)
    spectra_files_count: int = field(default=0, repr=False)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'subset_id': self.subset_id,
            'additions': json.dumps(self.additions) if self.additions else None,
            'outlier': 1 if self.outlier else 0
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Sample':
        """Create from database row."""
        additions = data.get('additions')
        if additions and isinstance(additions, str):
            additions = json.loads(additions)
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            subset_id=data.get('subset_id'),
            additions=additions,
            outlier=bool(data.get('outlier', False)),
            subset_name=data.get('subset_name'),
            spectra_files_count=data.get('spectra_files_count', 0)
        )


@dataclass
class Protein:
    """Protein entry (Uniprot or custom)."""
    
    id: str = ""  # Uniprot ID or custom
    is_uniprot: bool = False
    fasta_name: str | None = None
    sequence: str | None = None
    gene: str | None = None
    name: str | None = None  # NEW: Short protein name
    uniprot_data: 'UniprotData | None' = field(default=None, repr=False)  # NEW: UniprotData object
    taxon_id: int | None = None            # NCBI Taxonomy ID
    organism_name: str | None = None       # Organism display name
    
    # Enrichment data (loaded optionally) - kept for future use
    protein_atlas_data: dict | None = field(default=None, repr=False)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'is_uniprot': self.is_uniprot,
            'fasta_name': self.fasta_name,
            'sequence': self.sequence,
            'gene': self.gene,
            'name': self.name,
            'taxon_id': self.taxon_id,
            'organism_name': self.organism_name
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Protein':
        """Create from database row."""
        return cls(
            id=data.get('id', ''),
            is_uniprot=bool(data.get('is_uniprot', False)),
            fasta_name=data.get('fasta_name'),
            sequence=data.get('sequence'),
            gene=data.get('gene'),
            name=data.get('name'),
            taxon_id=data.get('taxon_id'),
            organism_name=data.get('organism_name'),
            uniprot_data=None,  # Will be loaded separately if needed
            protein_atlas_data=None  # Not stored in main table
        )


@dataclass
class IdentificationWithSpectrum:
    """
    Combined identification + spectrum data used for batch ion-coverage calculation.

    Fields charge and peaks_count are loaded alongside spectrum arrays so that
    the coverage worker can use them without additional DB round-trips.
    """
    id: int
    spectre_id: int
    pepmass: float
    mz_array: ndarray
    intensity_array: ndarray
    tool_id: int
    sequence: str
    canonical_sequence: str
    charge: int | None = None
    peaks_count: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'IdentificationWithSpectrum':
        id_ = data.get('id')
        spectre_id = data.get('spectre_id')
        pepmass = data.get('pepmass')
        try:
            mz_array = decompress_array(data.get('mz_array'))
        except (ValueError, TypeError):
            mz_array = None
        try:
            intensity_array = decompress_array(data.get('intensity_array'))
        except (ValueError, TypeError):
            intensity_array = None
        tool_id = data.get('tool_id')
        sequence = data.get('sequence')
        canonical_sequence = data.get('canonical_sequence')
        charge = data.get('charge')
        peaks_count = data.get('peaks_count')
        return cls(
            id=id_,
            spectre_id=spectre_id,
            pepmass=pepmass,
            mz_array=mz_array,
            intensity_array=intensity_array,
            tool_id=tool_id,
            sequence=sequence,
            canonical_sequence=canonical_sequence,
            charge=int(charge) if charge is not None else None,
            peaks_count=int(peaks_count) if peaks_count is not None else None,
        )

    def to_worker_dict(self) -> dict[str, Any]:
        """
        Serialize to a plain dict suitable for multiprocessing (no numpy, no blobs).

        mz_array and intensity_array are converted to Python lists so they can
        be pickled across process boundaries without issues.
        """
        return {
            'id': self.id,
            'spectre_id': self.spectre_id,
            'pepmass': self.pepmass,
            'mz_array': self.mz_array.tolist() if self.mz_array is not None else [],
            'intensity_array': self.intensity_array.tolist() if self.intensity_array is not None else [],
            'tool_id': self.tool_id,
            'sequence': self.sequence,
            'canonical_sequence': self.canonical_sequence,
            'charge': self.charge,
            'peaks_count': self.peaks_count,
        }
