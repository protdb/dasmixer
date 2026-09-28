"""Common progress types shared between GUI and CLI for MaxQuant import."""

from dataclasses import dataclass


@dataclass
class MaxQuantImportProgress:
    """One progress message, delivered via callback."""
    stage: str      # "metadata" | "converting" | "creating_tool_subset" | "spectra" | "identifications" | "proteins" | "done"
    message: str    # human-readable text, e.g. "Converting CRC_Replic_P03.HCD.FTMS.peak.apl..."
    current: int = 0
    total: int = 0
