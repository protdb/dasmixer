"""Export proteins and query sequences to FASTA files for the protein match v2 pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dasmixer.api.calculations.peptides.types import SearchSequence
from dasmixer.api.config import config
from dasmixer.utils.exceptions import DasmixerException
from dasmixer.utils.logger import logger


def make_work_dir(project_path: Path | None) -> Path:
    """Create and return a fresh timestamped work directory for one run.

    The directory is laid out as
    ``config.get_tempdir('root') / 'peptide_match' / {project_stem} / {YYYYmmdd_HHMMSS}``
    and is created (with parents) on demand. ``project_stem`` is taken from
    ``project_path.stem`` (or ``'unnamed'`` when ``project_path`` is ``None``).
    """
    stem = project_path.stem if project_path is not None else "unnamed"
    base = config.get_tempdir("root") / "peptide_match" / stem / datetime.now().strftime("%Y%m%d_%H%M%S")
    base.mkdir(parents=True, exist_ok=True)
    logger.debug("Created peptide match work directory: %s", base)
    return base


def write_proteins_fasta(
    proteins: dict[str, str],
    path: Path,
    il_combinatorics: bool = False,
) -> None:
    """Stream ``proteins`` to ``path`` in FASTA format.

    Entries whose sequence is ``None`` are skipped. Every protein ID is
    validated: it must not be empty and must not contain spaces, tabs,
    newlines or ``>`` (those would break FASTA parsing). When
    ``il_combinatorics`` is ``True`` each written sequence has all ``I``
    replaced by ``L``.
    """
    written = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for pid, sequence in proteins.items():
            if sequence is None:
                continue
            if not pid or any(ch in pid for ch in (" ", "\t", "\n", ">")):
                raise DasmixerException(f"Invalid protein ID for FASTA export: {pid!r}")
            if il_combinatorics:
                sequence = sequence.replace("I", "L")
            f.write(f">{pid}\n{sequence}\n")
            written += 1
    logger.debug("Wrote %d protein entries to %s", written, path)


def write_queries_fasta(seqs: list[SearchSequence], path: Path) -> None:
    """Stream ``seqs`` to ``path`` as a query FASTA for npysearch.

    Each entry is written as ``>{index}\\n{search_sequence}\\n`` where
    ``index`` is the decimal integer :attr:`SearchSequence.index`.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(f">{seq.index}\n{seq.search_sequence}\n" for seq in seqs)
    logger.debug("Wrote %d query sequences to %s", len(seqs), path)
