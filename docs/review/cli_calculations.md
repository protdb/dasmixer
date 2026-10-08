# CLI-расчёты: отложенные задачи и найденные проблемы

**Тип документа:** постановка задач + результаты исследования (не реализация)
**Дата:** 2026-10-08
**Область:** `dasmixer-cli/src/dasmixer/cli/commands/calculate.py`, корневой `pipeline.py`
**Статус:** CLI-часть задачи 0.7.4a3 (параллелизм ion matching и protein map) **отложена** по решению разработчика.

---

## 1. Контекст

В рамках спецификации `docs/project/spec/0.7.4a3_SPEC.md` распараллеливаются два расчёта:

1. **Ion matching** — переход со статической нарезки sub-batches на очередь чанков
   (`ProcessPoolExecutor` + `run_identification_queue` + периодические записи в БД).
2. **Protein map / de novo correction** — распараллеливание per-row цикла через
   `protein_map_worker.process_protein_map_row`, переделка `map_proteins` из
   async-генератора в обычную async-функцию (запись внутрь + `progress_callback`/`stop_check`).

Core и GUI-части выполнены и проверены (см. п.2). **CLI-часть отложена**, потому что
`calculate.py` оказался фундаментально отставшим от ядра — «докрутить параллелизм» поверх
него невозможно без полноценного rewrite (см. п.4).

---

## 2. Что уже сделано (не требует повтора)

| Файл | Изменение |
|---|---|
| `dasmixer-core/.../spectra/queue_runner.py` | **новый** — `run_identification_queue(...)` (очередь чанков, semaphore, flush через callback) |
| `dasmixer-core/.../peptides/protein_map_worker.py` | **новый** — `process_protein_map_row(...)` (per-row, picklable) |
| `dasmixer-core/.../peptides/protein_map.py` | `map_proteins` — убран `yield`, `ProcessPoolExecutor` на каждый `tool_id`, запись внутрь (`add_peptide_matches_batch` + `_commit`), `progress_callback(processed, -1)` / `stop_check`, финальный `save()` |
| `dasmixer-gui/.../actions/ion_actions.py` | `IonCoverageAction.run` переведён на `run_identification_queue` |
| `dasmixer-gui/.../actions/protein_map_action.py` | `MatchProteinsAction.run` — `await map_proteins(...)` вместо `async for`, stoppable диалог |
| `docs/api/pipeline.md` | оба примера `map_proteins` обновлены под новую сигнатуру |

**Актуальные сигнатуры ядра** (для будущего rewrite CLI):

```python
# dasmixer.api.calculations.spectra.queue_runner
async def run_identification_queue(
    worker_dicts: list[dict],
    executor: ProcessPoolExecutor,
    chunk_size: int,
    flush_every: int,
    process_fn: Callable[..., list[dict]],
    process_fn_kwargs: dict,                       # kwargs для process_fn (кроме batch)
    flush_callback: Callable[[list[dict]], Awaitable[None]],
    progress_callback: Callable[[int], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> int:

# dasmixer.api.calculations.spectra.identification_processor
def process_identifications_batch(
    batch: list[dict],                             # список worker-dicts С уже загруженными спектрами
    params_dict: dict,                             # ions/tolerance/mode/water_loss/ammonia_loss
    fragment_charges: list[int],
    target_ppm: float,
    min_charge: int = 1,
    max_charge: int = 4,
    max_isotope_offset: int = 2,
    force_isotope_offset_lookover: bool = True,
    ptm_names_list: list[str] | None = None,
    max_ptm: int = 5,
    seq_criteria: Literal["peaks", "top_peaks", "coverage"] = "coverage",
    max_ptm_sites: int = 10,
    trust_ppm: bool = False,
    unallocated_only: bool = False,
    quality_threshold: float = 0.25,
) -> list[dict]:

# dasmixer.api.calculations.peptides.protein_map
async def map_proteins(
    project: Project,
    tool_settings: dict[int, dict],
    ion_params: dict,
    fragment_charges: list[int],
    seqfixer_params: dict,
    batch_size: int = 5000,
    sample_id: int | None = None,
    use_src_protein_ids: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,   # (processed, total=-1)
    stop_check: Callable[[], bool] | None = None,
) -> None:   # пишет в БД и делает save() внутри
```

---

## 3. Отложенные задачи

### Задача 1.3 — ion coverage в CLI (по `run_identification_queue`)

Команда `calculate ion_coverage` должна по аналогии с GUI (`ion_actions.py`):
1. читать настройки из `project_settings`;
2. строить `params_dict` (dict, а не объект) и `process_fn_kwargs` с **корректными именами** полей;
3. читать пакет через `project.get_identifications_with_spectra_batch(...)` → `obj.to_worker_dict()`;
4. вызывать `run_identification_queue(...)` с `flush_callback` = запись через
   `project.put_identification_data_batch` + `project._commit()`;
5. выводить прогресс (typer echo) и опционально поддерживать остановку.

### Задача 2.4 — protein map в CLI (по новой сигнатуре `map_proteins`)

Команды `calculate peptide_match` и `calculate peptides` (шаг «Match proteins») должны:
1. строить `tool_settings` в формате `map_proteins` (включая `min_protein_identity`,
   `leucine_combinatorics`, `match_correction_criteria`, `save_aa_substitutions`, PTM-список и т.д.);
2. строить `ion_params`, `fragment_charges`, `seqfixer_params`;
3. вызывать `await map_proteins(...)` с `progress_callback` (CLI-вывод) и `stop_check` (если нужно);
4. **не** трогать `add_peptide_matches_batch` — `map_proteins` теперь пишет сам.

