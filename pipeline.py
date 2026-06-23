#!/usr/bin/env python3
"""
Non-interactive DASMixer pipeline.

Strictly automated: project → subset → sample → MGF → PowerNovo2 idents → FASTA
→ ion coverage → preferred → protein mapping → protein identifications → LFQ.
"""

import asyncio
from pathlib import Path

import pandas as pd

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.spectra.mgf import MGFParser
from dasmixer.api.inputs.peptides.PowerNovo2 import PowerNovo2Importer
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identificatons_batch,
)
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.calculations.proteins.map_identifications import (
    find_protein_identifications,
)
from dasmixer.api.calculations.proteins.lfq import calculate_lfq

# ---------------------------------------------------------------------------
# Константы настроек (как в GUI по умолчанию)
# ---------------------------------------------------------------------------
TOOL_NAME = "PowerNovo2"
TOOL_TYPE = "De Novo"
TOOL_PARSER = "PowerNovo2"
SUBSET_NAME = "Default"
SAMPLE_NAME = "Sample"
BATCH_SIZE = 5000
FASTA_BATCH_SIZE = 1000

ION_PARAMS = {"ions": ["b", "y"], "tolerance": 20.0, "mode": "largest"}
FRAGMENT_CHARGES = [1, 2]
SEQFIXER_PARAMS = {
    "target_ppm": 50.0,
    "min_charge": 1,
    "max_charge": 4,
    "max_isotope_offset": 2,
    "force_isotope_offset": True,
}
TOOL_MAP_SETTINGS = {
    "min_protein_identity": 0.9,
    "max_ppm": 50.0,
    "ptm_list": None,
    "max_ptm": 5,
    "leucine_combinatorics": True,
    "denovo_correction": True,
    "denovo_correction_ppm": 50000.0,
    "match_correction_criteria": ["intensity_coverage"],
    "save_aa_substitutions": False,
    "min_score": 0.0,
    "min_ion_intensity_coverage": 0.0,
    "min_peptide_length": 7,
    "max_peptide_length": 30,
    "ignore_criteria": False,
}
PREFERRED_THRESHOLDS = {
    "min_score": 0.5,
    "max_abs_ppm": 20.0,
    "intensity_coverage": 10.0,
    "spectre_peaks_count": 5,
    "ions_matched": 3,
    "top_peaks_covered": 2,
    "canonical_length": (7, 30),
}
PROTEIN_IDENT_THRESHOLDS = {"min_peptides": 1, "min_uq_evidence": 1}
LFQ_METHODS = ["emPAI", "iBAQ"]


