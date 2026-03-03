# STAGE 7 SPEC: Доработки обработки идентификаций и качества покрытия ионами

> Документ подготовлен на основе `STAGE7_REQUIREMENTS.md` и анализа кода проекта.  
> Статус: **На согласовании**

---

## 1. Обзор задач

Этап 7 состоит из четырёх связанных блоков:

| # | Блок | Затрагиваемые файлы |
|---|------|---------------------|
| 1 | Импорт MGF: сохранение `peaks_count` | `api/inputs/spectra/mgf.py`, `api/project/mixins/spectra_mixin.py` |
| 2 | Рефакторинг `utils/ppm.py`: выделение `calculate_theor_mass`, учёт неканонических остатков | `utils/ppm.py`, `api/peptides/matching.py` |
| 3 | Доработка расчёта покрытия ионами: батчинг + multiprocessing, запись новых полей | `gui/views/tabs/peptides_tab.py`, `api/project/mixins/identification_mixin.py` |
| 4 | UI: новые параметры Tool Settings (4 поля) | `gui/views/tabs/peptides_tab.py` |

---

## 2. Блок 1 — Импорт MGF: поле `peaks_count`

### 2.1 Контекст

Поле `peaks_count INTEGER` добавлено в схему таблицы `spectre` (`api/project/schema.py`).  
При текущем импорте через `MGFParser.parse_batch()` значение этого поля не вычисляется и не передаётся.

### 2.2 Что нужно сделать

#### `api/inputs/spectra/mgf.py`
- В методе `parse_batch()` при формировании словаря записи добавить вычисление длины массива пиков:
  ```python
  'peaks_count': len(record.get('m/z array', [])),
  ```
  Добавляется рядом с `mz_array`, `intensity_array`.

#### `api/project/mixins/spectra_mixin.py`
- В методе `add_spectra_batch()` добавить считывание поля `peaks_count` из DataFrame и его запись в SQL-запрос.
- SQL-запрос `INSERT INTO spectre (...)` расширить полем `peaks_count`.
- Значение брать из строки DataFrame: `int(row['peaks_count']) if row.get('peaks_count') is not None else None`.
- Параметры INSERT и кортеж значений привести в соответствие (добавить 1 позицию).

### 2.3 Ограничения / Примечания
- `peaks_count` рассчитывается по длине `mz_array` (не `intensity_array`, хотя они обычно одинаковы — использовать `mz_array` как источник истины).
- Если массив отсутствует — 0. **Правка: в этом случае не NULL, а 0**

---

## 3. Блок 2 — Рефакторинг `utils/ppm.py`

### 3.1 Контекст

Сейчас:
- `utils/ppm.py` содержит `calculate_ppm(sequence, pepmass, charge)` — внутри него реализована логика парсинга модификаций и вычисления теоретической массы через pyteomics.
- `api/peptides/matching.py` содержит `safe_canon_calculate_mass(sequence)` — обрабатывает неканонические аминокислотные остатки (X и пр.) при ошибке `PyteomicsError`.
- В `map_proteins` используется `safe_canon_calculate_mass` напрямую; в `calculate_ppm` — аналогичная, но дублирующаяся логика.

### 3.2 Что нужно сделать

#### `utils/ppm.py` — добавить функцию `calculate_theor_mass`

```python
def calculate_theor_mass(sequence: str) -> float:
    """
    Рассчитывает теоретическую монизотопную массу (нейтральную) пептида.
    Поддерживает ProForma-нотацию модификаций.
    Обрабатывает неканонические остатки: при PyteomicsError считает массу
    канонических остатков + avg_mass * количество неканонических.
    """
```

**Логика (перенесена из `safe_canon_calculate_mass` + текущего внутреннего кода `calculate_ppm`):**

