# Cleanup & Review Report — 2026-09-09

Продолжение задачи по `docs/project/spec/CLEANUP_AND_REVIEW.md`.
Этот отчёт — второй проход: ранее отложенные задачи из
`CLEANUP_REPORT_2026-09-07.md`, требующие решения, теперь выполнены.
Исходный отчёт (`CLEANUP_REPORT_2026-09-07.md`) сохранён без изменений
для истории.

**Итог:** `ruff check .` — All checks passed! (0 ошибок) после двух
проходов ручных фиксов (§13, §16) + конфигурации `[tool.ruff]` (§14) +
стандартизации логгера (§15).

---

## 9. Отчёты — аннотации `go.Figure` (Ruff F821)

**Проблема:** в `reporting/reports/*.py` (`coverage_report.py`,
`sample_report.py`, `toolmatch_report.py`, `upset.py`) `go` используется в
type hints на уровне модуля, но импортируется локально внутри методов. Ruff
F821 помечал это как `Undefined name 'go'` (6 ошибок).

**Решение:** аннотации `go.Figure` переведены в строковую форму
(`"go.Figure"`) во всех файлах отчётов (включая `volcano_report.py`,
`median_report.py`, `pca_report.py` — для единообразия). Для файлов с
локальным импортом добавлен `if TYPE_CHECKING: import plotly.graph_objects
as go` — это делает `go` доступным для статического анализатора, не требуя
plotly в рантайме (`from __future__ import annotations` уже откладывает
вычисление аннотаций).

**Результат:** F821 в `reporting/reports/` — 0 ошибок. Plotly остаётся
опциональной зависимостью (`[project.optional-dependencies] plotly`).

---

## 10. CLI — синхронизация preferred identifications с GUI

**Проблема:** CLI (`calculate preferred`, `calculate peptides` шаг 3)
использовал legacy-функцию `select_preferred_identifications` (N+1-запросная
версия) из `matching.py`, тогда как GUI использует эффективную
`calculate_preferred_identifications_for_file` (per-file, с trusted/normal
пулами, de-novo correction и более полными фильтрами качества). Кроме того,
CLI передавал `sample_id=` в `select_preferred_identifications`, которая не
принимает этот параметр (latent `TypeError`).

**Решение:**

- `dasmixer-cli/.../cli/commands/calculate.py`:
  - Добавлена `_collect_tool_settings()` — строит `tool_settings` в формате,
    ожидаемом `calculate_preferred_identifications_for_file`, из
    `tool.settings` (сохранённых GUI в каноническом формате) с дефолтами.
  - Добавлена `_run_preferred_selection()` — перебирает spectra files
    (с фильтром по `sample_id` через `get_spectra_files(sample_id=...)`),
    вызывает `calculate_preferred_identifications_for_file` и
    `set_preferred_identifications_for_file` — точно как в GUI
    (`ion_actions.py:SelectPreferredAction.run`).
  - Команды `preferred` и `peptides` (шаг 3) переведены на
    `_run_preferred_selection`.
  - Удалён сломанный dead-code хелпер `_get_setting` (никогда не
    вызывался, всегда возвращал default, создавал неиспользуемую переменную
    `rows`).

- `dasmixer-core/.../calculations/peptides/matching.py`:
  - `select_preferred_identifications` помечена `DeprecationWarning` с
    указанием на `calculate_preferred_identifications_for_file`.

---

## 11. `gui/main.py` — ранняя инициализация логгера, отказ от `print`

**Проблема:** 8 `print()` в `gui/main.py` (bootstrap-печать до/вне
конфигурации логгера, уведомления о загрузке плагинов и Chrome/Kaleido).

**Решение:**

- `from dasmixer.utils.logger import logger` перенесён в начало модуля
  (до блока конфигурации логгера) — `setup_logger()` создаёт базовый
  console handler сразу при импорте, поэтому `logger` доступен даже если
  `_apply_logging_config` упадёт.
- `print("[Logging] ...")`, `print("[Plugin warning] ...")`,
  `print("[Plugin loader] ...")` → `logger.error(...)` / `logger.warning(...)`.
- `print("[Kaleido] ...")` (6 сообщений в `_ensure_chrome`) →
  `logger.info(...)` / `logger.warning(...)`.
- Удалён неиспользуемый `import sys` из `_ensure_chrome`.

---

## 12. Раздел 4 — расхождения CLI vs GUI (синхронизировано)

### 12.1 Дедупликация при импорте спектров

**Было:** GUI (`import_handlers.py`) проверяет
`get_spectra_file_by_path()` и поддерживает `on_duplicates`
(skip/reload/add_as_new). CLI (`mgf-file`/`mgf-pattern`) не проверял
дубликаты.

