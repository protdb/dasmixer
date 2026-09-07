"""Orchestrates full MaxQuant project import into an existing (or new) DASMixer Project."""

import asyncio
import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Awaitable

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.spectra.mgf import MGFParser
from dasmixer.api.inputs.peptides.MQ_Evidences import MaxQuantEvidenceParser
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.config import config as app_config, get_maxquant_import_temp_dir
from dasmixer.utils import logger

from .mqpar_parser import MQParPaths, RawFile
from .apl_convert import load_and_merge, process_apl
from .progress import MaxQuantImportProgress


@dataclass
class MaxQuantImportOptions:
    """All parameters for one MaxQuant project import run."""
    mqpar_path: Path
    txt_path: Path                       # effective path to folder with msms.txt/msmsScans.txt
    raw_parent: Path                     # effective directory with RAW files (for finding .apl)
    fasta_path: Path | None = None       # None if FASTA is not imported
    import_fasta: bool = True            # checkbox "Import proteins from FASTA file"
    fasta_is_uniprot: bool = True        # checkbox "Sequences are in UniProt format"
    tool_name: str = "MaxQuant"
    subset_name: str = "MaxQuant Import"
    delete_temp_files: bool = True
    keep_contaminants: bool = False      # inverted from "Skip contaminant identifications" checkbox
    selected_raw_names: list[str] = field(default_factory=list)  # which RAW files to import
    on_duplicates: str = "skip"          # "skip" | "reload" | "add_as_new"
    temp_dir: Path | None = None         # None = auto (~/.cache/dasmixer/tmp/maxquant_import/<ts>/)


ProgressCallback = Callable[[MaxQuantImportProgress], Awaitable[None]]