1. Если в строке `sequence` нет символа `[` (нет модификаций в ProForma-нотации):
   - Попытка `mass.calculate_mass(sequence=clean_sequence, ion_type='M', charge=0)` (нейтральная масса)
   - При `PyteomicsError` — сумма масс канонических остатков + `avg_mass * len(неканонических)`
2. Если есть `[` (ProForma):
   - Попытка `mass.calculate_mass(proforma=sequence, ion_type='M', charge=0)`
   - При `PyteomicsError` — аналогичный fallback по канонической части

> **Вопрос 1:** Как именно сейчас `calculate_ppm` обрабатывает ProForma-нотацию `[+15.99]`? Текущая логика в ppm.py ищет паттерн `(±число)` — это старая нотация. Нужно уточнить, какая нотация используется в реальных данных (PowerNovo2, PeptideShaker и т.д.) — круглые скобки `(+42.01)` или квадратные `[+42.01]`. Это влияет на то, нужно ли поддерживать оба варианта в `calculate_theor_mass`.
>**Ответ**: в БД проекта все последоватлеьности уже в нотации ProForma, форматирование выполняется на этапе загрузки данных, т.е. за это отвечает парсер input-файлов. Но замечание ценное, будет полезно в перспективе сделать штатный функционал приведения к ProForma для модификаций при парсинге. 

#### `utils/ppm.py` — рефакторинг `calculate_ppm`

- Убрать дублированную внутреннюю логику расчёта массы.
- Вызывать `calculate_theor_mass(sequence)` для получения нейтральной массы, затем пересчитать в m/z через `(neutral_mass + charge * proton) / charge`.
- Добавить `avg_mass` и `canonical_aa` как модульные константы (перенести из `matching.py`).

#### `api/peptides/matching.py` — замена `safe_canon_calculate_mass`

- Убрать локальное определение `safe_canon_calculate_mass`.
- Убрать локальные константы `canonical_aa`, `avg_mass`.
- Импортировать `calculate_theor_mass` из `utils.ppm`.
- Заменить все вызовы `safe_canon_calculate_mass(...)` на `calculate_theor_mass(...)` в `map_proteins`.

### 3.3 Ограничения / Примечания
- Не нарушать публичный интерфейс `calculate_ppm(sequence, pepmass, charge)` — он используется в `matching.py` и `peptides_tab.py`.
- `calculate_theor_mass` должна вернуть нейтральную монизотопную массу (без учёта заряда и протонов). **Правка**: поскольку основная задача - определение отклонения в ppm, то заряд стоит использвоать (в соответствии с зарядом прекурсора из spectre)

---

## 4. Блок 3 — Расчёт покрытия ионами: батчинг + multiprocessing + новые поля

### 4.1 Контекст

Текущая реализация `_run_coverage_calc` в `PeptidesTab`:
- Читает все идентификации через SQL-запрос напрямую через `execute_query_df`.
- Обходит их в цикле по одной, вызывая `get_spectrum_full` и `match_predictions` для каждой.
- Сохраняет только `intensity_coverage` через `update_identification_coverage`.
- Не сохраняет новые поля: `ions_matched`, `ion_match_type`, `top_peaks_covered`.
- Пересчёт PPM (`theor_mass`) не производится.

Уже подготовлены:
- `get_identifications_with_spectra_batch(tool_id, offset, limit)` в `identification_mixin.py` — читает идентификации со спектрами батчами.
- `put_identification_data_batch(data_rows)` в `identification_mixin.py` — обновляет набор полей батчем.
- `match_predictions` возвращает `top10_intensity_matches`, `total_peaks`, `max_ion_matches`, `top_matched_ion_type`.

### 4.2 Что нужно сделать

#### 4.2.1 Исправления в `identification_mixin.py`

При анализе кода обнаружены баги в уже написанных методах:

