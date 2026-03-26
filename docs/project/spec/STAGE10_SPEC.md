# STAGE 10 SPEC: Объединение маппинга белков и расчёта PPM/ion coverage

## Резюме задачи

Текущий пайплайн выполняет маппинг пептидов к белкам и расчёт PPM/coverage отдельными независимыми шагами. Задача этапа — объединить их: при маппинге сразу принимать решение о качестве совпадения, используя SeqFixer для неполных совпадений. Дополнительно добавляется флаг "Save AA substitutions" для сохранения матчей ниже порога с целью анализа аминокислотных замен.

---

## 1. Изменения в схеме данных (таблица `peptide_match`)

### 1.1 Новые колонки

К существующей таблице `peptide_match` добавляются четыре поля:

```sql
matched_peaks        INTEGER   -- аналог ions_matched в identification
matched_top_peaks    INTEGER   -- аналог top_peaks_covered в identification
matched_ion_type     TEXT      -- аналог ion_match_type в identification
matched_sequence_modified TEXT -- заполняется только если get_matched_ppm вернул override с модификациями
substitution         INTEGER   -- BOOLEAN: 1 если запись сохранена как AA-замена (только при save_aa_substitutions=True)
```

**Важно:** миграций и fallback не делаем. Проекты, созданные до этого этапа, будут несовместимы.

### 1.2 Изменения в `api/project/schema.py`

Добавить колонки к `CREATE TABLE peptide_match`:

```sql
matched_peaks INTEGER,
matched_top_peaks INTEGER,
matched_ion_type TEXT,
matched_sequence_modified TEXT,
substitution INTEGER NOT NULL DEFAULT 0
```

### 1.3 Изменения в `api/project/mixins/peptide_mixin.py`

**`add_peptide_matches_batch`**: расширить INSERT-запрос и маппинг колонок — добавить пять новых полей.

**`put_peptide_match_data_batch`**: этот метод становится устаревшим (вся логика переезжает в маппинг), но пока **не удаляем** — может использоваться в Advanced Options.

**`get_peptide_matches_with_spectra`**: метод более не используется в основном пайплайне, но тоже не удаляем.

---

## 2. Изменения в `api/calculations/peptides/protein_map.py`

Это ключевое изменение этапа. Функция `map_proteins` полностью переписывается.

### 2.1 Новая сигнатура

```python
async def map_proteins(
    project: Project,
    tool_settings: dict[int, dict],
    ion_params: dict,               # IonMatchParameters в виде dict (ions, tolerance, mode, water_loss, ammonia_loss)
    fragment_charges: list[int],    # для match_predictions
    seqfixer_params: dict,          # target_ppm, min_charge, max_charge, max_isotope_offset, force_isotope_offset_lookover, ptm_list (per-tool), max_ptm (per-tool)
    batch_size: int = 5000
) -> AsyncIterator[tuple[pd.DataFrame, int, int]]:
```

> **Вопрос 1:** Следует ли передавать `seqfixer_params` как единый словарь для всех инструментов (общие параметры), а PTM-специфичные (ptm_list, max_ptm) брать из `tool_settings`? Я предполагаю так — уточни, если неверно.
> Ответ: да, давай так

### 2.2 Создание SeqFixer

Для каждого инструмента создаётся отдельный экземпляр `SeqFixer`, т.к. у каждого свои ptm_list и max_ptm. Остальные параметры (target_ppm, override_charges, max_isotope_offset, force_isotope_offset_lookover) — общие.

```python
fixer = SeqFixer(
    ptm_list=ptms,
    max_ptm=tool_params.get('max_ptm', 5),
    target_ppm=seqfixer_params['target_ppm'],
    override_charges=(seqfixer_params['min_charge'], seqfixer_params['max_charge']),
    max_isotope_offset=seqfixer_params.get('max_isotope_offset', 2),
    force_isotope_offset_lookover=seqfixer_params.get('force_isotope_offset', False),
)
```

### 2.3 Логика обработки каждой BLAST-строки

При переборе строк blast-результата (текущий цикл `for _, row in blast.iterrows()`) новая логика:

#### Шаг A: определение идентификационных параметров