async def run_pipeline(
    mgf_path: str | Path,
    ident_csv_path: str | Path,
    fasta_path: str | Path,
    project_path: str | Path,
) -> None:
    """
    Выполнить полный пайплайн обработки одного образца.

    Parameters
    ----------
    mgf_path : str | Path
        Путь к MGF-файлу со спектрами.
    ident_csv_path : str | Path
        Путь к CSV-файлу с идентификациями PowerNovo2.
    fasta_path : str | Path
        Путь к FASTA-файлу (is_uniprot=True).
    project_path : str | Path
        Путь для сохранения проекта (.dasmix).
    """
    mgf_path = Path(mgf_path)
    ident_csv_path = Path(ident_csv_path)
    fasta_path = Path(fasta_path)
    project_path = Path(project_path)

    # -----------------------------------------------------------------------
    # 1. Создать / открыть проект
    # -----------------------------------------------------------------------
    async with Project(path=str(project_path), create_if_not_exists=True) as project:

        # -------------------------------------------------------------------
        # 2. Добавить subset
        # -------------------------------------------------------------------
        subset = await project.add_subset(name=SUBSET_NAME, details="Auto-generated subset")

        # -------------------------------------------------------------------
        # 3. Добавить sample
        # -------------------------------------------------------------------
        sample = await project.add_sample(name=SAMPLE_NAME, subset_id=subset.id)

        # -------------------------------------------------------------------
        # 4. Инструмент
        # -------------------------------------------------------------------
        tool = await project.add_tool(
            name=TOOL_NAME,
            type=TOOL_TYPE,
            parser=TOOL_PARSER,
            settings={"max_ppm": 20},
        )

        # -------------------------------------------------------------------
        # 5. Импорт MGF
        # -------------------------------------------------------------------
        spectra_file_id = await project.add_spectra_file(
            sample_id=sample.id,
            format="MGF",
            path=str(mgf_path),
        )
        parser = MGFParser(str(mgf_path))
        if not await parser.validate():
            raise ValueError(f"MGF validation failed: {mgf_path}")
        async for batch_df in parser.parse_batch(batch_size=BATCH_SIZE):
            await project.add_spectra_batch(spectra_file_id, batch_df)
        print(f"[OK] Spectra imported: {mgf_path}")

        # -------------------------------------------------------------------
        # 6. Импорт идентификаций PowerNovo2
        # -------------------------------------------------------------------
        id_list = await project.get_spectra_idlist(spectra_file_id, by="seq_no")
        id_map = pd.DataFrame(id_list)  # columns: seq_no, spectre_id

        ident_file_id = await project.add_identification_file(
            spectra_file_id=spectra_file_id,
            tool_id=tool.id,
            file_path=str(ident_csv_path),
        )
        ident_parser = PowerNovo2Importer(str(ident_csv_path))
        async for ident_df in ident_parser.parse_batch(batch_size=BATCH_SIZE):
            merged = pd.merge(id_map, ident_df, on="seq_no")
            merged["tool_id"] = tool.id
            merged["ident_file_id"] = ident_file_id
            merged["is_preferred"] = False
            await project.add_identifications_batch(merged)
        print(f"[OK] Identifications imported: {ident_csv_path}")

        # -------------------------------------------------------------------
        # 7. Импорт FASTA
        # -------------------------------------------------------------------
        fasta_parser = FastaParser(str(fasta_path), is_uniprot=True)
        if not await fasta_parser.validate():
            raise ValueError(f"FASTA validation failed: {fasta_path}")
        async for batch_df in fasta_parser.parse_batch(batch_size=FASTA_BATCH_SIZE):
            await project.add_proteins_batch(batch_df)
        print(f"[OK] Proteins imported: {fasta_path}")

        # -------------------------------------------------------------------
        # 8. Расчёт ion coverage (по одному тулу)
        # -------------------------------------------------------------------
        processed = 0
        while True:
            batch = await project.get_identifications_with_spectra_batch(
                tool_id=tool.id,
                offset=0,
                limit=BATCH_SIZE,
                only_missing=True,
            )
            if not batch:
                break
            worker_dicts = [item.to_worker_dict() for item in batch]
            results = process_identificatons_batch(
                batch=worker_dicts,
                params_dict=ION_PARAMS,
                fragment_charges=FRAGMENT_CHARGES,
                target_ppm=SEQFIXER_PARAMS["target_ppm"],
            )
            await project.put_identification_data_batch(results)
            processed += len(batch)
        await project.save()
        print(f"[OK] Ion coverage calculated ({processed} identifications)")

        # -------------------------------------------------------------------
        # 9. Выбор preferred identifications
        # -------------------------------------------------------------------
        candidates = await project.get_idents_for_preferred(
            spectra_file_id=spectra_file_id,
            tool_id=tool.id,
            **PREFERRED_THRESHOLDS,
        )
        if not candidates.empty:
            best_per_spectrum = candidates.loc[
                candidates.groupby("spectre_id")["score"].idxmax()
            ]
            preferred_ids = best_per_spectrum["id"].tolist()
            await project.set_preferred_identifications_for_file(
                spectra_file_id, preferred_ids
            )
        print(f"[OK] Preferred identifications set")

        # -------------------------------------------------------------------
        # 10. Protein mapping (BLAST)
        # -------------------------------------------------------------------
        async for matches_df, count, _tid in map_proteins(
            project=project,
            tool_settings={tool.id: TOOL_MAP_SETTINGS},
            ion_params=ION_PARAMS,
            fragment_charges=FRAGMENT_CHARGES,
            seqfixer_params=SEQFIXER_PARAMS,
            batch_size=5000,
        ):
            if not matches_df.empty:
                await project.add_peptide_matches_batch(matches_df)
        await project.save()
        print(f"[OK] Protein mapping completed")

        # -------------------------------------------------------------------
        # 11. Определение белков (protein identifications)
        # -------------------------------------------------------------------
        await project.clear_protein_identifications()
        joined_data = await project.get_joined_peptide_data(
            is_preferred=True,
            protein_identified=True,
        )
        if not joined_data.empty:
            sequences_db = await project.get_protein_db_to_search(null_sequence=True)
            async for result_df, _s_id in find_protein_identifications(
                joined_data=joined_data,
                sequences_db=sequences_db,
                **PROTEIN_IDENT_THRESHOLDS,
            ):
                if not result_df.empty:
                    await project.add_protein_identifications_batch(result_df)
        print(f"[OK] Protein identifications determined")

        # -------------------------------------------------------------------
        # 12. Расчёт LFQ (emPAI / iBAQ)
        # -------------------------------------------------------------------
        lfq_df = await calculate_lfq(
            project=project,
            sample_id=sample.id,
            methods=LFQ_METHODS,
        )
        if not lfq_df.empty:
            await project.add_protein_quantifications_batch(lfq_df)
        print(f"[OK] LFQ calculated")

        # -------------------------------------------------------------------
        # 13. Export joined data to CSV
        # -------------------------------------------------------------------
        project_dir = project_path.parent

        joined_csv = project_dir / f"{project_path.stem}_joined_data.csv"
        joined_data = await project.get_joined_peptide_data()
        if not joined_data.empty:
            joined_data.to_csv(joined_csv, index=False)
            print(f"[OK] Joined peptide data exported: {joined_csv}")

        protein_csv = project_dir / f"{project_path.stem}_protein_results.csv"
        protein_results = await project.get_protein_results_joined(limit=-1)
        if not protein_results.empty:
            protein_results.to_csv(protein_csv, index=False)
            print(f"[OK] Protein results exported: {protein_csv}")

        # -------------------------------------------------------------------
        # 14. Final save
        # -------------------------------------------------------------------
        await project.save(checkpoint=True)
        print(f"\n[DONE] Pipeline complete. Project saved to {project_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        print(
            "Usage: python pipeline.py <mgf_path> <ident_csv_path> <fasta_path> <project_path>"
        )
        sys.exit(1)

    asyncio.run(
        run_pipeline(
            mgf_path=sys.argv[1],
            ident_csv_path=sys.argv[2],
            fasta_path=sys.argv[3],
            project_path=sys.argv[4],
        )
    )