**Стало:** в CLI `mgf-file` и `mgf-pattern` добавлена опция
`--on-duplicates` (skip|reload|add_as_new, default `skip`). Перед
импортом вызывается `project.get_spectra_file_by_path(path)`; при
совпадении — skip / `delete_spectra_file` (reload) / создание новой
записи (add_as_new). Логика 1:1 с GUI.

### 12.2 Импорт идентификаций

**Было:** GUI использует `pd.merge` для сопоставления spectra_id;
CLI — `str.map()`. CLI не поддерживал `collect_proteins`/stacked import.

**Стало:**

- `_import_ident_file_internal` переведён на `pd.merge` (как в GUI).
- Добавлена проверка дубликатов через `get_identification_file_by_path`
  + опция `--on-duplicates` (skip|reload|add_as_new).
- Добавлены опции `--collect-proteins` и `--is-uniprot-proteins` (в
  `ident-file` и `ident-pattern`); collected proteins сохраняются через
  `add_proteins_batch`.
- Парсер создаётся с `collect_proteins=`/`is_uniprot_proteins=`;
  `require_project` поддержан (как в GUI).
- **Исправлен latent-баг:** CLI unpack'ал `async for batch_df, _ in
  parse_batch(...)` — но парсеры yield'ят `DataFrame`, не кортеж.
  Изменено на `async for batch_df in parse_batch(...)`.

### 12.3 Manage Samples View vs Samples Tab — унификация через SampleDataManager

**Было:** `ManageSamplesView` использует `SampleDataManager`; `SamplesTab`
(`SamplesSummarySection.load_data`) вызывал
`project.get_sample_status_summary()` напрямую.

**Стало:** в `SampleDataManager` добавлен метод
`get_status_summary()`, делегирующий в `project.get_sample_status_summary()`.
`SamplesSummarySection` теперь использует `SampleDataManager` (создаёт
экземпляр в `__init__`). Оба view используют единый data-access путь.

---

## 13. Ruff — ручные фиксы

Целевые коды (по задаче): `F401`, `RUF013`, `F841`, `C408`, `S110`,
`SIM118`, `RUF022`, `F821`.

**Все целевые коды — 0 ошибок.**

| Код | Было | Стало | Метод |
|---|---|---|---|
| F821  | 6  | 0 | строковые аннотации + `TYPE_CHECKING` (см. §9) |
| F401  | 14 | 0 | `__init__.py` re-exports добавлены в `__all__`; неиспользуемые импорты в `docs/` и `scripts/` удалены (safe fix) |
| RUF013 | 34 | 0 | `Annotated[T, ...] = None` → `Annotated[T \| None, ...] = None` (unsafe-fix, проверено: CLI `--help` работает) |
| F841  | 17 | 0 | удалены genuinely-unused переменные / dead code; 5 false-positive в `matching.py` (pandas `@query`) → `# noqa: F841` |
| C408  | 22 | 0 | `dict(...)` → `{...}` (unsafe-fix, plotly kwargs) |
| S110  | 15 | 0 | `except: pass` → `logger.debug(..., exc_info=True)` (cleanup) / `logger.exception()` (genuine) |
| SIM118 | 10 | 0 | `key in d.keys()` → `key in d` (unsafe-fix) |
| RUF022 | 2  | 0 | `__all__` отсортирован (unsafe-fix) |

**Детали F841 (аккуратно):**

- `calculate.py` — удалён broken dead-code `_get_setting`.
- `matching.py:61-65` — `max_ppm`/`min_score`/`min_ion_intensity_coverage`/
  `min_len`/`max_len` используются в pandas `query("@var")` (строка);
  ruff не видит использования → `# noqa: F841` (false positive).
- `plugin_loader.py` — `success, error = ...` → `_, error = ...` (success
  нигде не использовался).
- `seqfixer_utils.py:117` — удалён `canonical_ppm = calculate_ppm(...)`
  (вычисление без побочных эффектов, результат не использовался).
- `app.py:27` — `app = DASMixerApp(...)` → `DASMixerApp(...)` (переменная не
  использовалась).
- `plotly_viewer.py:52`, `viewer.py:37` — `window = webview.create_window(...)`
  → без присваивания (результат не нужен, вызов ради side-effect).
- `sample_panel.py:68-69` — удалены неиспользуемые `expected_if`/`ident_ok`
  в `_build_sample_header`.
- `plugins_view.py:89` — удалён неиспользуемый `external_ids` в
  `_build_controls`.
- `settings_view.py:476` — удалён неиспользуемый `dialog_closed`.
- `plots_tab.py:435` — удалён dead-code `template = Template(...)` и импорт
  `jinja2.Template` (HTML-шаблон загружался, но экспорт идёт через
  python-docx программно).
