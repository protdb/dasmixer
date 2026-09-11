"""Export spectra as MGF files with optional modifications from identifications."""

import gzip
import io
import os
import zipfile
from collections.abc import Awaitable, Callable

import numpy as np
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
    replace_scans: bool = False,
) -> dict:
    """
    Формирует dict params для одного MGF-спектра.
    spec_row — полный dict спектра из get_spectrum_full() (включая all_params как dict).
    ident — dict предпочитаемой идентификации или None.

    Алгоритм:
    1. Из all_params берутся только дополнительные поля (не начинающиеся с "_",
       и не входящие в EXPLICIT_KEYS: mass, charge, pepmass, title, scans, seq).
    2. title — из spec_row["title"].
    3. pepmass — (mass, intensity) из spec_row["pepmass"] и spec_row["intensity"].
    4. charge — из spec_row["charge"], переопределяется из ident если write_spectra_charge.
    5. scans — из all_params или fallback из spec_row["scans"].
    6. seq — из идентификации если write_seq, иначе из all_params.
    7. offset — из идентификации если write_offset.
    """
    EXPLICIT_KEYS = {"mass", "charge", "pepmass", "title", "scans", "seq"}

    params = {}

    all_params = spec_row.get("all_params") or {}
    for key, value in all_params.items():
        if key.startswith("_"):
            continue
        if key in EXPLICIT_KEYS:
            continue
        params[key] = value

    params["title"] = spec_row.get("title", "")

    mass = spec_row.get("pepmass", 0.0)
    intensity = spec_row.get("intensity")
    params["pepmass"] = (float(mass), float(intensity) if intensity is not None else None)

    charge = spec_row.get("charge")
    if write_spectra_charge and ident is not None:
        override = ident.get("override_charge")
        if override is not None:
            charge = int(override)
    if charge is not None:
        params["charge"] = [int(charge)]

    if replace_scans:
        params["scans"] = int(spec_row["id"])
    else:
        scans_in_all_params = all_params.get("scans")
        if scans_in_all_params is not None:
            params["scans"] = scans_in_all_params
        else:
            scans_from_db = spec_row.get("scans")
            if scans_from_db is not None:
                params["scans"] = int(scans_from_db)

    if write_seq and ident is not None:
        seq_val = ident.get("canonical_sequence" if seq_type == "canonical" else "sequence") or ""
        if seq_val:
            params["seq"] = seq_val
    else:
        seq_in_all_params = all_params.get("seq")
        if seq_in_all_params:
            params["seq"] = seq_in_all_params

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


async def _write_mgf_to_file(
    project,
    output_file,          # text-mode file-like object (opened externally)
    sf_ids: list[int],
    by: str,
    tool_id: int | None,
    need_ident: bool,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,
    sequence_contains: str | None,
    replace_scans: bool = False,
    batch_size: int = _BATCH_SIZE,
) -> int:
    """
    Read spectra in batches via get_full_spectrum_for_export, build MGF and write to output_file.
    Returns the number of exported spectra.
    """
    output_file.write("# Exported from DASMixer\n")
    total_written = 0
    offset = 0
    while True:
        batch = await project.get_full_spectrum_for_export(
            sf_ids=sf_ids, by=by, tool_id=tool_id, need_ident=need_ident,
            sequence_contains=sequence_contains, limit=batch_size, offset=offset,
        )
        if not batch:
            break
        batch_spectra = []
        for spec_row in batch:
            # Reconstruct ident dict from flat fields (same shape as old ident dict)
            ident = None
            if need_ident and spec_row.get("sequence") is not None:
                ident = {
                    "override_charge": spec_row.get("override_charge"),
                    "canonical_sequence": spec_row.get("canonical_sequence"),
                    "sequence": spec_row.get("sequence"),
                    "isotope_offset": spec_row.get("isotope_offset"),
                }
            mz_arr = spec_row.get("mz_array")
            int_arr = spec_row.get("intensity_array")
            params = _build_spectrum_params(
                spec_row, ident,
                write_offset, write_spectra_charge, write_seq, seq_type,
                replace_scans=replace_scans,
            )
            charge_arr = spec_row.get("charge_array")
            if charge_arr is None:
                common_val = spec_row.get("charge_array_common_value")
                if common_val is not None and mz_arr is not None:
                    charge_arr = np.full(len(mz_arr), int(common_val))
            else:
                charge_arr = np.where(np.isnan(charge_arr), 0, charge_arr).astype(int)
            spectrum_dict = {
                "params": params,
                "m/z array": mz_arr,
                "intensity array": int_arr,
            }
            if charge_arr is not None:
                spectrum_dict["charge array"] = charge_arr
            batch_spectra.append(spectrum_dict)
        if batch_spectra:
            mgf.write(batch_spectra, output=output_file)
            total_written += len(batch_spectra)
        offset += batch_size
    return total_written


