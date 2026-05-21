# Этап 9: Спецификация реализации

## Обзор задачи

Этап включает три независимых направления:

1. **Схема БД** — добавление полей `source_sequence` и `isotope_offset` в таблицу `identification`
2. **GUI** — доработка `tool_settings_section.py` (выбор PTM) и `ion_settings_section.py` (параметры isotope offset)
3. **Пайплайн расчёта** — замена `coverage_worker` на `identification_processor` с настоящей параллельной обработкой

---

## 1. Схема БД (`api/project/schema.py`)

### Изменения

Добавить два поля в таблицу `identification`:

```sql
source_sequence TEXT,      -- оригинальная (немодифицированная) последовательность,
                           -- NULL если совпадает с sequence
isotope_offset INTEGER     -- precursor isotope offset, NULL если не определялся
```

**Позиция вставки:** после `override_charge INTEGER`, до FOREIGN KEY-блока.

**Обратная совместимость:** не обеспечивается (миграция не требуется, как указано в требованиях).

---

## 2. Mixin идентификаций (`api/project/mixins/identification_mixin.py`)

### 2.1 `put_identification_data_batch`

Расширить UPDATE-запрос, добавив `source_sequence` и `isotope_offset`:

```sql
UPDATE identification
SET
    ppm = ?,
    theor_mass = ?,
    override_charge = ?,
    intensity_coverage = ?,
    ions_matched = ?,
    ion_match_type = ?,
    top_peaks_covered = ?,
    source_sequence = ?,
    isotope_offset = ?
WHERE id = ?
```

Логика формирования `source_sequence` при записи: если значение `source_sequence` в dict совпадает с `sequence`, то записывать NULL (хранить только если отличается).

### 2.2 `get_identifications_with_spectra_batch`

Нет изменений в запросе — `source_sequence` и `isotope_offset` не нужны для расчёта (они являются результатом, а не входными данными).

---

## 3. GUI — Tool Settings Section (`gui/views/tabs/peptides/tool_settings_section.py`)

### 3.1 Контрол выбора PTM

**Механика:** кнопка "Select PTMs..." открывает `ft.AlertDialog` со списком чекбоксов по одному на каждый PTM из `utils/seqfixer_utils.PTMS`. После подтверждения выбранные PTM отображаются на карточке инструмента как текстовое поле (read-only `ft.TextField` или просто `ft.Text`) с перечислением через запятую.

**Список PTM:** получается из `PTMS` в `utils/seqfixer_utils.py` — берётся атрибут `.code` каждого `FixedPTM`.

**Хранение:** список выбранных кодов PTM сохраняется в `tool.settings['ptm_list']` как список строк (JSON-сериализуется штатным механизмом settings).

**Дефолт:** все PTM выбраны (None в settings == использовать все PTMS).

**Реализация:**

```python
# В _create_tool_controls() — добавить:
'ptm_selected': list[str]   # хранится в state как список кодов
'ptm_display': ft.Text(...)  # строка через запятую, read-only
```

Кнопка "PTMs..." рядом с `ptm_display` вызывает метод `_open_ptm_dialog(tool_id)`.

Диалог:
- Заголовок: "Select PTMs for {tool.name}"
- Контент: `ft.Column` с `ft.Checkbox` на каждый PTM (label = `ptm.code`)
- Кнопки: "Cancel" / "Apply"
- При Apply: обновляет `ptm_selected` в dict controls и обновляет текст `ptm_display`

**Важно:** диалог должен быть модальным (`modal=True`) и открываться через `page.overlay`.

### 3.2 Изменения в карточке (`_build_tool_card`)

Добавить строку с PTM-выбором:

```
Row: [ptm_display_field (expand=True), ptm_button]
```

Добавить после Row с leucine_combinatorics.

### 3.3 Сохранение (`save_tool_settings`)

Добавить в `tool.settings`:
```python
'ptm_list': controls['ptm_selected'],  # list[str] или None (если все)
```

### 3.4 Получение для pipeline (`get_tool_settings_for_matching`)

Добавить:
```python
'ptm_list': controls['ptm_selected'],
```

---

## 4. GUI — Ion Settings Section (`gui/views/tabs/peptides/ion_settings_section.py`)

### 4.1 Новые поля

```python
self.force_isotope_offset_cb = ft.Checkbox(
    label="Force isotope offset lookover",
    value=True
)
self.max_isotope_offset_field = ft.TextField(
    label="Max isotope offset",
    value="2",
    width=180,
    keyboard_type=ft.KeyboardType.NUMBER,
)
```

### 4.2 Расположение в `_build_content`