---

## 4. Проблемы `dasmixer-cli/src/dasmixer/cli/commands/calculate.py`

### 4.1 `ion_coverage` (строки 93–186) — полностью нерабочая

- **Строка 127** — `from dasmixer.api.calculations.ppm.seqfixer import SeqfixerParams`.
  Класс `SeqfixerParams` **не существует** (по всему `dasmixer-core` его нет — `grep` пуст).
  Команда падает на импорте.
- **Строки 141–148** — `IonMatchParameters(ion_types=..., ppm_tolerance=..., match_mode=...,
  water_loss=..., ammonia_loss=..., fragment_charges=...)`. Поля **неверные**. Реальные поля
  `IonMatchParameters`: `ions, tolerance, mode, water_loss, ammonia_loss, charges`.
- **Строки 166–175** — цикл читает `idents_df = await project.get_identifications(...)` и
  передаёт `batch = idents_df.iloc[...]` (сырой **DataFrame**) в
  `process_identifications_batch(batch, ion_params, seqfixer_params)`.
  - `process_identifications_batch` ждёт `list[dict]` с уже загруженными `mz_array`/`intensity_array`.
  - Вторым аргументом передаётся объект `IonMatchParameters` вместо `params_dict: dict`,
    третьим — `SeqfixerParams` вместо `fragment_charges: list[int]`.
- **Спектры не загружаются вообще.** GUI делает
  `get_identifications_with_spectra_batch(...)` → `obj.to_worker_dict()`; в CLI этого шага нет.

### 4.2 `peptide_match` (строки 225–283)

- **Строки 267–273** — `map_proteins(project, tool_settings, fasta_path=..., identity_threshold=...,
  mapping_batch_size=..., sample_id=sample_id)`. Таких kwargs **нет** ни в старой, ни в новой
  сигнатуре (реальные: `ion_params`, `fragment_charges`, `seqfixer_params`, `batch_size`,
  `sample_id`, `use_src_protein_ids`).
- **Строка 267** — `total = await map_proteins(...)`; `map_proteins` теперь возвращает `None`.
- `tool_settings` в этой команде строится «вручную» (строки 257–264) и не содержит нужных
  `map_proteins` ключей (`min_protein_identity`, `leucine_combinatorics`,
  `match_correction_criteria`, `save_aa_substitutions`, PTM-список).

### 4.3 `peptides` (строки 457–558) — те же проблемы в двух шагах

- **Шаг 1 «Match proteins» (строки 494–501)** — `map_proteins(... fasta_path=..., identity_threshold=...,
  mapping_batch_size=...)` — неверные kwargs, как в 4.2.
- **Шаг 2 «Ion coverage» (строки 506–539)** — тот же `SeqfixerParams` (строка 519) +
  неверные поля `IonMatchParameters` (строки 522–529) + передача сырого DataFrame в
  `process_identifications_batch` (строка 536).

### 4.4 `_collect_tool_settings` (строки 18–47)

Возвращает `tool_settings`, заточенный под `calculate_preferred_identifications_for_file`
(ключи `ignore_criteria`, `min_score`, `min_peptide_length` и т.п.), а не под `map_proteins`.
Для 2.4 понадобится отдельная сборка settings (или расширение этой функции под обе цели).

### 4.5 Команды, которые НЕ трогаем

`preferred` (193), `protein_idents` (290), `lfq` (359) — не связаны с ion matching/protein
map и в рамках этой задачи не меняются.

---

## 5. Корневой `pipeline.py`

`/pipeline.py` (299 строк) — standalone-пример, по сути дублирует «Complete Script» из
`docs/api/pipeline.md`. После рефакторинга `map_proteins` он **сломается**:

- **Строка 215** — `async for matches_df, count, _tid in map_proteins(...)`.

В спецификации 0.7.4a3 затронут только `docs/api/pipeline.md` (задача 2.5, выполнена),
а `pipeline.py` остался вне скоупа. Нужно решение разработчика: **обновить** (по аналогии с
pipeline.md), **удалить** (как дубль документации) или **оставить** (только пометить как устаревший).

---

## 6. Второстепенные замечания

1. **Опечатка в спеке 0.7.4a3 (таблица 1.2)**: пример `chunk_size = 625` не соответствует
   формуле `int(batch_size / worker_count)` (при 5000/7 → 714; 625 = 5000/8). Формула и принцип
   «flush ≈ batch_size» согласованы — это только пример-опечатка.
2. **`docs/api/pipeline.md` Step 6** всё ещё использует `process_identificatons_batch`
   (устаревшее имя с опечаткой, ныне `process_identifications_batch`) и непотоковый вызов —
   вне скоупа задачи 2.5, но стоит поправить отдельно.
3. В `map_proteins` прогресс-счётчик `total_processed` не увеличивается в edge-ветках
   «весь пакет ушёл в src-protein» и «`blast_df.empty`» (там `continue` до инкремента).
   На корректность данных не влияет; только на точность CLI/GUI прогресса — учесть при rewrite CLI.

---

## 7. Предлагаемый порядок работы (когда вернёмся к CLI)

1. Решить судьбу `pipeline.py` (обновить/удалить).
2. Rewrite `ion_coverage` под реальный процессор (задача 1.3).
3. Rewrite `peptide_match` и шаг «Match proteins» в `peptides` под новую `map_proteins` (2.4).
4. Починить шаг «Ion coverage» в `peptides` (там же, что и 1.3).
5. Расширить/завести отдельную сборку `tool_settings` для `map_proteins`.
6. При желании — синхронизировать `docs/api/pipeline.md` Step 6 с актуальным именем процессора.