Для каждой строки нужны данные из таблицы `identification`:
- `sequence` (ProForma, с модификациями) — **нужно добавить в SELECT при получении batch_data**
- `ppm` — ppm для canonical_sequence (уже есть)
- `override_charge` — заряд из identification (уже есть)
- `isotope_offset` — из identification (нужно добавить)
- `intensity_coverage`, `ions_matched`, `top_peaks_covered` — метрики для сравнения (нужно добавить)
- `mz_array`, `intensity_array` — спектральные данные (для неполных совпадений нужны, требуют JOIN к `spectre`)

> **Вопрос 2:** Сейчас `batch_data` получается через `project.get_identifications(...)`, который возвращает не все нужные поля. Предлагаю добавить параметр `include_spectra=True` к этому методу или создать отдельный метод `get_identifications_for_mapping(...)` со всеми нужными полями. Как предпочтительнее?
 
> Ответ: тут важно экономить память. Если последовательности совпали, а может быть и так, что они совпали для всего инструмента (если задан порог identity=1.0), то нет смысла вообще тянуть данные спектров.
> Поэтому здесь я предлагаю сделать отдельный метод в project'е (spectra_mixin) для получения данных спектров по списку ID идентификаций.
> Схема напрашивается такая:
> 1. после мэппинга результатов blast'а обратно к идентификациям выбираем из них те, у которых identity < 1.0
> 2. Для них запрашиваем данные спектров
> 3. Считаем ppm и параметры покрытия ионами
> 4. Смотрим результаты, сохраняем

#### Шаг B: ветвление по Identity

**Случай 1: `identity == 1.0`** (полное совпадение `canonical_sequence == matched_sequence`)

Не выполняем никаких расчётов. Копируем метрики напрямую из `identification`:

```python
result = {
    'protein_id': row['TargetId'],
    'identification_id': int(row['id']),
    'matched_sequence': matched_seq,
    'identity': 1.0,
    'unique_evidence': row['id'] in uq_evidences,
    'matched_ppm': row['ppm'],
    'matched_theor_mass': row['theor_mass'],   # нужно добавить в batch_data
    'matched_peaks': row['ions_matched'],
    'matched_top_peaks': row['top_peaks_covered'],
    'matched_ion_type': row['ion_match_type'],
    'matched_sequence_modified': None,          # нет модификаций поверх
    'substitution': False,
}
```

**Случай 2: `identity < 1.0`** (неполное совпадение)

Вызываем `fixer.get_matched_ppm(...)`:

```python
seq_results = fixer.get_matched_ppm(
    sequence=row['sequence'],         # оригинальная ProForma с PTM-кандидатами
    matched_sequence=matched_seq,     # canonical из BLAST
    pepmass=row['pepmass'],
    charge=eff_charge,               # override_charge или charge из спектра
    isotope_offset=row['isotope_offset'] or 0,
)
```

Выбираем итоговые параметры `SeqMatchParams`:
- Если `seq_results.override` — берём лучший вариант (`_get_best_override` из `identification_processor.py`, критерий — coverage по ионам)
- Если нет override — берём `seq_results.original`

**Корректировка:** если в override больше одной последовательности, рассчитываем мэтчинг для них всех. Берем лучшую по coverage_percent

Рассчитываем ионный мэтчинг для выбранной последовательности:

```python
match_result = match_predictions(
    params=ion_params_obj,
    mz=row['mz_array'],
    intensity=row['intensity_array'],
    charges=fragment_charges,
    sequence=chosen_seq_params.sequence,
)
```

Определяем `matched_sequence_modified`:
- Если выбранная последовательность == `matched_seq` (canonical, без модификаций) → `None`
- Если отличается (есть PTM override) → сохраняем выбранную последовательность

#### Шаг C: Match correction criteria — фильтрация неполных совпадений

Критерии (`match_correction_criteria`) берутся из `tool_settings` для данного инструмента. Набор значений: `ppm`, `intensity_coverage`, `ions_matched`, `top10_ions_matched`.

Маппинг значения критерия → поле сравнения:

| Критерий в настройках | Поле идентификации | Поле мэтча | Направление |
|---|---|---|---|
| `ppm` | `identification.ppm` (abs) | `chosen.abs_ppm` | меньше или равно |
| `intensity_coverage` | `identification.intensity_coverage` | `match_result.intensity_percent` | больше или равно |
| `ions_matched` | `identification.ions_matched` | `match_result.max_ion_matches` | больше или равно |
| `top10_ions_matched` | `identification.top_peaks_covered` | `match_result.top10_intensity_matches` | больше или равно |

