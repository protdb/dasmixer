"""Export tab state — preserves UI values across tab destroy/recreate cycles."""

from dataclasses import dataclass, field


@dataclass
class ExportTabState:
    system_flags: dict[str, bool] = field(default_factory=lambda: {
        "samples": True,
        "subsets": True,
        "tools": True,
        "spectra_metadata": True,
        "identification_file": True,
        "spectre_file": True,
        "identification": True,
        "peptide_match": True,
        "protein_identifications": True,
        "protein_quantifications": True,
        "project_settings": True,
    })

    joined_flags: dict[str, bool] = field(default_factory=lambda: {
        "sample_details": True,
        "identifications": True,
        "protein_identifications": True,
        "protein_statistics": True,
    })
    joined_format: str = "xlsx"
    joined_one_per_sample: bool = False

    mgf_sample_ids: list[int] = field(default_factory=list)
    mgf_by: str = "all"
    mgf_tool_id: int | None = None
    mgf_write_offset: bool = False
    mgf_write_spectra: bool = False
    mgf_write_seq: bool = False
    mgf_seq_type: str = "canonical"
    mgf_compression: str = "none"

    mztab_sample_ids: list[int] = field(default_factory=list)
    mztab_lfq_method: str = "emPAI"
    mztab_title: str = ""
    mztab_description: str = ""