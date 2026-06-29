"""Export spectra as MGF files with optional modifications from identifications."""

import gzip
import io
import os
import zipfile
from typing import Awaitable, Callable

from pyteomics import mgf


_BATCH_SIZE = 500  # спектров за один батч


def _sanitize(name: str) -> str:
    """Заменяем недопустимые символы в имени файла на '_'."""
    for ch in '/\\:*?"<>| ':
        name = name.replace(ch, "_")
    return name


def _build_spectrum_params(
    spec_row: dict,
    ident: dict | None,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,
) -> dict:
    """
    Формирует dict params для одного MGF-спектра.
    spec_row — полный dict спектра из get_spectrum_full().
    ident — dict предпочитаемой идентификации или None.
    """
    params: dict = {
        "title": spec_row.get("title", ""),
        "pepmass": (spec_row.get("pepmass", 0.0), None),
    }

    charge = spec_row.get("charge")

    if write_spectra_charge and ident is not None:
        override = ident.get("override_charge")
        if override is not None:
            charge = int(override)

    if charge is not None:
        params["charge"] = [int(charge)]

    if write_seq and ident is not None:
        if seq_type == "canonical":
            seq_val = ident.get("canonical_sequence") or ""
        else:
            seq_val = ident.get("sequence") or ""
        if seq_val:
            params["seq"] = seq_val

    if write_offset and ident is not None:
        offset_val = ident.get("isotope_offset")
        if offset_val is not None:
            params["offset"] = offset_val

    return params


async def _get_sample(project, sample_id: int):
    """Возвращает Sample по id или None."""
    samples = await project.get_samples()
    for s in samples:
        if s.id == sample_id:
            return s
    return None


async def _get_preferred_identification(
    project, spectrum_id: int, tool_id: int | None
) -> dict | None:
    """Возвращает preferred-идентификацию для спектра (по tool_id если задан)."""
    if tool_id is not None:
        rows = await project.execute_query(
            "SELECT * FROM identification "
            "WHERE spectre_id = ? AND tool_id = ? AND is_preferred = 1 LIMIT 1",
            [spectrum_id, tool_id],
        )
    else:
        rows = await project.execute_query(
            "SELECT * FROM identification "
            "WHERE spectre_id = ? AND is_preferred = 1 LIMIT 1",
            [spectrum_id],
        )
    return rows[0] if rows else None


async def _iter_spectra_batched(project, query: str, params: list, batch_size: int):
    """
    Асинхронный генератор, возвращающий строки батчами.
    Каждый элемент — dict с полями spectre (без BLOB).
    """
    cursor = await project._execute(query, params)
    col_names = [desc[0] for desc in cursor.description]
    while True:
        rows = await cursor.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            yield dict(zip(col_names, row))
    await cursor.close()


async def _write_mgf_to_file(
    project,
    output_file,          # text-mode file-like object (открытый снаружи)
    spectrum_ids: list[int],
    need_ident: bool,
    tool_id: int | None,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,
    batch_size: int = _BATCH_SIZE,
) -> None:
    """
    Читает спектры батчами по spectrum_ids, формирует MGF и пишет в output_file.
    """
    for i in range(0, len(spectrum_ids), batch_size):
        batch_ids = spectrum_ids[i: i + batch_size]
        batch_spectra = []

        for spec_id in batch_ids:
            full_spec = await project.get_spectrum_full(spec_id)

            ident: dict | None = None
            if need_ident:
                ident = await _get_preferred_identification(project, spec_id, tool_id)

            mz_arr = full_spec.get("mz_array")
            int_arr = full_spec.get("intensity_array")

            params = _build_spectrum_params(
                full_spec, ident,
                write_offset, write_spectra_charge, write_seq, seq_type,
            )

            batch_spectra.append({
                "params": params,
                "m/z array": mz_arr,
                "intensity array": int_arr,
            })

        if batch_spectra:
            mgf.write(batch_spectra, output=output_file)


async def _get_spectrum_ids(
    project,
    sf_ids: list[int],
    by: str,
    tool_id: int | None,
) -> list[int]:
    """
    Возвращает список spectrum.id для заданных spectre_file_id и режима фильтрации.
    """
    placeholders = ",".join("?" for _ in sf_ids)

    if by == "all":
        query = (
            f"SELECT id FROM spectre "
            f"WHERE spectre_file_id IN ({placeholders}) ORDER BY id"
        )
        rows = await project.execute_query(query, sf_ids)
    elif by == "all_preferred":
        query = (
            f"SELECT DISTINCT s.id FROM spectre s "
            f"INNER JOIN identification i ON i.spectre_id = s.id "
            f"WHERE s.spectre_file_id IN ({placeholders}) AND i.is_preferred = 1 "
            f"ORDER BY s.id"
        )
        rows = await project.execute_query(query, sf_ids)
    else:
        # preferred_by_tool
        if tool_id is None:
            return []
        query = (
            f"SELECT DISTINCT s.id FROM spectre s "
            f"INNER JOIN identification i ON i.spectre_id = s.id "
            f"WHERE s.spectre_file_id IN ({placeholders}) "
            f"AND i.is_preferred = 1 AND i.tool_id = ? "
            f"ORDER BY s.id"
        )
        rows = await project.execute_query(query, sf_ids + [tool_id])

    return [row["id"] for row in rows]