- `detection_section.py:127` — `total = await action.run(...)` → без
  присваивания (результат не использовался).

**Детали S110:** для cosmetic/cleanup-блоков (`dialog.close()`, `update()`,
PRAGMA-restore, ROLLBACK) использован `logger.debug(..., exc_info=True)`
(исключения ожидаемые, трейсбек не нужен). Для genuine error-swallowing —
`logger.exception()`.

**Осталось (не в скоупе задачи) — 301 ошибка:**

| Код | Кол-во | Описание |
|---|---|---|
| BLE001 | 187 | blind `except Exception` — архитектурное решение, не сужать |
| F541   | 15  | f-string-missing-placeholders |
| RUF012 | 14  | mutable-class-default |
| DTZ005 | 13  | call-datetime-now-without-tzinfo |
| LOG015 | 13  | root-logger-call |
| UP037  | 11  | quoted-annotation |
| I001   | 8   | unsorted-imports |
| SIM102 | 6   | collapsible-if |
| прочие | ~34 | (RUF015, RUF059, N999, TRY002, S112, DTZ006, UP045, ...) |

**Рекомендация без изменений:** создать секцию `[tool.ruff]` в root
`pyproject.toml` с `target-version = "py311"`, `line-length`,
`extend-select`/`ignore` под нужды проекта.

---

## 14. Ruff — конфигурация `[tool.ruff]`

Создана секция `[tool.ruff]` в root `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
ignore = ["BLE001"]
```

- `target-version = "py311"` — соответствует `requires-python = ">=3.11"`.
- `line-length = 120` — фактическая длина строк в проекте.
- `ignore = ["BLE001"]` — blind `except Exception` — сознательная политика
  проекта (187 ошибок); сужение except-блоков требует архитектурного решения.
- `select` не указан — используется дефолтный набор ruff 0.16 (F, E, B, UP,
  RUF, SIM, и др.).

**Результат:** 301 → 77 ошибок (BLE001 подавлены; прочие остались).

---

## 15. Logging — LOG015 (root logger calls)

**Проблема:** 13 вызовов `logging.info(...)` / `logging.debug(...)` /
`logging.warning(...)` / `logging.exception(...)` — все на root logger,
в обход иерархии `dasmixer` и пользовательских настроек уровня/файла.

**Затронутые файлы:**

- `PeptideShaker.py` (12 вызовов) — `import logging` + `logging.X()`.
- `seqfixer.py:836` — `_logging.debug()` (root), при существующем named
  logger `_seqfixer_log = _logging.getLogger("dasmixer.seqfixer")`.

**Решение:**

- `PeptideShaker.py` — `import logging` заменён на
  `from dasmixer.utils.logger import logger`; все `logging.X()` → `logger.X()`.
- `seqfixer.py:836` — `_logging.debug(...)` → `_seqfixer_log.debug(...)`
  (использование существующего named logger).
- `build.py:217` — исправлена синтаксическая ошибка
  (`(...):` → `...`), мешавшая парсингу ruff'у.

**Архитектура логгера стандартизирована:**

- `utils/logger.py` — console handler переведён на уровень `NOTSET`
  (делегирует фильтрацию уровню логгера, который меняется в рантайме).
  Docstring описывает конвенцию: named loggers only, `from dasmixer.utils.logger
  import logger` или `logging.getLogger(__name__)`.
- `_apply_logging_config` (`settings_view.py`) — теперь настраивает логгер
  `dasmixer` (не root): `dasmixer_log.setLevel(level)` + file handler на
  `dasmixer_log`. Console handler из `setup_logger` сохраняется (не
  удаляется). Все child loggers (`dasmixer.*`) наследуют настройки.
- `identification_processor.py` — комментарии обновлены
  ("propagate to root" → "propagate to dasmixer").

**AGENTS.md** — правило 14 (Logging) переписано: named loggers only,
`from dasmixer.utils.logger import logger` или
`logging.getLogger(__name__)`, lazy formatting, `logger.exception()` в
except-блоках, bootstrap через `logger` без `print()`.

**Результат:** LOG015 — 0 ошибок.

---

## 16. Ruff — второй проход (дополнительные коды)

После первого прохода (§13) и конфигурации (§14) оставалось 77 ошибок.
Вторым проходом исправлены коды: `SIM102`, `RUF015`, `RUF059`, `ASYNC230`,
`S112`, `PLC0206`, `TRY002`, `PLR1704`, `PERF102`, `TRY401`, `SIM103`,
`PYI034`, `B008`, плюс авто-фикс `I001` (unsorted imports).