Условие добавления матча: **хотя бы один** из выбранных критериев выполнен.

```python
def _check_correction_criteria(criteria: list[str], ident_row: dict, match_ppm: float, match_result: MatchResult) -> bool:
    for c in criteria:
        if c == 'ppm' and abs(match_ppm) <= abs(ident_row['ppm'] or float('inf')):
            # **Примечание**: нужна другая логика проверки, ppm и другие критерии не будут 0/False/None, если его вдруг нет, будет np.nan!
            return True
        if c == 'intensity_coverage' and match_result.intensity_percent >= (ident_row['intensity_coverage'] or 0):
            return True
        if c == 'ions_matched' and match_result.max_ion_matches >= (ident_row['ions_matched'] or 0):
            return True
        if c == 'top10_ions_matched' and match_result.top10_intensity_matches >= (ident_row['top_peaks_covered'] or 0):
            return True
    return False
```

Если критерии не выполнены → матч **не добавляется** (в текущей реализации был жёсткий `abs(match_ppm) >= abs(max_ppm)`, теперь логика более гибкая).

#### Шаг D: Save AA substitutions

Если для инструмента установлен флаг `save_aa_substitutions=True`:
- Даже если критерии Шага C не выполнены — матч всё равно добавляется, но с `substitution=True`
- Условие добавления через substitution-ветку: identification должна соответствовать ограничениям по длине, покрытию и ppm, установленным для инструмента (т.е. is_preferred или соответствует threshold-ам tool_settings)

> **Вопрос 3:** Точнее про condition для substitution-ветки: "identification соответствует ограничениям" — имеется в виду условия фильтрации `get_identifications()` (max_ppm, min_score, min_ion_intensity_coverage, min_peptide_length, max_peptide_length)? Или только некоторые из них? Уточни критерий.

> Ответ: Да, должно быть соответствие всем заданным критериям 

### 2.4 Убрать старую PPM-фильтрацию

Текущая проверка:
```python
if identity < 1.0:
    if abs(match_ppm) >= abs(max_ppm):
        continue
```
Убирается полностью. Вместо неё — логика Шагов C и D.

---

## 3. Изменения в `api/project/mixins/identification_mixin.py`

### 3.1 Метод `get_identifications`

Добавить в SELECT поля, нужные для маппинга:
- `isotope_offset`
- `theor_mass`
- `ions_matched`
- `top_peaks_covered`
- `ion_match_type`

При `include_spectra=True` — добавить JOIN к `spectre` и возвращать `mz_array`, `intensity_array` в колонках (как bytes/BLOB, декомпрессия в protein_map.py).

> **Вопрос 4:** Как лучше передавать массивы спектров в protein_map.py? Варианты:
> - Возвращать в DataFrame как bytes (BLOB), декомпрессировать внутри protein_map при обходе
> - Разделить запросы: отдельный dict `{id: (mz_array, intensity_array)}` для быстрого lookup
> - Создать отдельный метод `get_identifications_for_mapping` возвращающий список dict (как `get_peptide_matches_with_spectra`)
>
> Я склоняюсь к третьему варианту — отдельный метод, возвращающий `list[dict]` с уже декомпрессированными массивами, аналогично `get_peptide_matches_with_spectra`. Это самый явный подход, хотя и самый тяжёлый по памяти.

---

## 4. Изменения в `gui/views/tabs/peptides/tool_settings_section.py`

### 4.1 Новые контролы

В `_create_tool_controls` добавить:

**`match_correction_criteria`** — группа чекбоксов (ft.Checkbox × 4):
```python
'match_correction_ppm': ft.Checkbox(label="PPM", value=True),
'match_correction_intensity': ft.Checkbox(label="Intensity coverage", value=True),
'match_correction_ions': ft.Checkbox(label="Ions matched", value=False),
'match_correction_top10': ft.Checkbox(label="Top 10 ions matched", value=False),
```

**`save_aa_substitutions`** — флаг:
```python
'save_aa_substitutions': ft.Checkbox(
    label="Save AA substitutions",
    value=False,
    tooltip="Save partial matches as amino acid substitution candidates"
),
```

### 4.2 Удаление контролов

В `fasta_section.py` убрать:
- `self.match_preferred_only_cb` (Checkbox "Match preferred only")
- Использование `only_prefered=self.match_preferred_only_cb.value` в вызове `map_proteins()`

