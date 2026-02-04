"""Main Project class for DASMixer - composed from mixins."""

from .core import ProjectLifecycle
from .mixins import (
    SubsetMixin,
    ToolMixin,
    SampleMixin,
    SpectraMixin,
    IdentificationMixin,
    PeptideMixin,
    ProteinMixin,
    PlotMixin,
    QueryMixin,
)


class Project(
    # Lifecycle and base functionality
    ProjectLifecycle,
    
    # Domain-specific mixins
    SubsetMixin,
    ToolMixin,
    SampleMixin,
    SpectraMixin,
    IdentificationMixin,
    PeptideMixin,
    ProteinMixin,
    
    # Utility mixins
    PlotMixin,
    QueryMixin,
):
    """
    Main class for managing DASMixer project data.
    
    Project is stored as a single SQLite database file.
    All methods are async to prevent UI blocking.
    
    This class is composed from multiple mixins, each handling a specific domain:
    - ProjectLifecycle: Database lifecycle (initialize, save, close)
    - SubsetMixin: Comparison groups management
    - ToolMixin: Identification tools management
    - SampleMixin: Sample management
    - SpectraMixin: Spectra files and spectra management
    - IdentificationMixin: Identification files and identifications management
    - PeptideMixin: Peptide matches and complex joined queries
    - ProteinMixin: Protein, identification results, and quantification management
    - PlotMixin: Data preparation for plotting
    - QueryMixin: Low-level SQL query interface
    
    Usage:
        # Create or open
        project = Project(path="my_project.dasmix", create_if_not_exists=True)
        await project.initialize()
        
        # Use as context manager
        async with Project(path="my_project.dasmix") as project:
            await project.add_sample(...)
    
    MRO (Method Resolution Order):
        The order of base classes is important for correct method resolution.
        ProjectLifecycle is first as it extends ProjectBase which provides
        fundamental database operations used by all mixins.
    """
    
    pass  # All functionality is provided by mixins
