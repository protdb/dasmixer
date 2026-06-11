"""Export joined (query-joined) data from project to CSV / XLSX."""

import os
from typing import Callable, Awaitable

import pandas as pd


def _sanitize(name: str) -> str:
    """Заменяем недопустимые символы в имени файла на '_'."""
    for ch in '/\\:*?"<>| ':
        name = name.replace(ch, "_")
    return name


async def _get_sample_details(project) -> pd.DataFrame:
    """Формирует DataFrame со статистикой по всем образцам."""
    stats_map = await project.get_all_cached_sample_stats()
    samples = await project.get_samples()
    rows = []
    for sample in samples:
        s = stats_map.get(sample.id, {})
        rows.append({
            "sample_id": sample.id,
            "name": sample.name,
            "subset_name": getattr(sample, "subset_name", ""),
            "outlier": sample.outlier,
            "spectra_files_count": s.get("spectra_files_count", 0),
            "ident_files_count": s.get("ident_files_count", 0),
            "identifications_count": s.get("identifications_count", 0),
            "preferred_count": s.get("preferred_count", 0),
            "coverage_known_count": s.get("coverage_known_count", 0),
            "protein_ids_count": s.get("protein_ids_count", 0),
        })
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(rows, columns=[  # type: ignore[arg-type]
        "sample_id", "name", "subset_name", "outlier",
        "spectra_files_count", "ident_files_count",
        "identifications_count", "preferred_count",
        "coverage_known_count", "protein_ids_count",
    ])


# Маппинг section-ключей → человекочитаемые имена листов/файлов
_SECTION_SHEET = {
    "sample_details": "SampleDetails",
    "identifications": "Identifications",
    "protein_identifications": "ProteinIdentifications",
    "protein_statistics": "ProteinStatistics",
}

_SECTION_FILE = {
    "sample_details": "sample_details",
    "identifications": "identifications",
    "protein_identifications": "protein_identifications",
    "protein_statistics": "protein_statistics",
}


async def _fetch_section(project, section: str) -> pd.DataFrame:
    """Получает DataFrame для указанной секции."""
    if section == "sample_details":
        return await _get_sample_details(project)
    elif section == "identifications":
        return await project.get_joined_peptide_data(limit=None)
    elif section == "protein_identifications":
        return await project.get_protein_results_joined(limit=-1)
    elif section == "protein_statistics":
        return await project.get_protein_statistics(limit=-1)
    return pd.DataFrame()


def _split_by_sample(df: pd.DataFrame, sample_ids: list[int]) -> dict[int, pd.DataFrame]:
    """Разбивает DataFrame по sample_id."""
    if "sample_id" not in df.columns:
        # Нет колонки — возвращаем один и тот же df для каждого образца
        return {sid: df for sid in sample_ids}
    result = {}
    for sid in sample_ids:
        result[sid] = df[df["sample_id"] == sid]
    return result


async def export_joined_data(
    project,
    flags: dict[str, bool],
    format_: str,
    one_per_sample: bool,
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]:
    """
    Экспортирует joined-данные в CSV или XLSX.

    Args:
        project: Project instance
        flags: {section_key: is_selected}
            Допустимые ключи: sample_details, identifications,
            protein_identifications, protein_statistics
        format_: "csv" | "xlsx"
        one_per_sample: Если True — identifications и protein_identifications
            разбиваются по образцам
        output_dir: Директория для CSV-файлов
        timestamp: YYYYMMDD_HHMMSS
        progress_callback: async callable(value: float, status: str)

    Returns:
        Список путей к созданным файлам (без дублей для XLSX)
    """
    sections = [k for k, v in flags.items() if v]
    if not sections:
        return []

    # Разделяемые по образцам секции
    _per_sample_sections = {"identifications", "protein_identifications"}

    # Получаем образцы заранее, если нужен one_per_sample
    samples_map: dict[int, str] = {}
    sample_ids: list[int] = []
    if one_per_sample and _per_sample_sections.intersection(sections):
        samples = await project.get_samples()
        sample_ids = [s.id for s in samples]
        samples_map = {s.id: s.name for s in samples}
    else:
        samples = await project.get_samples()
        samples_map = {s.id: s.name for s in samples}

    # Подсчёт задач для прогресса
    total_tasks = 0
    for section in sections:
        if one_per_sample and section in _per_sample_sections:
            total_tasks += max(len(sample_ids), 1)
        else:
            total_tasks += 1
    if total_tasks == 0:
        total_tasks = 1

    task_counter = 0
    created_files: list[str] = []
    xlsx_path = os.path.join(output_dir, f"dasmixer_export_{timestamp}.xlsx")
    xlsx_written = False  # флаг — добавлен ли xlsx в created_files

    # Для XLSX используем один ExcelWriter на весь экспорт
    # Но ExcelWriter — синхронный контекстный менеджер, открываем по необходимости
    # и переиспользуем через режим append.

    for section in sections:
        await progress_callback(
            task_counter / total_tasks,
            f"Loading {section}...",
        )

        df = await _fetch_section(project, section)

        if one_per_sample and section in _per_sample_sections:
            split = _split_by_sample(df, sample_ids)

            for sid in sample_ids:
                sub_df = split.get(sid, pd.DataFrame())
                s_name = _sanitize(samples_map.get(sid, str(sid)))

                if format_ == "xlsx":
                    sheet_name = f"{_SECTION_SHEET[section]}_{s_name}"
                    # Обрезаем имя листа до 31 символа (лимит Excel)
                    sheet_name = sheet_name[:31]
                    _write_xlsx_sheet(xlsx_path, sheet_name, sub_df)
                    if not xlsx_written:
                        created_files.append(xlsx_path)
                        xlsx_written = True
                else:
                    fname = f"{_SECTION_FILE[section]}_sample_{s_name}_{timestamp}.csv"
                    fpath = os.path.join(output_dir, fname)
                    sub_df.to_csv(fpath, index=False)
                    created_files.append(fpath)

                task_counter += 1
                await progress_callback(
                    task_counter / total_tasks,
                    f"Exported {section} for {s_name}",
                )
        else:
            if format_ == "xlsx":
                sheet_name = _SECTION_SHEET.get(section, section)[:31]
                _write_xlsx_sheet(xlsx_path, sheet_name, df)
                if not xlsx_written:
                    created_files.append(xlsx_path)
                    xlsx_written = True
            else:
                fname = f"{_SECTION_FILE.get(section, section)}_{timestamp}.csv"
                fpath = os.path.join(output_dir, fname)
                df.to_csv(fpath, index=False)
                created_files.append(fpath)

            task_counter += 1
            await progress_callback(
                task_counter / total_tasks,
                f"Exported {section}",
            )

    return created_files


def _write_xlsx_sheet(xlsx_path: str, sheet_name: str, df: pd.DataFrame) -> None:
    """
    Записывает DataFrame на лист Excel.
    Если файл уже существует — добавляет лист (режим append).
    """
    if os.path.exists(xlsx_path):
        with pd.ExcelWriter(  # type: ignore[call-overload]
            xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