async def _build_export_units(
    project,
    sample_ids: list[int],
    merge_mode: str,
) -> list[dict]:
    """
    Build export units based on merge mode.

    Each unit has: label, base_name, sf_ids.

    merge_mode == "by_sample" (current behavior): one unit per sample_id from
        sample_ids; sf_ids = all spectre_file of the sample; base_name = _sanitize(sample.name).
    merge_mode == "by_spectre_file": for each sample_id — one unit per each
        spectre_file; sf_ids = [sf_id]; base_name = f"{_sanitize(sample.name)}_{sf_id}".
    merge_mode == "one_file": ONE unit for the whole call; sf_ids = all spectre_file
        of all sample_ids; base_name = "dasmixer_mgf".

    When merge_mode == "one_file", there is exactly 1 unit, so zip_all and zip_each
    produce identical results (single zip with single MGF inside). This is by design,
    no special-case code needed.
    """
    from dasmixer.api.export.mgf_export import _sanitize as _san

    units: list[dict] = []

    if merge_mode == "one_file":
        all_sf_ids: list[int] = []
        all_labels: list[str] = []
        for sample_id in sample_ids:
            sf_df = await project.execute_query_df(
                "SELECT id FROM spectre_file WHERE sample_id = ?", [sample_id]
            )
            if sf_df is None or sf_df.empty:
                continue
            sf_ids_for_sample = sf_df["id"].tolist()
            all_sf_ids.extend(sf_ids_for_sample)
            # Get sample name for label via query
            rows = await project.execute_query(
                "SELECT name FROM sample WHERE id = ?", [sample_id]
            )
            if rows:
                all_labels.append(rows[0]["name"])
        if all_sf_ids:
            units.append({
                "label": "All samples",
                "base_name": "dasmixer_mgf",
                "sf_ids": all_sf_ids,
            })
        return units

    for sample_id in sample_ids:
        rows = await project.execute_query(
            "SELECT name FROM sample WHERE id = ?", [sample_id]
        )
        if not rows:
            continue
        sample_name = rows[0]["name"]

        sf_df = await project.execute_query_df(
            "SELECT id FROM spectre_file WHERE sample_id = ? ORDER BY id", [sample_id]
        )
        if sf_df is None or sf_df.empty:
            continue

        sf_ids = sf_df["id"].tolist()

        if merge_mode == "by_spectre_file":
            for sf_id in sf_ids:
                units.append({
                    "label": f"{sample_name} (spectre_file {sf_id})",
                    "base_name": f"{_san(sample_name)}_{sf_id}",
                    "sf_ids": [sf_id],
                })
        else:
            # by_sample (default)
            units.append({
                "label": sample_name,
                "base_name": _san(sample_name),
                "sf_ids": sf_ids,
            })

    return units


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
    replace_scans: bool = False,
    merge_mode: str = "by_sample",
    add_timestamp: bool = True,
    sequence_contains: str | None = None,
    file_suffix: str | None = None,
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
    need_ident = write_offset or write_spectra_charge or write_seq
    suffix_part = ""
    if file_suffix:
        suffix_part = file_suffix if file_suffix.startswith("_") else f"_{file_suffix}"
    ts_suffix = f"_{timestamp}" if add_timestamp else ""

    zip_all_path = os.path.join(output_dir, f"dasmixer_mgf{suffix_part}{ts_suffix}.zip")
    zip_all_file: zipfile.ZipFile | None = None
    if compression == "zip_all":
        zip_all_file = zipfile.ZipFile(zip_all_path, "w", compression=zipfile.ZIP_DEFLATED)

    try:
        units = await _build_export_units(project, sample_ids, merge_mode)
        total = len(units)

        for idx, unit in enumerate(units):
            await progress_callback(
                idx / total if total else 0.0,
                f"Exporting: {unit['label']}",
            )

            sf_ids = unit["sf_ids"]
            probe = await project.get_full_spectrum_for_export(
                sf_ids=sf_ids, by=by, tool_id=tool_id, need_ident=need_ident,
                sequence_contains=sequence_contains, limit=1, offset=0,
            )
            if not probe:
                await progress_callback(
                    (idx + 1) / total if total else 1.0,
                    f"Skipping {unit['label']} (no matching spectra)",
                )
                continue

            base_name = f"{unit['base_name']}{suffix_part}{ts_suffix}"

            if compression == "gzip":
                fpath = os.path.join(output_dir, f"{base_name}.mgf.gz")
                with gzip.open(fpath, "wt", encoding="utf-8") as gz:
                    await _write_mgf_to_file(
                        project, gz, sf_ids, by, tool_id, need_ident,
                        write_offset, write_spectra_charge, write_seq, seq_type,
                        sequence_contains, replace_scans=replace_scans,
                    )
                created_files.append(fpath)

            elif compression == "zip_all":
                buf = io.StringIO()
                await _write_mgf_to_file(
                    project, buf, sf_ids, by, tool_id, need_ident,
                    write_offset, write_spectra_charge, write_seq, seq_type,
                    sequence_contains, replace_scans=replace_scans,
                )
                assert zip_all_file is not None
                zip_all_file.writestr(f"{base_name}.mgf", buf.getvalue().encode("utf-8"))
                if zip_all_path not in created_files:
                    created_files.append(zip_all_path)

            elif compression == "zip_each":
                fpath = os.path.join(output_dir, f"{base_name}.zip")
                buf = io.StringIO()
                await _write_mgf_to_file(
                    project, buf, sf_ids, by, tool_id, need_ident,
                    write_offset, write_spectra_charge, write_seq, seq_type,
                    sequence_contains, replace_scans=replace_scans,
                )
                with zipfile.ZipFile(fpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(f"{base_name}.mgf", buf.getvalue().encode("utf-8"))
                created_files.append(fpath)

            else:
                fpath = os.path.join(output_dir, f"{base_name}.mgf")
                with open(fpath, "w", encoding="utf-8") as f:  # noqa: ASYNC230 — pyteomics mgf.write() needs sync file object
                    await _write_mgf_to_file(
                        project, f, sf_ids, by, tool_id, need_ident,
                        write_offset, write_spectra_charge, write_seq, seq_type,
                        sequence_contains, replace_scans=replace_scans,
                    )
                created_files.append(fpath)

            await progress_callback(
                (idx + 1) / total if total else 1.0,
                f"Completed {unit['label']}",
            )

    finally:
        if zip_all_file is not None:
            zip_all_file.close()

    return created_files
