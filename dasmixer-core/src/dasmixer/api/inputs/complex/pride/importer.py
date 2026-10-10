"""Orchestrates full PRIDE dataset import into an existing DASMixer Project."""

import asyncio
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from dasmixer.api.config import config as app_config
from dasmixer.api.config import get_pxd_temp_dir
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.inputs.registry import registry
from dasmixer.api.project.project import Project
from dasmixer.utils.logger import logger

from .dataset import PrideDataset, PrideFile
from .progress import PrideImportProgress


@dataclass
class PrideImportOptions:
    """All parameters for one PRIDE import run."""
    dataset_id: str
    subset_id: int
    spectra_parser: str = "MGF"        # registry name, e.g. "MGF"
    ident_parser: str = "mzTab"        # "mzTab" | "CasaNovo" (registry names)
    ident_mode: str = "single"         # "single" | "per_sample"
    tool_name: str = "PRIDE Import"
    selected_spectra_files: list[str] = field(default_factory=list)  # PrideFile.name values
    ident_file_mapping: dict[str, str] = field(default_factory=dict)  # {spectra_name: ident_name} for per_sample
    single_ident_file: str | None = None  # PrideFile.name for "single" mode
    import_fasta: bool = False
    collect_proteins: bool = False
    delete_temp_files: bool = True


ProgressCallback = Callable[[PrideImportProgress], Awaitable[None]]


def check_pride_available() -> bool:
    """Check whether PRIDE import is possible.

    Returns False if pridepy cannot be imported (not installed) or the
    PRIDE service is unreachable over the network.
    """
    try:
        import requests
        from pridepy.project.project import Project  # noqa: F401
    except ImportError:
        logger.warning("pridepy is not installed — PRIDE import unavailable")
        return False
    try:
        response = requests.get(
            "https://www.ebi.ac.uk/pride/ws/archive/v2/search/projects",
            params={"keyword": "PXD000001", "pageSize": 1},
            timeout=10,
        )
        return response.status_code == 200
    except requests.RequestException as e:
        logger.warning("PRIDE service unreachable: %s", e)
        return False


