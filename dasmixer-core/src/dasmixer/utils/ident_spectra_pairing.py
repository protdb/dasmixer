"""Pairing helpers between identification files and spectra files.

Contains the positional pairing utility for single-sample imports and the
ms_run location normalization/resolution helpers used by the mzTab parser.
"""

from pathlib import Path

import pandas as pd


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


def normalize_spectra_location(location: str) -> str:
    """Normalize a spectra file location/path to a comparable lowercase stem.

    Removes a leading ``file://`` scheme, converts backslashes to forward
    slashes, and returns the lowercase file stem (basename without extension).

    Args:
        location: Raw location string (e.g. from ``ms_run[N]-location``).

    Returns:
        Lowercase stem of the basename, e.g. ``"file:///C:/data/run1.mgf"``
        and ``"run1"`` both normalize to ``"run1"``.
    """
    s = location.strip()
    if s.lower().startswith("file://"):
        s = s[7:]
    s = s.replace("\\", "/")
    return Path(s).stem.lower()


def resolve_spectra_file_by_location(
    location: str, spectra_files: pd.DataFrame
) -> int | None:
    """Resolve a location string to a spectra_file id (case-insensitive stem match).

    Args:
        location: Raw location string to resolve.
        spectra_files: DataFrame of spectra files; must contain ``id`` and
            ``path`` columns.

    Returns:
        The ``id`` (as int) of the first spectra_file whose normalized path
        stem equals the normalized location, or ``None`` if no match.
    """
    target = normalize_spectra_location(location)
    for _, row in spectra_files.iterrows():
        row_path = str(row["path"]).replace("\\", "/")
        if Path(row_path).stem.lower() == target:
            return int(row["id"])
    return None