**`get_identifications_with_spectra_batch`:**
- SQL-запрос содержит синтаксическую ошибку: два `where` — `where s.id = i.spectre_id` и `where i.tool_id = ?`. Нужно исправить на `JOIN ... WHERE`.
- Корректный запрос:
  ```sql
  SELECT i.id, i.spectre_id, s.pepmass, s.mz_array, s.intensity_array,
         s.peaks_count, i.tool_id, i.sequence, i.canonical_sequence, s.charge
  FROM identification i
  JOIN spectre s ON s.id = i.spectre_id
  WHERE i.tool_id = ?
  LIMIT ? OFFSET ?
  ```
  (порядок LIMIT/OFFSET в SQLite: `LIMIT ? OFFSET ?`, params: `(limit, offset)` — в текущем коде порядок параметров перепутан: `(tool_id, offset, limit)` вместо `(tool_id, limit, offset)`)
- Добавить в выборку поля `s.charge` и `s.peaks_count` (они понадобятся при расчёте).
- Метод должен возвращать `list[IdentificationWithSpectrum]` — добавить `charge` и `peaks_count` в `IdentificationWithSpectrum` (dataclass).

**`put_identification_data_batch`:**
- В SQL UPDATE отсутствуют запятые между SET-присвоениями. Исправить.
- Метод не является `async` — добавить `await self._executemany(...)`.

#### 4.2.2 Архитектура нового расчёта

Создать отдельную функцию-воркер (не метод класса) в `api/spectra/ion_match.py` или в отдельном модуле `api/spectra/coverage_worker.py`:

```python
def process_identification_batch(
    batch: list[dict],   # сериализованные данные (mz_array как list, intensity_array как list)
    params_dict: dict,   # параметры IonMatchParameters
    charges: list[int],  # fragment charges из настроек
) -> list[dict]:
    """
    Воркер для multiprocessing.Pool.
    Принимает батч, возвращает список dict с результатами для put_identification_data_batch.
    """
```

Почему не передавать `IdentificationWithSpectrum` напрямую: объекты с numpy arrays не сериализуются через pickle стандартно для multiprocessing — нужно конвертировать в plain dict с `list`.

#### 4.2.3 Доработка `_run_coverage_calc` в `peptides_tab.py`

Новая логика метода:

1. Загрузить настройки ионов (уже делается).
2. Для каждого `tool_id` из `tool_settings_controls`:
   a. Читать батч через `project.get_identifications_with_spectra_batch(tool_id, offset, limit=1000)`.
   b. Сериализовать батч в `list[dict]` для передачи в multiprocessing.
   c. Запустить `multiprocessing.Pool` с `process_identification_batch`.
   d. Собрать результаты, передать в `project.put_identification_data_batch(results)`.
   e. Повторять до конца данных.
3. После обработки всех инструментов: `await project.save()`.
4. Обновлять прогресс-бар по количеству обработанных батчей.

> **Вопрос 2:** Сколько процессов использовать в `Pool`? Предлагаю `os.cpu_count() - 1` или `min(4, os.cpu_count())`. Нужно ли ограничение сверху?
> **Ответ**: os.cpu_count(), ограничение сверху реализуем отдельным этапом через системные настройки

> **Вопрос 3:** Нужно ли при `recalc_all=False` (только отсутствующие) фильтровать по `intensity_coverage IS NULL` или по всем трём полям (`ions_matched IS NULL AND ion_match_type IS NULL AND top_peaks_covered IS NULL`)? Предлагаю фильтровать по `intensity_coverage IS NULL` как сейчас, поскольку все поля рассчитываются вместе.
> **Да, делаем только по intensity_coverage IS NULL**

#### 4.2.4 Что записывается в БД

По результату `match_predictions` для каждой идентификации записываем через `put_identification_data_batch`:

| Поле в БД | Источник из `MatchResult` | Тип |
|-----------|--------------------------|-----|
| `ppm` | `calculate_ppm(sequence, pepmass, charge)` → `calculate_theor_mass` | float |
| `theor_mass` | `calculate_theor_mass(sequence)` | float |
| `intensity_coverage` | `result.intensity_percent` | float |
| `ions_matched` | `result.max_ion_matches` | int |
| `ion_match_type` | `result.top_matched_ion_type` | str |
| `top_peaks_covered` | `result.top10_intensity_matches` | int |