Добавить новую строку в `ft.Column` после строки с `min_precursor_charge` / `max_precursor_charge`:

```python
ft.Row([
    self.force_isotope_offset_cb,
    self.max_isotope_offset_field,
], spacing=10)
```

### 4.3 `load_data`

```python
self.force_isotope_offset_cb.value = (
    await self.project.get_setting('force_isotope_offset', '1')
) == '1'
self.max_isotope_offset_field.value = await self.project.get_setting(
    'max_isotope_offset', '2'
)
```

### 4.4 `save_settings`

```python
await self.project.set_setting(
    'force_isotope_offset', '1' if self.force_isotope_offset_cb.value else '0'
)
await self.project.set_setting('max_isotope_offset', self.max_isotope_offset_field.value)
```

### 4.5 `_sync_to_state` и `PeptidesTabState`

В `shared_state.py` добавить:
```python
force_isotope_offset: bool = True
max_isotope_offset: int = 2
```

В `_sync_to_state`:
```python
self.state.force_isotope_offset = self.force_isotope_offset_cb.value
self.state.max_isotope_offset = int(self.max_isotope_offset_field.value or 2)
```

### 4.6 `get_charge_parameters`

Расширить возвращаемый dict:
```python
return {
    'ignore_spectre_charges': self.state.ignore_spectre_charges,
    'min_charge': self.state.min_precursor_charge,
    'max_charge': self.state.max_precursor_charge,
    'force_isotope_offset': self.state.force_isotope_offset,
    'max_isotope_offset': self.state.max_isotope_offset,
}
```

---

## 5. Пайплайн расчёта (`gui/views/tabs/peptides/ion_calculations.py`)

### 5.1 Стратегия параллельной обработки

**Проблема текущей реализации:** `run_in_executor` вызывается с целым batch из 1000 записей, но `process_identification_batch` (coverage_worker) обрабатывает их последовательно внутри одного процесса. Т.е. реальный параллелизм — один процесс на один batch.

**Предлагаемое решение:** разбивать каждый fetched batch на `cpu_count` частей и запускать их параллельно через `ProcessPoolExecutor`. При этом:
- Размер одного pull из БД (`_BATCH_SIZE`) остаётся разумным (1000–2000 записей) для контроля ОЗУ
- Каждый sub-batch = `_BATCH_SIZE / cpu_count` записей
- Все sub-batches запускаются конкурентно через `asyncio.gather` + `loop.run_in_executor`

**Псевдокод:**

```python
import math

_WORKER_COUNT = max(1, (os.cpu_count() or 2) - 1)
_BATCH_SIZE = 1000

async def run_coverage_calc(self, recalc_all: bool):
    ...
    chunk_size = max(1, math.ceil(_BATCH_SIZE / _WORKER_COUNT))

    with ProcessPoolExecutor(max_workers=_WORKER_COUNT) as executor:
        for tool_id in tool_ids:
            offset = 0
            while True:
                batch_objects = await self.project.get_identifications_with_spectra_batch(
                    tool_id=tool_id,
                    offset=offset,
                    limit=_BATCH_SIZE,
                    only_missing=not recalc_all,
                )
                if not batch_objects:
                    break

                worker_batch = [obj.to_worker_dict() for obj in batch_objects]

                # Разбиваем на sub-batches по числу воркеров
                sub_batches = [
                    worker_batch[i:i + chunk_size]
                    for i in range(0, len(worker_batch), chunk_size)
                ]

                # Запускаем параллельно
                futures = [
                    loop.run_in_executor(
                        executor,
                        process_identificatons_batch,  # NEW: из identification_processor
                        sub_batch,
                        params_dict,
                        fragment_charges,
                        target_ppm,
                        min_charge,
                        max_charge,
                        max_isotope_offset,
                        force_isotope_offset,
                        ptm_list_for_tool,  # из tool settings
                        5,  # max_ptm (можно сделать настраиваемым)
                        seq_criteria,
                    )
                    for sub_batch in sub_batches
                ]

                sub_results = await asyncio.gather(*futures)
                results = [item for sub in sub_results for item in sub]  # flatten

                await self.project.put_identification_data_batch(results)
                total_processed += len(results)
                offset += _BATCH_SIZE
```

### 5.2 Замена функции worker'а

- **Старый:** `coverage_worker.process_identification_batch`
- **Новый:** `identification_processor.process_identificatons_batch`