async def export_mgf(
    project,
    sample_ids: list[int],
    by: str,                        # "all" | "all_preferred" | "preferred_by_tool"
    tool_id: int | None,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,                  # "canonical" | "modified"
    compression: str,               # "gzip" | "zip_all" | "zip_each" | "none"
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]:
    """
    Экспортирует спектры в MGF-файлы (по одному на образец).

    Args:
        project: Project instance
        sample_ids: Список ID образцов для экспорта
        by: Режим фильтрации спектров
        tool_id: ID инструмента (для by="preferred_by_tool")
        write_offset: Добавлять OFFSET из идентификации
        write_spectra_charge: Заменять charge из идентификации
        write_seq: Добавлять SEQ из идентификации
        seq_type: "canonical" или "modified"
        compression: Тип сжатия
        output_dir: Директория вывода
        timestamp: YYYYMMDD_HHMMSS
        progress_callback: async callable(value, status)

    Returns:
        Список созданных файлов
    """
    created_files: list[str] = []
    total = len(sample_ids)
    need_ident = write_offset or write_spectra_charge or write_seq

    # Для zip_all — один ZipFile открываем до цикла
    zip_all_path = os.path.join(output_dir, f"dasmixer_mgf_{timestamp}.zip")
    zip_all_file: zipfile.ZipFile | None = None
    if compression == "zip_all":
        zip_all_file = zipfile.ZipFile(zip_all_path, "w", compression=zipfile.ZIP_DEFLATED)

    try:
        for idx, sample_id in enumerate(sample_ids):
            sample = await _get_sample(project, sample_id)
            sample_name = _sanitize(sample.name if sample else str(sample_id))

            await progress_callback(
                idx / total if total else 0.0,
                f"Exporting sample: {sample_name}",
            )

            # Получаем ID файлов спектров для образца
            sf_df = await project.execute_query_df(
                "SELECT id FROM spectre_file WHERE sample_id = ?", [sample_id]
            )
            if sf_df is None or sf_df.empty:
                await progress_callback(
                    (idx + 1) / total if total else 1.0,
                    f"Skipping {sample_name} (no spectra files)",
                )
                continue

            sf_ids = sf_df["id"].tolist()

            # Получаем список spectrum.id с учётом фильтра
            spectrum_ids = await _get_spectrum_ids(project, sf_ids, by, tool_id)
            if not spectrum_ids:
                await progress_callback(
                    (idx + 1) / total if total else 1.0,
                    f"Skipping {sample_name} (no matching spectra)",
                )
                continue

            base_name = f"{sample_name}_{timestamp}"

            if compression == "gzip":
                fpath = os.path.join(output_dir, f"{base_name}.mgf.gz")
                with gzip.open(fpath, "wt", encoding="utf-8") as gz:
                    await _write_mgf_to_file(
                        project, gz, spectrum_ids, need_ident, tool_id,
                        write_offset, write_spectra_charge, write_seq, seq_type,
                    )
                created_files.append(fpath)

            elif compression == "zip_all":
                # Пишем MGF в StringIO, затем добавляем в общий ZipFile
                buf = io.StringIO()
                await _write_mgf_to_file(
                    project, buf, spectrum_ids, need_ident, tool_id,
                    write_offset, write_spectra_charge, write_seq, seq_type,
                )
                assert zip_all_file is not None
                zip_all_file.writestr(f"{base_name}.mgf", buf.getvalue().encode("utf-8"))
                if zip_all_path not in created_files:
                    created_files.append(zip_all_path)

            elif compression == "zip_each":
                fpath = os.path.join(output_dir, f"{base_name}.zip")
                buf = io.StringIO()
                await _write_mgf_to_file(
                    project, buf, spectrum_ids, need_ident, tool_id,
                    write_offset, write_spectra_charge, write_seq, seq_type,
                )
                with zipfile.ZipFile(fpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(f"{base_name}.mgf", buf.getvalue().encode("utf-8"))
                created_files.append(fpath)

            else:
                # none — plain MGF
                fpath = os.path.join(output_dir, f"{base_name}.mgf")
                with open(fpath, "w", encoding="utf-8") as f:
                    await _write_mgf_to_file(
                        project, f, spectrum_ids, need_ident, tool_id,
                        write_offset, write_spectra_charge, write_seq, seq_type,
                    )
                created_files.append(fpath)

            await progress_callback(
                (idx + 1) / total if total else 1.0,
                f"Completed {sample_name}",
            )

    finally:
        if zip_all_file is not None:
            zip_all_file.close()

    return created_files