В `actions_section.py`:
- Убрать шаг `_calculate_protein_metrics_step()` из `calculate_peptides()`
- Убрать кнопку "Calculate PPM and Coverage for Proteins" из `advanced_panel`
- Убрать вызов `self.parent_tab.ion_calculations.calculate_protein_metrics_internal` из Advanced Options

### 4.3 Обновление `_build_tool_card`

Добавить секцию "Match Correction Criteria" с заголовком и четырьмя чекбоксами, ниже — `save_aa_substitutions`.

### 4.4 Обновление `save_tool_settings` / `get_tool_settings_for_matching`

Сохранять/читать:
```python
'match_correction_criteria': [c for c, cb in {
    'ppm': controls['match_correction_ppm'],
    'intensity_coverage': controls['match_correction_intensity'],
    'ions_matched': controls['match_correction_ions'],
    'top10_ions_matched': controls['match_correction_top10'],
}.items() if cb.value],
'save_aa_substitutions': controls['save_aa_substitutions'].value,
```

---

## 5. Изменения в `gui/views/tabs/peptides/fasta_section.py`

### 5.1 `match_proteins_internal`

Изменить вызов `map_proteins()`:
- Передать `ion_params` (из `state` через ion_settings_section)
- Передать `fragment_charges`
- Передать `seqfixer_params` (из state: target_ppm, min/max charge, isotope params)
- Убрать параметр `only_prefered`

Нужно также убрать из `tool_settings` передачу `only_prefered`.

### 5.2 Убрать вызов `clear_peptide_matches` при identity==1.0

Нет — `clear_peptide_matches` нужно оставить, т.к. мы пересчитываем маппинг целиком.

---

## 6. Изменения в `gui/views/tabs/peptides/actions_section.py`

### 6.1 Упрощение пайплайна

Убрать шаг 3 (`_calculate_protein_metrics_step`) из `calculate_peptides()`. Новый порядок:
1. Match proteins (теперь включает PPM/coverage расчёт)
2. Calculate ion coverage (для идентификаций)
3. Run identification matching

```python
async def calculate_peptides(self, e):
    # Step 1: Match proteins (с встроенным расчётом PPM/coverage)
    await self._run_step("Matching Proteins", self._match_proteins_step())
    await asyncio.sleep(0.5)
    
    # Step 2: Calculate ion coverage for identifications
    await self._run_step("Calculating Ion Coverage", self._calculate_coverage_step())
    await asyncio.sleep(0.5)
    
    # Step 3: Run identification matching
    await self._run_step("Running Identification Matching", self._run_matching_step())
    
    self.show_success("Peptide calculations complete!")
```

---

## 7. Многопоточность и производительность

### 7.1 Текущий подход

Текущий `map_proteins` синхронный (выполняется в async-контексте через `await`), вычисления PPM простые (только `calculate_ppm`/`calculate_theor_mass`).

### 7.2 Новый подход

Расчёт `SeqFixer.get_matched_ppm()` + `match_predictions()` для каждой строки blast — заметно дороже. При больших базах это может быть узким местом.

**Предложение:** вынести обработку blast-строк в `ProcessPoolExecutor` аналогично `run_coverage_calc`. Разбить blast-результаты на sub-batches и запускать параллельно.

> **Вопрос 5:** Нужна ли параллелизация в protein_map уже на этом этапе, или сначала делаем синхронный (однопоточный) вариант и оптимизируем позже? Если делать параллельный сразу — потребуется вынести логику в отдельную функцию-воркер в модуле без DB-импортов (как `coverage_worker.py`).

> Ответ: нет, npysearch работает очень быстро, здесь нет необходимости в дополнительной оптимизации за пределами текущей логики с batch'ами, процент требующих перерасчета идентификаций ожидается небольшой, для них нет нужды усложнять логику, по крайней мере прямо сейчас.

---

## 8. Структура нового модуля-воркера (если параллельно)

Если решено делать параллельно, предлагаю создать `api/calculations/peptides/protein_map_worker.py`:

```python
def process_blast_match_batch(
    batch: list[dict],           # строки blast-результата с данными идентификации и спектров
    ion_params_dict: dict,
    fragment_charges: list[int],
    seqfixer_config: dict,       # ptm_list, max_ptm, target_ppm, etc.
    match_correction_criteria: list[str],
    save_aa_substitutions: bool,
    tool_max_ppm: float,
    tool_min_coverage: float,
    ...
) -> list[dict]:
    """Синхронная функция для ProcessPoolExecutor."""
```