Сигнатура `process_identificatons_batch` принимает дополнительные параметры:
- `target_ppm` — берётся из `state.ion_ppm_threshold`
- `min_charge`, `max_charge` — из state
- `max_isotope_offset` — из state (новое поле)
- `force_isotope_offset_lookover` — из state (новое поле)
- `ptm_names_list` — из tool settings (`ptm_list`), `None` = все
- `max_ptm` — фиксированно 5 (или вынести в настройки инструмента позже)
- `seq_criteria` — `'coverage'` (по умолчанию)

### 5.3 Новые поля в результатах и их сохранение

`process_identificatons_batch` возвращает в каждом dict поля:
- `id`, `sequence`, `ppm`, `theor_mass`, `override_charge`
- `intensity_coverage`, `ions_matched`, `ion_match_type`, `top_peaks_covered`
- `isotope_offset` (новое)
- `source_sequence` (новое — оригинальная последовательность до замены PTM)

`put_identification_data_batch` должен принять и записать `source_sequence` и `isotope_offset`.

**Логика `source_sequence`:** в `process_identificatons_batch` уже присваивается `result['source_sequence'] = sequence` (исходная последовательность до PTM-подбора). При сохранении: если `source_sequence == result['sequence']` (т.е. последовательность не была изменена), записывать NULL.

---

## 6. Затронутые файлы — итого

| Файл | Тип изменений |
|---|---|
| `api/project/schema.py` | Добавление 2 полей в таблицу `identification` |
| `api/project/mixins/identification_mixin.py` | Расширение `put_identification_data_batch` (2 новых поля) |
| `gui/views/tabs/peptides/shared_state.py` | Добавление 2 полей в `PeptidesTabState` |
| `gui/views/tabs/peptides/ion_settings_section.py` | Добавление 2 контролов + save/load/sync |
| `gui/views/tabs/peptides/tool_settings_section.py` | PTM-диалог, контролы, save/load |
| `gui/views/tabs/peptides/ion_calculations.py` | Замена worker'а, параллельная обработка sub-batch |

---

## 7. Открытые вопросы

### 7.1 Параметр `max_ptm` в настройках инструмента

Сейчас предлагается использовать фиксированное значение `5`. Стоит ли выносить его в `tool_settings_section` как числовое поле? Это влияет на производительность: больше `max_ptm` — экспоненциально растёт число комбинаций для проверки.

> Ответ: да, надо вынести, это я забыл

### 7.2 `seq_criteria` — критерий выбора лучшей override-последовательности

В `process_identificatons_batch` параметр `seq_criteria` принимает `'peaks'`, `'top_peaks'` или `'coverage'`. Нужно ли выносить его в ion settings UI или оставить фиксированным `'coverage'`?

> Ответ: выносим как выпадающий список

### 7.3 Размер `_BATCH_SIZE` и ОЗУ

При `_BATCH_SIZE=1000` и наличии массивов mz/intensity (float64, потенциально 1000–10000 точек на спектр) одна такая batch может занять значительный объём ОЗУ. При передаче sub-batch через IPC (pickle) это умножается на число процессов. Стоит ли сделать `_BATCH_SIZE` настраиваемым (в системных настройках) или оставить хардкодом с уменьшенным значением (например, 500)?

> Ответ: вынос размеров батчей в настройки сделаем, но позже. Пока оставляем 1000

### 7.4 PTM-диалог — поведение при отсутствии ни одной выбранной PTM

Если пользователь снял все чекбоксы в диалоге — нужно ли интерпретировать это как "не применять PTM-коррекцию вообще" (передавать пустой список) или как "использовать все PTM по умолчанию" (передавать None)? Семантика `ptm_names_list=None` в `process_identificatons_batch` — "все PTMS", а `ptm_names_list=[]` — "ни одного PTM".

> Ответ: интерпретируем отсутствие виделений как отсутствие коррекции

### 7.5 Обновление `get_identifications_with_spectra_batch` для фильтрации по tool

При переходе на `identification_processor` необходимо убедиться, что `only_missing` корректно работает — сейчас фильтр `intensity_coverage IS NULL` корректен. Но после добавления новых полей, возможно, стоит добавить опциональный фильтр `isotope_offset IS NULL OR source_sequence IS NULL` для "пересчёта только без новых полей".

> Ответ: не добавляем новые поля, считаем что если есть intensity_coverage, то расчет был выполнен

### 7.6 Взаимодействие с `process_peptide_match_batch` (protein metrics)

`calculate_protein_metrics_internal` по-прежнему использует `coverage_worker.process_peptide_match_batch`. Эта функция не затрагивается в данном этапе — но стоит ли при следующем рефакторинге переключить и её на новый пайплайн или оставить как есть?

> Ответ: оставляем как есть, для белков нужно будет немного усовершенствовать пайплайн