> **Вопрос 4:** Поле `ppm` в идентификации — это PPM между экспериментальной `pepmass` и теоретической массой пептида. Сейчас оно могло быть заполнено при импорте (из файла идентификации). При пересчёте — перезаписывать? Или только если `NULL`? Предлагаю всегда перезаписывать при `recalc_all=True`, и только если `NULL` при `recalc_all=False`.
> **Ответ** Давай на UI вынесем чекбокс Recalculate PPM Error в блок Ion Matching Settings, по умолчанию True
---

## 5. Блок 4 — UI: новые параметры Tool Settings

### 5.1 Контекст

В `PeptidesTab._create_tool_settings_controls()` создаются контролы для настроек каждого инструмента. Требуется добавить 4 новых поля.

### 5.2 Что нужно сделать

#### `gui/views/tabs/peptides_tab.py`

В методе `_create_tool_settings_controls(tool)` добавить в возвращаемый словарь:

```python
'min_top_peaks': ft.TextField(
    label="Min Top-10 Peaks Covered",
    value=str(settings.get('min_top_peaks', 1)),
    width=200,
    keyboard_type=ft.KeyboardType.NUMBER
),
'min_ions_covered': ft.TextField(
    label="Min Ions Covered",
    value=str(settings.get('min_ions_covered', 5)),
    width=200,
    keyboard_type=ft.KeyboardType.NUMBER
),
'min_spectre_peaks': ft.TextField(
    label="Min Spectrum Peaks",
    value=str(settings.get('min_spectre_peaks', 10)),
    width=200,
    keyboard_type=ft.KeyboardType.NUMBER
),
'leucine_combinatorics': ft.Checkbox(
    label="Use Leucine Combinatorics (I/L)",
    value=settings.get('leucine_combinatorics', False)
),
```

#### Отображение в UI (layout)

Добавить в блок отображения настроек инструмента (в `refresh_tools`) новую строку:
```
Row([min_top_peaks, min_ions_covered, min_spectre_peaks])
leucine_combinatorics  (отдельная строка)
```

#### `save_tool_settings(tool_id)`

Добавить в словарь `tool.settings`:
```python
'min_top_peaks': int(controls['min_top_peaks'].value),
'min_ions_covered': int(controls['min_ions_covered'].value),
'min_spectre_peaks': int(controls['min_spectre_peaks'].value),
'leucine_combinatorics': controls['leucine_combinatorics'].value,
```

#### `_validate_tool_settings(tool_id)`

Добавить валидацию:
- `min_top_peaks >= 0`
- `min_ions_covered >= 0`
- `min_spectre_peaks >= 0`

#### `run_identification_matching`

В словарь `tool_settings[tool_id]` добавить:
```python
'min_top_peaks': int(controls['min_top_peaks'].value),
'min_ions_covered': int(controls['min_ions_covered'].value),
'min_spectre_peaks': int(controls['min_spectre_peaks'].value),
'leucine_combinatorics': controls['leucine_combinatorics'].value,
```

Эти параметры уже используются в `calculate_preferred_identifications_for_file` (через `tool_params.get(...)`), поэтому достаточно их передать.

---

## 6. Затрагиваемые файлы (сводка)

