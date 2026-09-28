# Cleanup & Review Report — 2026-09-07

Промежуточная задача по `docs/project/spec/CLEANUP_AND_REVIEW.md`: очистка
кода, устранение дублирующих процессов, ruff, review AGENTS.md, поиск
кандидатов на рефакторинг.

---

## 1. Удалённый dead code

### Файлы пакетов (подтверждены grep'ом по всем 4 пакетам — 0 импортов)

| Файл | Причина |
|---|---|
| `dasmixer-core/.../api/inputs/registry_new.py` | точная копия `registry.py` |
| `dasmixer-core/.../api/project/project_spectra_mapping.py` | черновик метода, перенесённого в `SpectraMixin` |
| `dasmixer-core/.../api/project/mixins/fast_ident_match_mixin.py` | класс `IdentificationMatchMixin` не подключён в `Project`, тело `pass` |
| `dasmixer-gui/.../views/tabs/samples_tab.py` (1422 строки) | не импортируется; `samples/__init__.py` использует `samples/samples_tab.py` |
| `dasmixer-gui/.../views/tabs/samples_tab_old.py` | не импортируется |
| `dasmixer-gui/.../views/tabs/peptides_tab.py` (1034 строки) | не импортируется; `peptides/__init__.py` использует `peptides_tab.py` |
| `dasmixer-gui/.../views/tabs/proteins_tab_old.py` | не импортируется |
| `dasmixer-gui/.../views/tabs/peptides/base_section_old.py` | не импортируется |
| `dasmixer-core/.../utils/mq_evidences.py` | 0 импортов нигде (отдельно от `inputs/peptides/MQ_Evidences.py`, который активен) |

### Файлы корня

| Файл | Причина |
|---|---|
| `apply_project_patch.py` | одноразовый sed-скрипт для правки старого `project.py` (до монорепо) |
| `check_ppm.py` | debug-скрипт с хардкод путями |
| `processed_spectra_files.txt` | debug-дамп ID |
| `best_ids.txt` (4.5 МБ) | debug-дамп ID |

### Переименование

- `peptides_tab_new.py` → `peptides_tab.py` (убран вводящий в заблуждение суффикс
  `_new`). Импорт в `peptides/__init__.py` и ссылка в `peptides/README.md`
  обновлены.

### НЕ удалено (требует решения разработчика)

- `pipeline.py`, `export_workflow.py` (корень) — задокументированные примеры
  (`docs/api/pipeline.md`, `docs/api/export_workflow.md`), частично дублируют
  логику CLI. Оставлены как сознательно самостоятельные примеры использования
  `dasmixer-core` без GUI.
- `scripts/inspect_spectra.py` — рабочий diagnostic-скрипт с docstring-usage.

---

## 2. Исправленные баги

### Критичный — runtime crash в CLI (`calculate.py`)

Команды `preferred`, `protein_idents`, `peptides` (full pipeline) падали с
`UnboundLocalError` при запуске без опциональных флагов `--criterion` /
`--min-peptides` / `--min-unique`: параметры замыкались во внутренней
`async def _run()` через присваивание той же переменной без `nonlocal`.

**Файл:** `dasmixer-cli/.../cli/commands/calculate.py`
- `preferred` (стр. ~149): `criterion` → `criterion_val`
- `protein_idents` (стр. ~262): `min_peptides`/`min_unique` → `*_val`
- `peptides` (стр. ~496): `criterion` → `criterion_val`

### Скрытый ImportError в CLI

`calculate.py` импортировал `process_identificatons_batch` из
`dasmixer.api.calculations.spectra.ion_match`, но этой функции в `ion_match.py`
нет (она живёт в `identification_processor.py`). Команды `ion-coverage` и
`peptides` падали с `ImportError` при попытке выполнения. Исправлено: импорт
переведён на правильный модуль `identification_processor`.

### Прочее

- `reporting/base.py:249` — `int(self._project_settings.get('plot_height'))`
  без дефолта → `TypeError` при отсутствии ключа. Добавлен дефолт `800`
  (как у `plot_width`).
- `protein_mixin.py:645` — голый `except:` → `except Exception:`.
- `sample_dialog.py:53` (GUI) — голый `except:` → `except Exception:`.
- Debug `print()` → `logger.debug`/`logging.debug` в:
  `utils/seqfixer_utils.py` (9), `utils/lic.py` (1),
  `mixins/peptide_mixin.py` (2), `peptides/protein_map.py` (1),
  `inputs/peptides/PeptideShaker.py` (8), `spectra/ion_match.py` (1).
- `process_identificatons_batch` → `process_identifications_batch` (typo в
  имени публичной batch-функции). Старое имя оставлено как deprecated alias с
  `DeprecationWarning` для обратной совместимости. Все вызовы в core/CLI/GUI/
  `pipeline.py` обновлены на новое имя.

### sample_status_cache