async def run_pride_import(
    project: Project,
    dataset: PrideDataset,
    options: PrideImportOptions,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Run a full PRIDE dataset import into an existing (open) Project.

    Steps:
    1. Download selected files (spectra, identifications, optional FASTA).
    2. Import spectra files — one Sample per spectra file.
    3. Import identifications ("single" mzTab multi-ms_run mode, or
       "per_sample" mode with one ident file per spectra file).
    4. Import FASTA proteins (optional).
    5. Save, cleanup temp files, return summary.

    Returns summary dict:
        {
          "samples_processed": int, "spectra_imported": int,
          "identifications_imported": int, "fasta_files_imported": int,
        }

    Raises ValueError on critical errors (missing ident file, parser mismatch,
    invalid ident file).
    """
    async def _progress(stage: str, message: str, current: int = 0, total: int = 0):
        if progress_callback:
            await progress_callback(PrideImportProgress(
                stage=stage, message=message, current=current, total=total
            ))
            # Yield control back to the event loop so the UI update is
            # actually flushed before any subsequent blocking work starts.
            await asyncio.sleep(0)

    if options.ident_mode not in ("single", "per_sample"):
        raise ValueError(f"Unknown ident_mode: {options.ident_mode!r}")

    # --- Step 1: Download files ---
    selected_spectra = [
        f for f in dataset.spectra_files if f.name in options.selected_spectra_files
    ]
    if options.ident_mode == "single":
        ident_files = [
            f for f in dataset.ident_files if f.name == options.single_ident_file
        ]
        if not ident_files:
            raise ValueError(
                f"Identification file '{options.single_ident_file}' not found in dataset "
                f"{options.dataset_id}"
            )
    else:
        wanted_idents = set(options.ident_file_mapping.values())
        ident_files = [f for f in dataset.ident_files if f.name in wanted_idents]

    fasta_files = dataset.fasta_files if options.import_fasta else []

    to_download: list[PrideFile] = []
    seen_names: set[str] = set()
    for pride_file in [*selected_spectra, *ident_files, *fasta_files]:
        if pride_file.name not in seen_names:
            seen_names.add(pride_file.name)
            to_download.append(pride_file)

    local_paths: dict[str, Path] = {}
    total_files = len(to_download)
    for i, pride_file in enumerate(to_download):
        await _progress("downloading", f"Downloading {pride_file.name}...", i, total_files)
        try:
            path = await asyncio.to_thread(pride_file.download_file)
            local_paths[pride_file.name] = path
            logger.debug("Downloaded %s -> %s", pride_file.name, path)
        except Exception as e:
            logger.warning("Failed to download %s: %s", pride_file.name, e)
        await asyncio.sleep(0.1)

    # --- Step 2: Import spectra ---
    samples_processed = 0
    spectra_imported = 0
    identifications_imported = 0
    fasta_files_imported = 0

    spectra_file_id_by_name: dict[str, int] = {}
    spec_parser_class = registry.get_parser(options.spectra_parser, "spectra")

    total_spectra_files = len(options.selected_spectra_files)
    for i, spectra_name in enumerate(options.selected_spectra_files):
        pride_file = next((f for f in selected_spectra if f.name == spectra_name), None)
        if pride_file is None or pride_file.name not in local_paths:
            logger.warning("Spectra file '%s' was not downloaded, skipping", spectra_name)
            continue

        await _progress("spectra", f"Importing spectra {pride_file.name} ({i + 1}/{total_spectra_files})...",
                        i, total_spectra_files)

        sample_name = Path(pride_file.name).stem
        sample = await project.get_sample_by_name(sample_name)
        if sample is None:
            sample = await project.add_sample(name=sample_name, subset_id=options.subset_id)
            logger.info("Created sample: %s", sample_name)

        path_str = str(local_paths[pride_file.name])
        spectra_file_id = await project.add_spectra_file(
            sample_id=sample.id,
            format=options.spectra_parser,
            path=path_str,
        )

        parser = spec_parser_class(path_str)
        if not await parser.validate():
            logger.warning("Spectra validation failed: %s", pride_file.name)
            continue

        async for batch in parser.parse_batch(batch_size=app_config.spectra_batch_size):
            await project.add_spectra_batch(spectra_file_id, batch)
            spectra_imported += len(batch)

        spectra_file_id_by_name[pride_file.name] = spectra_file_id
        samples_processed += 1
        logger.info("  %s <- %s", sample.name, pride_file.name)

    # --- Step 3: Import identifications ---
    await _progress("identifications", "Importing identifications...")

    # Get-or-create tool
    tool_type = "Library" if options.ident_parser == "mzTab" else "De Novo"
    tools = await project.get_tools()
    tool = next((t for t in tools if t.name == options.tool_name), None)
    if tool is not None and tool.parser != options.ident_parser:
        raise ValueError(
            f"Tool '{options.tool_name}' already exists with parser '{tool.parser}' "
            f"(expected '{options.ident_parser}')"
        )
    if tool is None:
        tool = await project.add_tool(
            name=options.tool_name,
            type=tool_type,
            parser=options.ident_parser,
            settings={},
        )
        logger.info("Created tool: %s", options.tool_name)

    ident_parser_class = registry.get_parser(options.ident_parser, "identification")

    # Determine the effective import approach.
    # In "single" mode with only one ms_run, fall back to per-sample
    # import (one ident file per spectra file) so that the MzTab parser's
    # _ignore_ms_run optimization binds all identifications to the given
    # spectra_file_id.
    use_multifile = options.ident_mode == "single"
    if use_multifile:
        _probe = ident_parser_class(
            str(local_paths[options.single_ident_file]),
            collect_proteins=False,
            is_uniprot_proteins=False,
        )
        if _probe.require_project:
            _probe.project = project
        _probe._read_mtd()
        if len(_probe.ms_run_locations) == 1:
            use_multifile = False

    if use_multifile:
        # Mirror import_identification_files_multifile: one mzTab with
        # several ms_run locations, one identification_file per ms_run.
        await _progress("identifications", f"Parsing {options.single_ident_file}...")

        path = local_paths[options.single_ident_file]
        parser = ident_parser_class(
            str(path),
            collect_proteins=options.collect_proteins,
            is_uniprot_proteins=False,
        )
        if parser.require_project:
            parser.project = project

        if not await parser.validate():
            raise ValueError(f"Invalid identification file: {options.single_ident_file}")

        ms_run_spectra: dict[int, int] = getattr(parser, "ms_run_spectra", {}) or {}
        if not ms_run_spectra:
            raise ValueError(
                f"No ms_run locations resolved to spectra files in {options.single_ident_file}"
            )

        targets: dict[int, tuple[int, int]] = {}
        for ms_run_idx, spectra_file_id in sorted(ms_run_spectra.items()):
            ident_file_id = await project.add_identification_file(
                spectra_file_id=int(spectra_file_id),
                tool_id=tool.id,
                file_path=str(path),
                selection_field="mz_run",
                selection_field_value=str(ms_run_idx),
            )
            targets[ms_run_idx] = (int(spectra_file_id), ident_file_id)

        mappings: dict[int, list[dict]] = {}
        for spectra_file_id, _ in targets.values():
            if spectra_file_id not in mappings:
                mappings[spectra_file_id] = await project.get_spectra_idlist(
                    spectra_file_id, by=parser.spectra_id_field
                )

        async for batch in parser.parse_batch(batch_size=app_config.identification_batch_size):
            for key, group in batch.groupby(["spectra_file_id", "ms_run_index"]):
                spectra_file_id, ms_run_idx = int(key[0]), int(key[1])
                if ms_run_idx not in targets:
                    continue
                mapping = mappings.get(spectra_file_id)
                if mapping is None:
                    continue
                merged = pd.merge(
                    group,
                    pd.json_normalize(mapping),
                    on=parser.spectra_id_field,
                    how="inner",
                )
                if len(merged) == 0:
                    continue
                merged["tool_id"] = tool.id
                merged["ident_file_id"] = targets[ms_run_idx][1]
                await project.add_identifications_batch(merged)
                identifications_imported += len(merged)

        if options.collect_proteins and parser.contain_proteins and parser.proteins:
            proteins_df = pd.DataFrame([p.to_dict() for p in parser.proteins.values()])
            proteins_df["is_uniprot"] = 0
            await project.add_proteins_batch(proteins_df)
            logger.info("Saved %d proteins from identification file", len(parser.proteins))

    else:
        # Per-sample import: one ident file per spectra file.
        # Used both for "per_sample" mode and for "single" mode when the
        # mzTab has only one ms_run (the _ignore_ms_run optimization in
        # MzTabImporter binds all rows to the given spectra_file_id).
        if options.ident_mode == "single":
            ident_mapping = {
                name: options.single_ident_file
                for name in spectra_file_id_by_name
            }
        else:
            ident_mapping = options.ident_file_mapping

        total_idents = len(ident_mapping)
        for i, (spectra_name, ident_name) in enumerate(ident_mapping.items()):
            await _progress(
                "identifications",
                f"Importing identifications for {spectra_name} ({i + 1}/{total_idents})...",
                i, total_idents,
            )

            spectra_file_id = spectra_file_id_by_name.get(spectra_name)
            if spectra_file_id is None:
                logger.warning(
                    "No spectra file for '%s' in project — import spectra first, skipping",
                    spectra_name,
                )
                continue
            ident_path = local_paths.get(ident_name)
            if ident_path is None:
                logger.warning("Identification file '%s' not downloaded, skipping", ident_name)
                continue

            ident_file_id = await project.add_identification_file(
                spectra_file_id=int(spectra_file_id),
                tool_id=tool.id,
                file_path=str(ident_path),
            )

            parser = ident_parser_class(
                str(ident_path),
                collect_proteins=options.collect_proteins,
                is_uniprot_proteins=False,
            )
            if parser.require_project:
                parser.project = project
                parser.spectra_file_id = spectra_file_id

            if not await parser.validate():
                logger.warning("Identification validation failed: %s", ident_name)
                continue

            spectra_list = await project.get_spectra_idlist(
                spectra_file_id, by=parser.spectra_id_field
            )
            logger.debug(
                "Matching identifications to spectra file id=%s by %s",
                spectra_file_id, parser.spectra_id_field,
            )

            async for batch in parser.parse_batch(
                batch_size=app_config.identification_batch_size
            ):
                if len(batch) == 0:
                    continue
                batch = pd.merge(
                    batch,
                    pd.json_normalize(spectra_list),
                    on=parser.spectra_id_field,
                    how="inner",
                )
                if len(batch) == 0:
                    continue
                batch["tool_id"] = tool.id
                batch["ident_file_id"] = ident_file_id
                await project.add_identifications_batch(batch)
                identifications_imported += len(batch)

            if options.collect_proteins and parser.contain_proteins and parser.proteins:
                proteins_df = pd.DataFrame([p.to_dict() for p in parser.proteins.values()])
                proteins_df["is_uniprot"] = 0
                await project.add_proteins_batch(proteins_df)
                logger.info("Saved %d proteins from identification file", len(parser.proteins))

    # --- Step 4: Import FASTA (optional) ---
    if options.import_fasta:
        total_fasta = len(fasta_files)
        for i, fasta_file in enumerate(fasta_files):
            await _progress("fasta", f"Importing FASTA {fasta_file.name} ({i + 1}/{total_fasta})...",
                            i, total_fasta)
            path = local_paths.get(fasta_file.name)
            if path is None:
                logger.warning("FASTA file '%s' not downloaded, skipping", fasta_file.name)
                continue
            parser = FastaParser(str(path))
            if not await parser.validate():
                logger.warning("FASTA validation failed: %s", fasta_file.name)
                continue
            async for batch in parser.parse_batch(batch_size=100):
                await project.add_proteins_batch(batch)
            fasta_files_imported += 1
            logger.info("Imported FASTA: %s", fasta_file.name)

    # --- Step 5: Save & cleanup ---
    await _progress("done", "Saving project...")
    await project.save(checkpoint=True)

    if options.delete_temp_files:
        shutil.rmtree(get_pxd_temp_dir() / options.dataset_id, ignore_errors=True)
        logger.debug("Removed temp files for %s", options.dataset_id)

    await _progress(
        "done",
        f"Import complete: {samples_processed} sample(s), "
        f"{spectra_imported} spectra, "
        f"{identifications_imported} identifications"
        + (f", {fasta_files_imported} FASTA file(s)" if fasta_files_imported else ""),
    )

    return {
        "samples_processed": samples_processed,
        "spectra_imported": spectra_imported,
        "identifications_imported": identifications_imported,
        "fasta_files_imported": fasta_files_imported,
    }
