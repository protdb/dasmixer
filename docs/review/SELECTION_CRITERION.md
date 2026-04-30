# Selection Criterion — Анализ текущего состояния

**Статус:** Отложено (Stage 13, п.10)  
**Дата анализа:** Апрель 2026

Этот документ фиксирует текущее состояние кода по теме выбора критерия при de-novo коррекции последовательностей, а также описывает выявленные проблемы. Реализация доработок отложена для отдельного анализа.

---

## 1. Цепочка параметра seq_criteria

```
ToolSettingsSection.controls['match_correction_*']   (UI чекбоксы)
  └→ save_tool_settings()
       └→ tool.settings['match_correction_criteria']  (list[str] в БД)
            └→ get_tool_settings_for_matching()
                 └→ tool_settings[tool_id]['match_correction_criteria']
                      └→ IonCoverageAction.run()
                           └→ seq_criteria = state.seq_criteria   ← НЕ берётся из tool_settings!
                                └→ process_identificatons_batch(seq_criteria=...)
                                     └→ process_single_ident(selection_criteria=...)
                                          └→ _get_best_override(criteria=...)
```

**Ключевая проблема:** `IonCoverageAction.run()` использует `state.seq_criteria` (глобальный, захардкоженный в `PeptidesTabState` как `'coverage'`), а не значение из `tool.settings['match_correction_criteria']`, которое пользователь настраивает через UI.

---

## 2. Фиксированное значение в shared_state

Файл: `dasmixer/gui/views/tabs/peptides/shared_state.py`, строка 36:

```python
# Sequence selection criteria
seq_criteria: str = 'coverage'
```

Значение `'coverage'` захардкожено и никогда не обновляется из UI или из настроек инструментов.

---

## 3. UI чекбоксы — что хранится и как называется

В `tool_settings_section.py` (строки 183–198) создаются 4 чекбокса:

| Ключ в controls | Label в UI | Значение в tool.settings |
|---|---|---|
| `match_correction_ppm` | "PPM" | `'ppm'` |
| `match_correction_intensity` | "Intensity coverage" | `'intensity_coverage'` |
| `match_correction_ions` | "Ions matched" | `'ions_matched'` |
| `match_correction_top10` | "Top 10 ions matched" | `'top10_ions_matched'` |

Значения по умолчанию (строка 86): `['ppm', 'intensity_coverage']`.

---

## 4. Что ожидает _get_best_override

Файл: `dasmixer/api/calculations/spectra/identification_processor.py`, строки 53–60:

```python
def _get_best_override(
    overrides: list[tuple[SeqMatchParams, MatchResult]], criteria: str
) -> tuple[SeqMatchParams, MatchResult]:
    """Select the best override by primary criterion, then by abs_ppm."""
    if criteria == "coverage":
        criteria = "intensity_percent"
    overrides.sort(key=lambda row: (-getattr(row[1], criteria), row[0].abs_ppm))
    return overrides[0]
```

Функция принимает строку `criteria` и вызывает `getattr(row[1], criteria)` на объекте `MatchResult`.

**Атрибуты `MatchResult`** (из `ion_match.py`):
- `intensity_percent` — % интенсивности покрытых пиков
- `max_ion_matches` — максимальное число совпадающих ионов (серия)
- `top10_intensity_matches` — совпадения в топ-10 пиках по интенсивности
- `top_matched_ion_type` — строка, тип иона (не числовой критерий)

**Атрибуты `SeqMatchParams`** (из `ppm/dataclasses.py`):
- `abs_ppm` — абсолютное значение PPM ошибки
- `ppm`, `charge`, `sequence`, `seq_neutral_mass`, `isotope_offset`

---

## 5. Несоответствие имён

| Что хранит UI / tool.settings | Что ожидает `_get_best_override` | Совпадает? |
|---|---|---|
| `'ppm'` | `'abs_ppm'` (атрибут `SeqMatchParams`) | **НЕТ** |
| `'intensity_coverage'` | `'intensity_percent'` (атрибут `MatchResult`) | **НЕТ** |
| `'ions_matched'` | `'max_ion_matches'` (атрибут `MatchResult`) | **НЕТ** |
| `'top10_ions_matched'` | `'top10_intensity_matches'` (атрибут `MatchResult`) | **НЕТ** |
| `'coverage'` (state default) | `'intensity_percent'` (есть алиас в коде: `if criteria == "coverage": criteria = "intensity_percent"`) | Работает только этот один |

Только встроенный дефолт `'coverage'` корректно обрабатывается через алиас в `_get_best_override`. Все значения из UI сломаны.

---

## 6. Проблема с критерием PPM

Критерий PPM особый: нужно минимизировать `abs_ppm` (не максимизировать как остальные). Текущая сортировка:

```python
overrides.sort(key=lambda row: (-getattr(row[1], criteria), row[0].abs_ppm))
```

Использует `-getattr(row[1], criteria)` (максимизация). Для PPM нужна минимизация `row[0].abs_ppm`, причём PPM — атрибут `SeqMatchParams` (`row[0]`), а не `MatchResult` (`row[1]`). Поэтому текущая сортировка не применима для PPM вообще.

---

## 7. Область применения

**Важно:** `seq_criteria` / `_get_best_override` применяется **только** для de-novo последовательностей, у которых `SeqFixer` генерирует несколько override-вариантов (`seq_results.override`). Для library search (MaxQuant, PLGS) override'ов нет, и `process_single_ident` использует оригинальную последовательность без сравнения вариантов.

Таким образом, проблема актуальна только для инструментов типа `"De Novo"` (PowerNovo2).

---

## 8. Открытые вопросы для будущей реализации

1. **Разделить критерий per-tool или оставить глобальным?** Сейчас `seq_criteria` глобален (`state.seq_criteria`), но в `tool.settings` хранится per-tool. Нужно определить: глобальный критерий для всех de-novo инструментов или каждый инструмент со своим.

2. **Несколько чекбоксов выбрано — как применять?** Если выбраны "Intensity coverage" + "Ions matched" — как комбинировать? Лексикографически (первый по приоритету), взвешенная сумма, или только первый selected?

3. **Нужен ли маппинг имён?** Либо переименовать значения в UI/settings, либо добавить словарь маппинга перед вызовом `_get_best_override`.

4. **Критерий PPM требует отдельной логики** в `_get_best_override` — специальный случай с минимизацией `SeqMatchParams.abs_ppm`.

---

## 9. Предлагаемый путь исправления (для будущей реализации)

1. Определить финальный список критериев и их внутренние имена (соответствующие атрибутам `MatchResult` или `SeqMatchParams`)
2. Обновить `_get_best_override` — добавить обработку PPM как специального случая
3. Добавить маппинг `tool.settings` значений → внутренние имена в `IonCoverageAction.run()`
4. Передавать `seq_criteria` из `tool_settings` в `process_identificatons_batch` (per-tool, не из `state`)
5. Обновить UI labels и значения чекбоксов в соответствии с финальным маппингом