| Файл | Характер изменений |
|------|--------------------|
| `api/inputs/spectra/mgf.py` | Добавить вычисление `peaks_count` |
| `api/project/mixins/spectra_mixin.py` | Добавить `peaks_count` в INSERT |
| `utils/ppm.py` | Добавить `calculate_theor_mass`, рефакторинг `calculate_ppm` |
| `api/peptides/matching.py` | Заменить `safe_canon_calculate_mass` на `calculate_theor_mass` |
| `api/project/dataclasses.py` | Добавить `charge`, `peaks_count` в `IdentificationWithSpectrum` |
| `api/project/mixins/identification_mixin.py` | Исправить баги в `get_identifications_with_spectra_batch` и `put_identification_data_batch` |
| `api/spectra/ion_match.py` или новый `api/spectra/coverage_worker.py` | Воркер-функция для multiprocessing |
| `gui/views/tabs/peptides_tab.py` | Новые контролы Tool Settings, рефакторинг `_run_coverage_calc` |

---

## 7. Порядок реализации

Предлагаемый порядок работы с учётом зависимостей:

1. **`utils/ppm.py`** — `calculate_theor_mass` + рефакторинг `calculate_ppm` (независимо, является основой для всего остального)
2. **`api/peptides/matching.py`** — замена `safe_canon_calculate_mass` (зависит от п.1)
3. **`api/project/dataclasses.py`** — расширение `IdentificationWithSpectrum`
4. **`api/project/mixins/identification_mixin.py`** — исправление багов
5. **`api/inputs/spectra/mgf.py`** + **`spectra_mixin.py`** — `peaks_count` при импорте (независимо)
6. **`api/spectra/coverage_worker.py`** — воркер-функция (зависит от п.1)
7. **`gui/views/tabs/peptides_tab.py`** — новые контролы + рефакторинг `_run_coverage_calc` (зависит от п.3,4,6)

---

## 8. Открытые вопросы

| # | Вопрос | Предлагаемое решение |
|---|--------|----------------------|
| **Q1** | Какая нотация модификаций в реальных входных данных — `(+42.01)` или `[+42.01]` (ProForma)? Обе? | Уточнить у разработчика; поддержать оба варианта в `calculate_theor_mass` |
| **Q2** | Количество процессов в `multiprocessing.Pool` | `min(os.cpu_count() - 1, 4)`, но нужно подтверждение |
| **Q3** | Фильтрация при `recalc_all=False`: по какому полю определять «не рассчитано» | По `intensity_coverage IS NULL` (как сейчас), т.к. все поля рассчитываются одновременно |
| **Q4** | При пересчёте — перезаписывать поле `ppm`, если оно уже заполнено из файла идентификации? | Да при `recalc_all=True`; нет при `recalc_all=False` |
| **Q5** | `get_identifications_with_spectra_batch` сейчас принимает только `tool_id`. Нужна ли фильтрация по `spectra_file_id`? Или обрабатываем все файлы сразу для данного инструмента? | Уточнить: обработка по tool_id для всего проекта выглядит логичной, но при больших проектах может быть нужен дополнительный параметр |
| **Q6** | Нужно ли пересчитывать `ppm` и для protein match (`matched_ppm` в `peptide_match`), или только для `identification`? | По тексту требований затрагивается только `identification`, `calculate_protein_match_metrics` остаётся как есть |

> **Ответы (для первых 4-х дублирую):**
> A1: считаем что в БД всегда уже ProForma, приведение к нотации - ответственность логики input'ов
> A2: сейчас реализуем без ограничения "сверху", делаем через os.cpu_count()
> A3: intensity_coverage IS NULL
> A4: через дополнительны й флаг
> A5: здесь и так используется batch по количеству строк за раз, отделньый фильтр для файла не нужен
> A6: calculate_protein_match_metrics не трогаем, этот функционал, похоже, ушел в прошлое. Касательно UI: файл peptides_tab на 800+ строк не является актуальным, был выполнен рефакторинг. смотри в gui/views/tabs/peptides/peptides_tab_new.py и импортируемые из него модули

---

## 9. Что НЕ входит в этот этап

- Изменения в CLI
- Изменения в белковых идентификациях или LFQ
- Изменения в схеме БД (поля уже добавлены)
- Новые тесты (пишутся отдельным шагом по команде)
- Изменения в `pyproject.toml`
