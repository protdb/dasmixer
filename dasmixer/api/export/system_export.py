"""Export system (raw database) tables to CSV using aiocsv for streaming I/O."""

import json
import os
from typing import Callable, Awaitable

import aiocsv
import aiofiles


# SQL queries per flag — BLOB columns excluded explicitly
TABLE_QUERIES: dict[str, str] = {
    "Samples": "SELECT * FROM sample",
    "Subsets": "SELECT * FROM subset",
    "Tools": "SELECT * FROM tool",
    # mz_array / intensity_array / charge_array excluded; all_params kept for JSON expand
    "Spectra metadata": (
        "SELECT id, spectre_file_id, seq_no, title, scans, charge, rt, pepmass, "
        "intensity, peaks_count, charge_array_common_value, all_params FROM spectre"
    ),
    "Identification file": "SELECT * FROM identification_file",
    "Spectre file": "SELECT * FROM spectre_file",
    "Identification": "SELECT * FROM identification",
    "Peptide match": "SELECT * FROM peptide_match",
    "Protein identifications": "SELECT * FROM protein_identification_result",
    "Protein quantifications": "SELECT * FROM protein_quantification_result",
    "Project settings": "SELECT * FROM project_settings",
}

# Columns that contain raw binary BLOBs — must never appear in output
BLOB_COLUMNS: set[str] = {
    "mz_array",
    "intensity_array",
    "charge_array",
    "uniprot_data",
    "plots",
    "tables",
}

# Columns whose values are JSON objects (dicts) — expanded with prefix "{col}."
JSON_COLUMNS: set[str] = {
    "settings",
    "additions",
    "all_params",
    "positional_scores",
}

_BATCH_SIZE = 1000


def _expand_json_row(row_dict: dict) -> dict:
    """
    Для каждой JSON-колонки в строке:
      - если значение — строка и парсится как dict → разворачиваем в плоские ключи "{col}.{key}"
      - иначе оставляем как есть (строка, None, список)
    Возвращает новый dict с удалёнными исходными JSON-колонками и добавленными плоскими.
    """
    result = {}
    expansions: dict[str, dict] = {}

    for key, value in row_dict.items():
        if key in JSON_COLUMNS and value is not None:
            parsed = None
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif isinstance(value, dict):
                parsed = value

            if isinstance(parsed, dict):
                expansions[key] = parsed
                # исходную колонку не включаем
                continue

        result[key] = value

    # Добавляем развёрнутые поля
    for col, d in expansions.items():
        for k, v in d.items():
            # Вложенные объекты сериализуем обратно в JSON-строку
            if isinstance(v, (dict, list)):
                result[f"{col}.{k}"] = json.dumps(v)
            else:
                result[f"{col}.{k}"] = v

    return result


async def _export_table(
    project,
    table_name: str,
    file_path: str,
    query: str,
    batch_size: int = _BATCH_SIZE,
) -> None:
    """
    Экспортирует таблицу в CSV через aiocsv, батчами.
    JSON-колонки разворачиваются в плоские ключи.
    BLOB-колонки исключаются.
    """
    cursor = await project._execute(query)

    # Имена колонок из cursor.description
    raw_columns = [desc[0] for desc in cursor.description]
    # Убираем BLOB-поля сразу
    base_columns = [c for c in raw_columns if c not in BLOB_COLUMNS]
    col_indices = {col: idx for idx, col in enumerate(raw_columns)}

    # Первый батч нужен чтобы определить финальные заголовки (с учётом JSON expand)
    first_batch = await cursor.fetchmany(batch_size)

    # Строим итоговые заголовки: сначала разворачиваем первый батч
    fieldnames: list[str] | None = None
    expanded_first: list[dict] = []

    for raw_row in first_batch:
        row_dict = {col: raw_row[col_indices[col]] for col in base_columns}
        expanded = _expand_json_row(row_dict)
        expanded_first.append(expanded)
        if fieldnames is None:
            fieldnames = list(expanded.keys())

    if fieldnames is None:
        # Таблица пустая — определяем заголовки из схемы без разворачивания
        fieldnames = base_columns

    async with aiofiles.open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = aiocsv.AsyncDictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        await writer.writeheader()

        # Записываем первый батч
        for row in expanded_first:
            await writer.writerow(row)

        # Читаем и записываем остальные батчи
        while True:
            batch = await cursor.fetchmany(batch_size)
            if not batch:
                break
            for raw_row in batch:
                row_dict = {col: raw_row[col_indices[col]] for col in base_columns}
                expanded = _expand_json_row(row_dict)
                await writer.writerow(expanded)

    await cursor.close()


def _table_filename(table_name: str, timestamp: str) -> str:
    """Формирует имя файла: {table_name_lower_underscored}_{timestamp}.csv"""
    safe_name = table_name.lower().replace(" ", "_")
    return f"{safe_name}_{timestamp}.csv"


async def export_system_data(
    project,
    flags: dict[str, bool],
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]:
    """
    Экспортирует выбранные системные таблицы в CSV.

    Args:
        project: Project instance
        flags: {table_label: is_selected}
        output_dir: Директория для сохранения файлов
        timestamp: Временная метка для имён файлов (YYYYMMDD_HHMMSS)
        progress_callback: async callable(value: float, status: str)

    Returns:
        Список путей к созданным файлам
    """
    active_tables = [name for name, active in flags.items() if active]
    if not active_tables:
        return []

    created_files: list[str] = []
    total = len(active_tables)

    for i, table_name in enumerate(active_tables):
        query = TABLE_QUERIES.get(table_name)
        if query is None:
            continue

        file_name = _table_filename(table_name, timestamp)
        file_path = os.path.join(output_dir, file_name)

        await progress_callback(i / total, f"Exporting {table_name}...")

        try:
            await _export_table(project, table_name, file_path, query)
            created_files.append(file_path)
        except Exception as e:
            # Логируем, но продолжаем — не прерываем весь экспорт из-за одной таблицы
            print(f"Warning: failed to export '{table_name}': {e}")

        await progress_callback((i + 1) / total, f"Exported {table_name}")

    return created_files
