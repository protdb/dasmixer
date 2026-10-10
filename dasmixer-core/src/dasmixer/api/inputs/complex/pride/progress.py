"""Progress dataclass for PRIDE import — shared between GUI and CLI."""

from dataclasses import dataclass


@dataclass
class PrideImportProgress:
    """One progress message delivered via callback."""
    stage: str      # "downloading" | "spectra" | "identifications" | "fasta" | "done"
    message: str
    current: int = 0
    total: int = 0
