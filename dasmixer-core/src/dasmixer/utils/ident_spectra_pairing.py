"""Positional pairing of identification files to spectre_file entries by filename."""

from pathlib import Path


def resolve_ident_to_spectra_mapping(
    ident_paths: list[str],
    spectra_files: list[dict],  # [{"id": int, "path": str}, ...] — spectre_file of ONE sample
) -> tuple[dict[str, int], list[str]]:
    """
    Sort identification_paths and spectra_files by basename(path), pair positionally
    (i-th identification file -> i-th spectre_file). Extra identification files (when
    there are more of them than spectre_file entries) are returned as unmatched.

    Returns:
        (mapping {ident_path: spectra_file_id}, unmatched_ident_paths)
    """
    ident_sorted = sorted(ident_paths, key=lambda p: Path(p).name)
    spectra_sorted = sorted(spectra_files, key=lambda s: Path(s["path"]).name)

    mapping: dict[str, int] = {}
    unmatched: list[str] = []
    for i, ident_path in enumerate(ident_sorted):
        if i < len(spectra_sorted):
            mapping[ident_path] = int(spectra_sorted[i]["id"])
        else:
            unmatched.append(ident_path)
    return mapping, unmatched