---

## 9. Поток данных (итоговая схема)

```
get_identifications (+ spectra) 
        ↓
   build query dict
        ↓
  npysearch.blast()
        ↓
 for each blast row:
    if identity == 1.0:
        copy metrics from identification → peptide_match record
    else:
        SeqFixer.get_matched_ppm(original_sequence, matched_seq, ...)
        match_predictions(best_seq)
        check match_correction_criteria (any pass?) → add if True
        save_aa_substitutions=True → always add with substitution=True
        (+ ppm filter still applies as fallback if no criteria selected?)
        ↓
 yield pd.DataFrame of results
        ↓
 project.add_peptide_matches_batch(df)
```

---

## 10. Открытые вопросы

**Вопрос 1** (см. §2.1): Параметры SeqFixer — общие для всех инструментов vs per-tool PTM?

> Общий словарь + PTM для инструмента

**Вопрос 2** (см. §2.2, Шаг A): Способ получения данных идентификации со спектрами для маппинга.

> Новый метод в Project через mixin'ы, получаем только данные тех спектров, которые необходимо пересчитать 

**Вопрос 3** (см. §2.2, Шаг D): Точный критерий для substitution-ветки — какие именно ограничения `identification` должны выполняться?

> Все указанные для инструмента

**Вопрос 4** (см. §3.1): Как передавать спектральные массивы из БД в protein_map.

> Новый метод в Project, который позволяет получить спектральные данные по списку ID. На всякий случай проверь, что такого сейчас нет.

**Вопрос 5** (см. §7.2): Параллелизация protein_map на этом этапе или позже?

> Не сейчас

**Вопрос 6** (новый): При identity==1.0 мы копируем `ppm` из `identification`. Но ppm в identification рассчитан для `canonical_sequence` (не для `sequence` с PTM). Это правильное поведение? Или нужно использовать `override_charge` + пересчитать для `matched_sequence`?

> белку сопоставляется всегда каноничная последовательность. Если она нашлась один в один - можно добавить ещё копирование в matched_modified sequence из поля sequence в identification

**Вопрос 7** (новый): Нужно ли обновить отображение данных в `get_joined_peptide_data` (для таблицы пептидов в UI) — добавить в SELECT новые поля `matched_peaks`, `matched_top_peaks`, `matched_ion_type`, `substitution`? И отображать ли их в `PeptideIonTableView`?

> Да, давай обновим. В таблицу добавим как скрытые по умолчанию

**Вопрос 8** (новый): Флаг `match_preferred_only` (`only_prefered`) убирается из UI. Однако в текущем `map_proteins` он передаётся в `get_identifications(only_prefered=...)`. После объединения шагов — маппировать только `is_preferred=True` или все идентификации? Логика подсказывает, что маппировать нужно только preferred (иначе одному спектру может соответствовать несколько белков от разных идентификаций), но это поведение нужно явно закрепить.

> Одному спектру может соответствовать несклоько идентификаций, несколько matched белков, это нормально, их полезно иметь возможность видеть глазами. При использовании логики de novo correction выбор preferred идентификации завязывается на ppm из peptide_match, поэтому мы сначала всем адекватным идентификациям ищем белок, потом уже делаем разметку preferred.

---

## 11. Файлы, затрагиваемые изменениями

| Файл | Тип изменения |
|---|---|
| `api/project/schema.py` | Добавление колонок в `peptide_match` |
| `api/project/mixins/peptide_mixin.py` | `add_peptide_matches_batch` (новые поля), `get_identifications_for_mapping` (новый метод) |
| `api/project/mixins/identification_mixin.py` | `get_identifications` — добавить поля; или новый метод |
| `api/calculations/peptides/protein_map.py` | Полная переработка логики |
| `api/calculations/peptides/protein_map_worker.py` | Новый файл (если параллельно) |
| `gui/views/tabs/peptides/tool_settings_section.py` | Новые контролы, save/load |
| `gui/views/tabs/peptides/fasta_section.py` | Убрать `match_preferred_only_cb`, обновить вызов |
| `gui/views/tabs/peptides/actions_section.py` | Убрать шаг 3, убрать кнопку из Advanced |