Удалены неиспользуемые методы из `SampleMixin` (согласно changelog v0.7.0a4 —
они сознательно оставались "для совместимости", но ни разу не вызывались):
`get_cached_sample_stats`, `get_all_cached_sample_stats`,
`upsert_sample_status_cache`, `upsert_sample_status_cache_batch`,
`invalidate_sample_status_cache`, `compute_and_cache_sample_stats`.

Таблица `sample_status_cache` в `schema.py` оставлена с пометкой
`-- DEPRECATED`. **Удаление самой таблицы из схемы — отдельная задача**
(потребует schema migration и bump `PROJECT_VERSION`); разработчик сказал,
что сделает это позже вместе с другими возможными правками схемы.

---

## 3. Оставлено без изменений (требует решения разработчика)

### SQL injection в `set_preferred_identifications_for_file`

`identification_mixin.py:421,424` — f-string подстановка списка ID в SQL:
```python
f"UPDATE identification SET is_preferred = 0 WHERE id IN ({', '.join([str(x) for x in ids])})"
```
**Решение разработчика:** не трогать. Проект работает с локальными файлами
`.dasmix`, защита от SQL-инъекций через параметризацию не критична; у
параметризованного запроса был смысл, но им можно пренебречь. Зафиксировано
здесь для протокола.

### `import plotly.graph_objects as go` на уровне функций (не модуля)

В `reporting/reports/*.py` (`coverage_report.py`, `sample_report.py`,
`toolmatch_report.py`, `upset.py`) `go` используется в type hints на уровне
модуля, но импортируется локально внутри методов. Ruff F821 помечает это как
`Undefined name 'go'`.

**Решение разработчика:** не трогать. Это сознательное решение, позволяющее
установить `dasmixer-core` без `plotly` (графики — опциональная фича). При
необходимости можно использовать строковые аннотации (`"go.Figure"`) или
`TYPE_CHECKING`, но это косметика.

### `select_preferred_identifications` (legacy) в CLI

CLI `calculate.py` (`preferred`, `peptides`) вызывает старую
`select_preferred_identifications` (N+1-запросная версия) из `matching.py`,
тогда как GUI использует новую эффективную `calculate_preferred_identifications_for_file`.

**Не трогаем** — это уже задокументированное и согласованное ранее решение
(см. `docs/project/spec/0.7.1a1_SPEC.md`, `0.7.2a1_SPEC.md`, `0.7.2a2_SPEC.md`):
"Legacy-функция... Не трогаем... вне скоупа задачи". Менять только по
отдельному запросу.

### `print()` в `gui/main.py`

8 `print()` в `gui/main.py` (строки 22, 34, 37, 125, 129, 134, 139, 143) —
это early-bootstrap печать до инициализации логгера и уведомления о загрузке
Kaleido/Chrome. Оставлены: логгер ещё не сконфигурирован, `print` оправдан.

### `print()` в `identification_processor.py:394`

Stderr fallback в worker-процессе при ошибке обработки идентификации —
сознательная печать в stderr, видимая независимо от конфигурации логгера
(в дополнение к `log.error`). Оставлена.

### `print()` в `__main__` блоках

`seqfixer_utils.py:167`, `mqpar_parser.py:124` — self-test блоки
`if __name__ == '__main__':`. Оставлены.

---

## 4. Расхождения процессов CLI vs GUI (наблюдения, не исправлено)

1. **Дедупликация при импорте спектров**: GUI (`import_handlers.py`)
   проверяет `get_spectra_file_by_path()` и поддерживает `on_duplicates`
   (skip/reload/add_as_new). CLI (`mgf_file`/`mgf_pattern`) не проверяет
   дубликаты и не имеет опции `on_duplicates`. Решение: добавить в CLI или
   сознательно оставить (CLI обычно для batch-первичного импорта).

2. **Импорт идентификаций**: GUI использует `pd.merge` для сопоставления
   spectra_id, CLI — `str.map()`. Функционально эквивалентно, но CLI не
   поддерживает `collect_proteins`/stacked import. Низкий приоритет.

3. **Manage Samples View vs Samples Tab**: разная логика получения
   статистики сэмплов (`SampleDataManager` в одном, прямые вызовы
   `project.*` в другом). Не критично, но стоит унифицировать через общий
   `SampleDataManager`.

---

## 5. Ruff

Конфигурации `[tool.ruff]` нет нигде — ruff работает с дефолтными правилами.
`ruff (>=0.16.5,<0.17.0)` объявлен в dev-зависимостях root `pyproject.toml`.

**Применено:** `ruff check --fix` (только safe fixes, без `--unsafe-fixes`) —
**551 фиксов** (сортировка импортов `I001`, устаревший type-hint синтаксис
`UP006/UP035/UP045`, f-string conversion `RUF010`, `PIE790`, `F541`, и т.п.).

**Осталось 382 ошибки**, требующих ручного решения (не автофиксятся):

