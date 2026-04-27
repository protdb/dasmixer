"""Export proteomics data to mzTab 1.0 format using mztabwriter."""

from typing import Awaitable, Callable

import pandas as pd
from mztabwriter import CvParam, MzTabDocument


UNLABELED_REAGENT = CvParam("MS", "MS:1002038", "unlabeled sample")
DASMIXER_SOFTWARE = CvParam("MS", "MS:1001207", "DASMixer")
DASMIXER_SCORE = CvParam("MS", "MS:1001171", "DASMixer:intensity_coverage")


async def export_mztab(
    project,
    sample_ids: list[int],
    lfq_method: str,                # "emPAI" | "iBAQ" | "NSAF" | "Top3"
    title: str | None,
    description: str | None,
    output_path: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> str:
    """
    Экспортирует данные проекта в mzTab-формат.

    Args:
        project: Project instance
        sample_ids: Список ID образцов для экспорта
        lfq_method: Метод LFQ ("emPAI" | "iBAQ" | "NSAF" | "Top3")
        title: Заголовок документа (или None → "DASMixer Export")
        description: Описание документа (или None → "")
        output_path: Полный путь к выходному файлу .mzTab
        progress_callback: async callable(value: float, status: str)

    Returns:
        Путь к созданному файлу
    """
    await progress_callback(0.0, "Building metadata...")

    # --- Загрузка образцов и сабсетов ---
    all_samples = await project.get_samples()
    samples = [s for s in all_samples if s.id in sample_ids]
    samples_map = {s.id: s for s in samples}   # sample_id -> Sample

    subsets = await project.get_subsets()

    # --- Создание документа ---
    doc = MzTabDocument(
        mode="Complete",
        type_="Quantification",
        title=title or "DASMixer Export",
        description=description or "",
    )

    doc.add_software(DASMIXER_SOFTWARE)
    doc.set_quantification_method(UNLABELED_REAGENT)
    doc.set_protein_quantification_unit(
        CvParam("PRIDE", "PRIDE:0000393", "Relative quantification unit"),
    )
    doc.add_protein_search_engine_score(DASMIXER_SCORE)
    doc.add_psm_search_engine_score(DASMIXER_SCORE)

    await progress_callback(0.10, "Setting up ms_run / assay / study_variable...")

    # sample_id  -> Assay object
    sample_assay_map: dict[int, object] = {}
    # spectre_file.id -> MsRun object
    ms_run_index: dict[int, object] = {}
    # subset_id -> list[Assay]
    subset_assays: dict[int, list] = {}

    for sample in samples:
        sf_rows = await project.execute_query_df(
            "SELECT id, path FROM spectre_file WHERE sample_id = ?",
            [sample.id],
        )

        ms_runs = []
        if sf_rows is not None and not sf_rows.empty:
            for _, row in sf_rows.iterrows():
                path_val = row.get("path")
                location = f"file://{path_val}" if path_val else "file:///no_data"
                ms_run = doc.add_ms_run(location)
                ms_run_index[int(row["id"])] = ms_run
                ms_runs.append(ms_run)

        if ms_runs:
            assay = doc.add_assay(ms_runs[0], UNLABELED_REAGENT)
        else:
            # Образец без spectre_file — фиктивный ms_run
            dummy_run = doc.add_ms_run("file:///no_data")
            assay = doc.add_assay(dummy_run, UNLABELED_REAGENT)

        sample_assay_map[sample.id] = assay
        subset_assays.setdefault(sample.subset_id, []).append(assay)

    # study_variable — по одному на subset (только те, где есть хоть один assay)
    sv_map: dict[int, object] = {}   # subset_id -> StudyVariable
    for subset in subsets:
        assays_in_subset = subset_assays.get(subset.id, [])
        if assays_in_subset:
            sv = doc.add_study_variable(subset.name, assays_in_subset)
            sv_map[subset.id] = sv

    await progress_callback(0.30, "Loading protein data...")

    # --- PRT секция ---
    # Загружаем ВСЕ строки (limit=-1)
    proteins_df = await project.get_protein_results_joined(limit=-1)

    if proteins_df is not None and not proteins_df.empty:
        # Фильтруем по выбранным образцам.
        # После drop() колонки sample_id нет — get_protein_results_joined её удаляет.
        # Нужно пересобрать через другой запрос или использовать protein_identification_result.
        # Поэтому используем прямой запрос для фильтрации.
        proteins_df = await project.execute_query_df(
            """
            SELECT
                pir.protein_id,
                pir.sample_id,
                pir.peptide_count,
                pir.coverage,
                pir.intensity_sum,
                p.gene,
                p.name AS protein_name
            FROM protein_identification_result pir
            LEFT JOIN protein p ON pir.protein_id = p.id
            WHERE pir.sample_id IN ({})
            ORDER BY pir.protein_id
            """.format(",".join("?" for _ in sample_ids)),
            sample_ids,
        )

    await progress_callback(0.45, "Building protein rows...")

    # Ключи для search_engine_scores и num_psms — ms_run[N] для каждого ms_run
    all_ms_run_keys = {
        f"ms_run[{ms_r.index}]": None  # type: ignore[union-attr]
        for ms_r in ms_run_index.values()
    }

    if proteins_df is not None and not proteins_df.empty:
        for protein_id, group in proteins_df.groupby("protein_id"):
            first_row = group.iloc[0]

            # LFQ данные по образцам
            quant_df = await project.get_protein_quantification_data(
                method=lfq_method,
                protein_id=str(protein_id),
            )
            if quant_df is None:
                quant_df = pd.DataFrame()

            # Фильтруем только выбранные образцы
            if not quant_df.empty and "sample_id" in quant_df.columns:
                quant_df = quant_df[quant_df["sample_id"].isin(sample_ids)]

            # protein_abundance_assay: {assay[N]: rel_value}
            protein_abundance_assay: dict[str, float | None] = {}
            for _, qrow in quant_df.iterrows():
                sid = qrow.get("sample_id")
                if sid is not None and sid in sample_assay_map:
                    assay = sample_assay_map[sid]
                    key = f"assay[{assay.index}]"  # type: ignore[union-attr]
                    protein_abundance_assay[key] = qrow.get("rel_value")

            # protein_abundance_study_variable: среднее по образцам subset
            abundance_sv: dict[str, float | None] = {}
            stdev_sv: dict[str, float | None] = {}
            stderr_sv: dict[str, float | None] = {}

            if not quant_df.empty and "sample_id" in quant_df.columns:
                # Добавляем subset_id через samples_map
                quant_df = quant_df.copy()
                subset_id_lookup: dict[int, int] = {
                    sid: s.subset_id for sid, s in samples_map.items()
                }
                quant_df["_subset_id"] = (  # type: ignore[call-overload]
                    quant_df["sample_id"].map(subset_id_lookup)  # type: ignore[arg-type]
                )
                for subset_id, grp in quant_df.dropna(  # type: ignore[call-overload]
                    subset=["_subset_id"]
                ).groupby("_subset_id"):
                    sid_int = int(subset_id)  # type: ignore[arg-type]
                    if sid_int not in sv_map:
                        continue
                    sv = sv_map[sid_int]
                    sv_key = f"study_variable[{sv.index}]"  # type: ignore[union-attr]
                    values = grp["rel_value"].dropna()
                    if len(values) == 0:
                        continue
                    mean_val = float(values.mean())
                    std_val = float(values.std()) if len(values) > 1 else 0.0
                    stderr_val = std_val / (len(values) ** 0.5) if len(values) > 1 else std_val
                    abundance_sv[sv_key] = mean_val
                    stdev_sv[sv_key] = std_val
                    stderr_sv[sv_key] = stderr_val

            # num_peptides_distinct: per ms_run — заполняем из group по sample_id
            num_distinct: dict[str, int | None] = dict(all_ms_run_keys)  # type: ignore[arg-type]
            for sid_in_group, subgroup in group.groupby("sample_id"):
                if int(sid_in_group) not in samples_map:
                    continue
                # Получаем spectre_file.id для этого образца
                sf_rows_q = await project.execute_query_df(
                    "SELECT id FROM spectre_file WHERE sample_id = ?",
                    [int(sid_in_group)],
                )
                if sf_rows_q is None or sf_rows_q.empty:
                    continue
                for _, sf_row in sf_rows_q.iterrows():
                    sf_id = int(sf_row["id"])
                    if sf_id in ms_run_index:
                        ms_r = ms_run_index[sf_id]
                        pc = int(subgroup["peptide_count"].sum()) if "peptide_count" in subgroup.columns else 0
                        num_distinct[f"ms_run[{ms_r.index}]"] = pc  # type: ignore[union-attr]

            best_score = None
            if "intensity_sum" in group.columns:
                max_val = group["intensity_sum"].max()
                if pd.notna(max_val):
                    best_score = float(max_val)

            doc.add_protein(
                accession=str(protein_id),
                description=first_row.get("protein_name") or None,
                database="FASTA",
                search_engine=DASMIXER_SOFTWARE,
                best_search_engine_score=best_score,
                search_engine_scores=dict(all_ms_run_keys),
                num_psms=dict(all_ms_run_keys),  # type: ignore[arg-type]
                num_peptides_distinct=num_distinct,  # type: ignore[arg-type]
                protein_coverage=first_row.get("coverage") or None,
                protein_abundance_assay=protein_abundance_assay or None,
                protein_abundance_study_variable=abundance_sv or None,
                protein_abundance_stdev_study_variable=stdev_sv or None,
                protein_abundance_std_error_study_variable=stderr_sv or None,
            )

    await progress_callback(0.75, "Building PSM rows...")

    # --- PSM секция ---
    psm_id_counter = 1
    for sample_id in sample_ids:
        psm_df = await project.get_joined_peptide_data(
            sample_id=sample_id,
            is_preferred=True,
            limit=None,
        )
        if psm_df is None or psm_df.empty:
            continue

        # Определяем spectre_file.id для этого образца
        sf_rows_s = await project.execute_query_df(
            "SELECT id FROM spectre_file WHERE sample_id = ?",
            [sample_id],
        )
        sf_ids_for_sample: set[int] = set()
        if sf_rows_s is not None and not sf_rows_s.empty:
            sf_ids_for_sample = set(sf_rows_s["id"].tolist())

        # ms_run объекты для этого образца
        ms_runs_for_sample = {
            sf_id: ms_r
            for sf_id, ms_r in ms_run_index.items()
            if sf_id in sf_ids_for_sample
        }

        for _, row in psm_df.iterrows():
            # spectre_file_id должен быть в psm_df; если его нет — spectra_ref=None
            spectre_file_id = row.get("spectre_file_id")
            if spectre_file_id is not None:
                ms_r = ms_runs_for_sample.get(int(spectre_file_id))
            else:
                ms_r = None

            if ms_r is not None:
                seq_no = row.get("seq_no")
                spectra_ref = (
                    f"ms_run[{ms_r.index}]:index={int(seq_no)}"  # type: ignore[union-attr]
                    if seq_no is not None
                    else None
                )
            else:
                spectra_ref = None

            charge_val = row.get("override_charge") or row.get("charge")
            pepmass = row.get("pepmass")

            doc.add_psm(
                sequence=row.get("canonical_sequence") or row.get("sequence") or "",
                psm_id=psm_id_counter,
                accession=row.get("protein_id") or "unknown",
                unique=1 if row.get("unique_evidence") else 0,
                database="FASTA",
                search_engine=DASMIXER_SOFTWARE,
                search_engine_score=row.get("score") or None,
                spectra_ref=spectra_ref,
                charge=int(charge_val) if charge_val is not None else None,
                exp_mass_to_charge=float(pepmass) if pepmass is not None else None,
                pre=None,
                post=None,
                start=None,
                end=None,
            )
            psm_id_counter += 1

    await progress_callback(0.95, "Writing file...")

    doc.to_file(output_path)

    await progress_callback(1.0, "Export complete")
    return output_path