def find_apl_files(raw_parent: Path, raw_names: set[str]) -> list[Path]:
    """
    Find .apl files for given raw_names under raw_parent/<name>/p0/.
    
    Ported from mq2dasmix/app.py:_find_apl_files, but accepts a SINGLE
    raw_parent (not a list) — see spec section 1 item 2.
    
    Returns list of Path objects (without size — size>0 filter kept internally).
    """
    result: list[Path] = []
    if not raw_parent.is_dir():
        return result
    for entry in sorted(raw_parent.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name not in raw_names:
            continue
        p0 = entry / 'p0'
        if not p0.is_dir():
            continue
        for apl in sorted(p0.glob('*.apl')):
            size = apl.stat().st_size
            if size > 0:
                result.append(apl)
    return result


async def run_maxquant_import(
    project: Project,
    options: MaxQuantImportOptions,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """
    Full MaxQuant import cycle. The open project is passed by the caller —
    this module does NOT create or close Project (unlike mq2dasmix/app.py).
    
    Steps:
    1. Load metadata (msms.txt + msmsScans.txt), find .apl files.
    2. Create temp directory.
    3. Convert each .apl → MGF + CSV via process_apl.
    4. Get-or-create subset and tool.
    5. Import FASTA proteins (optional).
    6. For each raw_name: get-or-create sample, import spectra + identifications.
    7. Save, cleanup temp files, return summary.
    
    Returns summary dict:
        {
          "samples_processed": int, "spectra_imported": int,
          "identifications_imported": int, "proteins_imported": int,
          "skipped_duplicates": int, "temp_dir": str | None,
        }
    
    Raises ValueError on critical errors (missing files, parser mismatch).
    """
    async def _progress(stage: str, message: str, current: int = 0, total: int = 0):
        if progress_callback:
            await progress_callback(MaxQuantImportProgress(
                stage=stage, message=message, current=current, total=total
            ))
            # Yield control back to the event loop so the UI update is
            # actually flushed before any subsequent blocking work starts.
            await asyncio.sleep(0)

    # --- Step 1: Load metadata ---
    await _progress("metadata", "Reading metadata...")
    
    msms_file = options.txt_path / 'msms.txt'
    msms_scans_file = options.txt_path / 'msmsScans.txt'
    for name, p in [('msms.txt', msms_file), ('msmsScans.txt', msms_scans_file)]:
        if not p.exists():
            raise ValueError(f"{name} not found in {options.txt_path}")
    
    merged, msms_df = await asyncio.to_thread(load_and_merge, options.txt_path)
    logger.info(f"Loaded merged: {len(merged)} rows, msms: {len(msms_df)} rows")
    
    selected_set = set(options.selected_raw_names)
    apl_files = find_apl_files(options.raw_parent, selected_set)
    logger.info(f"Found {len(apl_files)} .apl files")
    
    # --- Step 2: Create temp directory ---
    temp_dir = options.temp_dir or get_maxquant_import_temp_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Temp directory: {temp_dir}")

    # --- Step 3: Convert APL → MGF + CSV ---
    to_process = list(apl_files)
    total_apl = len(to_process)
    for i, apl in enumerate(to_process):
        await _progress("converting", f"Converting {apl.name}...", i, total_apl)
        try:
            written, total = await asyncio.to_thread(
                process_apl, apl, merged, msms_df, temp_dir,
                keep_contaminants=options.keep_contaminants,
            )
            logger.debug(f"  {apl.name}: {written}/{total} spectra written")
        except Exception as e:
            logger.warning(f"  Error converting {apl.name}: {e}")

    # Effective raw_names = those for which .mgf files were actually created
    processed_raw_names = sorted({
        f.name.split('.')[0]
        for f in temp_dir.glob('*.mgf')
    })
    logger.info(f"Processed raw names: {processed_raw_names}")

    # --- Step 4: Get-or-create subset ---
    await _progress("creating_tool_subset", "Setting up subset and tool...")
    
    subsets = await project.get_subsets()
    subset = next((s for s in subsets if s.name == options.subset_name), None)
    if not subset:
        subset = await project.add_subset(name=options.subset_name)
        logger.info(f"Created subset: {options.subset_name}")
    
    # --- Step 5: Get-or-create tool ---
    tools = await project.get_tools()
    tool = next((t for t in tools if t.name == options.tool_name), None)
    if tool is not None and tool.parser != "MaxQuant":
        raise ValueError(
            f"Tool '{options.tool_name}' already exists with parser '{tool.parser}' "
            f"(expected 'MaxQuant')"
        )
    if not tool:
        tool = await project.add_tool(
            name=options.tool_name,
            type="Library",
            parser="MaxQuant",
            settings={},
        )
        logger.info(f"Created tool: {options.tool_name}")

    # --- Step 6: Import proteins (optional) ---
    proteins_imported = 0
    if options.import_fasta and options.fasta_path and options.fasta_path.is_file():
        await _progress("proteins", "Importing proteins from FASTA...")
        parser = FastaParser(
            str(options.fasta_path),
            is_uniprot=options.fasta_is_uniprot,
        )
        async for batch_df in parser.parse_batch(batch_size=100):
            await project.add_proteins_batch(batch_df)
            proteins_imported += len(batch_df)
        logger.info(f"Imported {proteins_imported} proteins")

    # --- Step 7: Import spectra and identifications ---
    samples_processed = 0
    spectra_imported = 0
    identifications_imported = 0
    skipped_duplicates = 0

    total_raw = len(processed_raw_names)
    for i, raw_name in enumerate(processed_raw_names):
        await _progress("spectra", f"Processing {raw_name} ({i + 1}/{total_raw})", i, total_raw)

        mgf_files = sorted(temp_dir.glob(f'{raw_name}.*.mgf'))
        if not mgf_files:
            continue

        # Get or create sample
        sample = await project.get_sample_by_name(raw_name)
        if not sample:
            sample = await project.add_sample(name=raw_name, subset_id=subset.id)

        for mgf_path in mgf_files:
            csv_path = mgf_path.with_suffix('.csv')

            # --- Duplicate check for spectra file ---
            mgf_path_str = str(mgf_path)
            existing_sf = await project.get_spectra_file_by_path(mgf_path_str)
            if existing_sf is not None:
                if options.on_duplicates == "skip":
                    skipped_duplicates += 1
                    logger.info(f"Skipping duplicate spectra: {mgf_path}")
                    continue
                elif options.on_duplicates == "reload":
                    await project.delete_spectra_file(existing_sf['id'])
                # "add_as_new": fall through, create new record

            # Add spectra file record
            spectra_file_id = await project.add_spectra_file(
                sample_id=sample.id,
                format="MGF",
                path=mgf_path_str,
            )
            
            # Parse and import spectra
            mgf_parser = MGFParser(mgf_path_str)
            if not await mgf_parser.validate():
                logger.warning(f"MGF validation failed: {mgf_path}")
                continue

            batch_size = app_config.spectra_batch_size
            async for batch_df in mgf_parser.parse_batch(batch_size=batch_size):
                await project.add_spectra_batch(spectra_file_id, batch_df)
                spectra_imported += len(batch_df)

            # --- Import identifications from companion CSV ---
            if csv_path.exists():
                csv_path_str = str(csv_path)

                # Duplicate check for identification file
                existing_if = await project.get_identification_file_by_path(csv_path_str)
                if existing_if is not None:
                    if options.on_duplicates == "skip":
                        skipped_duplicates += 1
                        logger.info(f"Skipping duplicate identifications: {csv_path}")
                        continue
                    elif options.on_duplicates == "reload":
                        await project.delete_identification_file(existing_if['id'])
                    # "add_as_new": fall through

                ident_file_id = await project.add_identification_file(
                    spectra_file_id=spectra_file_id,
                    tool_id=tool.id,
                    file_path=csv_path_str,
                )

                ident_parser = MaxQuantEvidenceParser(csv_path_str)
                
                # Get spectra ID mapping: scans -> spectre_id
                id_list = await project.get_spectra_idlist(
                    spectra_file_id, by='scans'
                )
                # Convert [{scans:123, spectre_id:456}, ...] to DataFrame
                id_map = pd.DataFrame(id_list)

                ident_batch_size = app_config.identification_batch_size
                async for ident_df in ident_parser.parse_batch(batch_size=ident_batch_size):
                    # Merge on 'scans' to get spectre_id
                    merged_df = pd.merge(id_map, ident_df, on='scans')
                    merged_df['tool_id'] = tool.id
                    merged_df['ident_file_id'] = ident_file_id
                    merged_df['is_preferred'] = False
                    if len(merged_df) > 0:
                        await project.add_identifications_batch(merged_df)
                        identifications_imported += len(merged_df)

            logger.info(f"  {sample.name} <- {mgf_path.name}")
        
        samples_processed += 1

    # --- Step 8: Save ---
    await _progress("done", "Saving project...")
    await project.save(checkpoint=True)

    # --- Step 9: Cleanup temp files ---
    if options.delete_temp_files:
        import shutil
        for pat in ('*.mgf', '*.csv'):
            for f in temp_dir.glob(pat):
                f.unlink()
        # Remove temp_dir if empty
        try:
            shutil.rmtree(temp_dir)
            temp_dir_ret = None
        except OSError:
            temp_dir_ret = str(temp_dir)
    else:
        temp_dir_ret = str(temp_dir)

    # --- Step 10: Return summary ---
    summary = {
        "samples_processed": samples_processed,
        "spectra_imported": spectra_imported,
        "identifications_imported": identifications_imported,
        "proteins_imported": proteins_imported,
        "skipped_duplicates": skipped_duplicates,
        "temp_dir": temp_dir_ret,
    }
    
    await _progress("done", f"Import complete: {samples_processed} sample(s), "
                            f"{spectra_imported} spectra, "
                            f"{identifications_imported} identifications"
                            + (f", {proteins_imported} proteins" if proteins_imported else ""))
    
    return summary