| Код | Кол-во | Описание |
|---|---|---|
| BLE001 | 214 | blind `except Exception` — проект повсеместно ловит `Exception`, сужать или нет — архитектурное решение |
| F401 | 89 | unused-import (unsafe fix, требует ручной проверки) |
| RUF013 | 34 | implicit-optional |
| F841 | 27 | unused-variable |
| C408 | 22 | unnecessary-collection-call |
| S110 | 15 | try-except-pass |
| SIM118 | 14 | in-dict-keys |
| RUF012 | 14 | mutable-class-default |
| UP037 | 14 | quoted-annotation |
| RUF022 | 14 | unsorted-dunder-all |
| DTZ005 | 13 | call-datetime-now-without-tzinfo |
| F821 | 6 | undefined-name (`go` в reporting/reports — см. п.3, не трогаем) |
| F823 | 0 | (исправлены — UnboundLocalError в CLI) |
| E722 | 0 | (исправлены — 2 голых except) |

**Рекомендация по дальнейшему использованию ruff:** создать секцию
`[tool.ruff]` в root `pyproject.toml` с `target-version = "py311"`,
`line-length`, `extend-select`/`ignore` под нужды проекта (например, отключить
`BLE001`/`S110` если "catch Exception" — сознательная политика, или наоборот
включить и постепенно сужать). Без конфига дефолт слишком шумный для
постоянного CI-использования.

---

## 6. Большие файлы (400+ строк)

После удаления dead code список файлов 700+ строк сократился до 4:

| Строк | Файл | Рефакторинг |
|---|---|---|
| 819 | `api/project/mixins/protein_mixin.py` | Разбить по подобластям: CRUD белков / joined-queries / LFQ-related. Самый приоритетный кандидат. |
| 778 | `gui/views/manage_samples_view/manage_samples_view.py` | Вынести секции аккордеона в отдельные модули (по аналогии с `tabs/samples/`). |
| 736 | `api/calculations/ppm/seqfixer.py` | Возможно вынести PTM-логику в отдельный модуль. Требует осторожности (горячий цикл расчётов). |
| 700 | `gui/app.py` | Роутинг/жизненный цикл — рефакторинг рискованный, только при отдельном запросе. |

Ещё 23 файла в диапазоне 400-700 строк (полный список ниже) — в основном
нормальный размер для доменных модулей (mixins, table_view, sections,
importers). Рефакторинг не предлагается без запроса.

<details>
<summary>Полный список 400-700 строк</summary>

| Строк | Файл |
|---|---|
| 677 | `api/calculations/proteins/sempai/protein.py` |
| 634 | `gui/views/tabs/peptides/tool_settings_section.py` |
| 623 | `gui/components/base_table_view.py` |
| 592 | `api/reporting/base.py` |
| 586 | `api/project/mixins/identification_mixin.py` |
| 582 | `api/calculations/proteins/sempai/prediction.py` |
| 576 | `cli/commands/import_data.py` |
| 548 | `gui/views/tabs/samples/dialogs/import_pattern_dialog.py` |
| 539 | `gui/views/tabs/samples/import_handlers.py` |
| 499 | `api/inputs/peptides/table_importer.py` |
| 487 | `api/calculations/peptides/protein_map.py` |
| 481 | `gui/views/tabs/plots/plots_tab.py` |
| 480 | `api/project/mixins/sample_mixin.py` |
| 459 | `api/project/mixins/joined_peptide_data_mixin.py` |
| 452 | `cli/commands/calculate.py` |
| 451 | `gui/views/settings_view.py` |
| 441 | `gui/views/tabs/peptides/peptide_ion_table_view.py` |
| 434 | `gui/components/base_plot_view.py` |
| 423 | `api/project/mixins/import_project_mixin.py` |
| 421 | `api/calculations/proteins/sempai/algorithms.py` |
| 412 | `gui/views/tabs/reports/report_item.py` |

</details>

---

## 7. AGENTS.md

Обновлено:
- Версия актуализирована (0.5.0 → 0.7.3a1 / PROJECT_VERSION 0.7.2).
- Добавлен `migrations.py` в дерево `api/project/`.
- Добавлен раздел **Changelog** (формат файлов, правило "только по команде
  разработчика").
- Добавлен раздел **Versioning** (`build_tools/set_version.py`, правило "агент
  не меняет версии сам").
- Обновлён список Sample API (убраны удалённые методы `sample_status_cache`,
  добавлена пометка DEPRECATED).
- Добавлено правило 13 про `process_identifications_batch` (новое имя) и
  deprecated alias.

---

## 8. Smoke test

- Импорт всех затронутых модулей (core, cli, gui) — успешно.
- `dasmixer-cli --help`, `dasmixer-cli calculate --help`,
  `dasmixer-cli calculate preferred --help` — работают (раньше `calculate`
  падал с `ImportError`/`UnboundLocalError`).
- `ruff check` после правок — F823/E722 чисто; F821 `go` остался по решению
  разработчика.