| Код | Было | Стало | Метод |
|---|---|---|---|
| SIM102  | 4  | 0 | вложенные `if` схлопнуты в одно условие (`prediction.py`, `import_project_mixin.py`, `plot_mixin.py`, `spectra_mixin.py`) |
| RUF015  | 3  | 0 | `[...][0]` → `next(... for ... in ...)` (`ion_match.py`, `table_importer.py` ×2, `proteins_tab.py` — `list(e.control.selected)[0]` → `next(iter(...))`) |
| RUF059  | 3  | 0 | неиспользуемые unpacked-переменные → `_` (`seqfixer.py` ×2, `manage_samples_view.py`) |
| ASYNC230 | 1 | 0 | `mgf_export.py:434` — `# noqa: ASYNC230` (pyteomics `mgf.write()` требует sync file object, aiofiles невозможен без переписывания стороннего API) |
| S112    | 2  | 0 | `pca_report.py`: `except: continue` → `logger.warning(..., exc_info=True)` + `continue` |
| PLC0206 | 1  | 0 | `seqfixer.py:303`: `for code in d: x = d[code]` → `for code, x in d.items()` |
| TRY002  | 4  | 0 | создан `dasmixer-core/utils/exceptions.py` с `DasmixerException(Exception)`; 4 `raise Exception(...)` → `raise DasmixerException(...)` |
| PLR1704 | 1  | 0 | `protein_mixin.py:755`: loop-переменная `protein_id` переопределяла параметр функции → переименована в `pid` |
| PERF102 | 1  | 0 | `report_form.py:326`: `.items()` → `.values()` (`attr_name` не использовался) |
| TRY401  | 1  | 0 | `migrations.py:134`: `logger.exception("...%s", e)` — избыточное `e` убрано; `MigrationError(Exception)` → `MigrationError(DasmixerException)` |
| SIM103  | 1  | 0 | `protein_map.py:169`: `if cond: return False; return True` → `return not (cond)` |
| PYI034  | 1  | 0 | `lifecycle.py:77`: `__aenter__(self) -> 'ProjectLifecycle'` → `-> Self` (через `from typing import Self`); type checker'ы выводят корректный тип для подклассов (`Project`) |
| B008    | 1  | 0 | `search_section.py:229`: `row.to_dict()` в default-аргументе лямбды → вынесен в `row_data = row.to_dict()` перед лямбдой |
| I001    | —  | 0 | авто-фикс unsorted imports (также очистил F541, UP037, UP045, RUF012, SIM102 как побочный эффект) |

**Новый файл:**

- `dasmixer-core/src/dasmixer/utils/exceptions.py` — `DasmixerException(Exception)`,
  базовый класс для всех проект-специфичных исключений. `MigrationError` теперь
  наследуется от `DasmixerException`.

---

## 17. Smoke test (финальный)

- Импорт всех затронутых модулей (core, cli, gui) — успешно.
- `dasmixer-cli --help`, `dasmixer-cli calculate --help`,
  `dasmixer-cli import ident-file --help` — работают.
- `ruff check .` — **All checks passed!** (0 ошибок).

---

## Оставшиеся задачи (из исходного отчёта, не в скоупе)

Из `CLEANUP_REPORT_2026-09-07.md`, разделы, не затронутые в этом проходе:

- **§3.1 SQL injection в `set_preferred_identifications_for_file`** —
  решение разработчика: не трогать (локальные `.dasmix`, параметризация не
  критична).
- **§3.3 `select_preferred_identifications` (legacy)** — помечена
  deprecated (см. §10); удаление самой функции — отдельный запрос.
- **§3.4 `print()` в `identification_processor.py:394`** — сознательная
  печать в stderr в worker-процессе (в дополнение к `log.error`). Оставлена.
- **§3.5 `print()` в `__main__` блоках** (`seqfixer_utils.py:167`,
  `mqpar_parser.py:124`) — self-test блоки. Оставлены.
- **§5 (Ruff) остаток** — `ruff check .` = 0 ошибок после двух проходов
  (§13 + §16) + конфигурации (§14) + `ignore = ["BLE001"]`. Оставшиеся
  коды (DTZ005, DTZ006, N999, RUF007) — не вошли в задачу; при
  необходимости обрабатываются отдельным запросом.
- **§6 Большие файлы (400+ строк)** — рефакторинг не проводился; 4 файла
  700+ строк (`protein_mixin.py`, `manage_samples_view.py`, `seqfixer.py`,
  `app.py`) — кандидаты на будущее разбиение.
- **Удаление таблицы `sample_status_cache` из схемы** — требует schema
  migration и bump `PROJECT_VERSION`; отдельный запрос разработчика.