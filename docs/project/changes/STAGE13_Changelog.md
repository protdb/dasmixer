# STAGE 13 — Мелкие доработки и улучшения интерфейса

**Дата:** Апрель 2026  
**Версия приложения:** 0.1.0  
**Статус:** ✅ Завершено

---

## Обзор

Этап включает серию UI- и backend-улучшений: модальные диалоги прогресса при экспорте, кнопки Select All/Deselect All на вкладке Plots, связывание настроек batch sizes и CPU threads с реальным кодом, добавление настроек логирования, полная переработка диалога импорта по паттерну, вынос загрузки FASTA в модальный диалог, реорганизация кнопок Actions на вкладке Peptides, механизм suspend/resume для блока Tool Settings, доработка диалога параметров отчётов. Пункт 10 (Sequence Selection Criteria) отложен — анализ вынесен в `docs/review/SELECTION_CRITERION.md`.

---

## Задача 1 — Модальный диалог экспорта

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/reports/report_item.py` | Заменён `_show_loading`/`_close_loading` (простой AlertDialog) на `ProgressDialog` с этапами в `_on_export`; удалён legacy `params_field` TextArea; кнопка `params_btn` всегда показывается (disabled с tooltip если нет формы) |
| `dasmixer/gui/views/tabs/reports/reports_tab.py` | `_export_all_to_folder` — добавлен `ProgressDialog` со счётчиком X/N |
| `dasmixer/gui/views/tabs/plots/plots_tab.py` | `_export_plots_to_word` — заменён `show_snack` на `ProgressDialog` с этапами: «Loading plot X/N...», «Rendering PNG...», «Building document...», «Saving...» |
| `dasmixer/gui/components/base_table_view.py` | `_on_export` — добавлен `ProgressDialog` во время сохранения файла |

### Детали

Используется готовый компонент `ProgressDialog` (`dasmixer/gui/views/tabs/peptides/dialogs/progress_dialog.py`) с поддержкой:
- `update_progress(value, title, subtitle, processed, total)`
- `complete(message)`
- `close()`

Диалог `modal=True`, блокирует UI. ProgressBar determinate при многоэтапных операциях, indeterminate при однофайловом экспорте. Кнопка Cancel не показывается (экспорт не прерываемый). При ошибке диалог закрывается, ошибка показывается в `snack_bar`.

---

## Задача 2 — Вкладка Plots: Select All / Deselect All

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/plots/plots_tab.py` | Добавлены кнопки «Select All» и «Deselect All» в `header`; методы `_on_select_all` и `_on_deselect_all` |

### Метод `_on_select_all`
- Перебирает все `PlotItemCard` в `plots_list.controls`
- Устанавливает `card.checkbox.value = True`
- Добавляет все `plot_info["id"]` в `self.selected_ids`
- Вызывает `self.plots_list.update()`

### Метод `_on_deselect_all`
- Устанавливает `card.checkbox.value = False` у каждой карточки
- Очищает `self.selected_ids`
- Вызывает `self.plots_list.update()`

---

## Задача 3 — Привязка Batch Sizes из настроек

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/actions/ion_actions.py` | Удалены хардкод-константы `_BATCH_SIZE = 20000` и `_WORKER_COUNT`; значения читаются из `config` на этапе выполнения (batch_size, max_workers) |
| `dasmixer/gui/actions/protein_map_action.py` | `batch_size` читается из `config.protein_mapping_batch_size` |
| `dasmixer/gui/views/tabs/samples/import_handlers.py` | Batch sizes для импорта MGF и идентификаций читаются из `config` (spectra_batch_size, identification_batch_size) |

### Принцип

Все параметры передаются через GUI-слой (Actions → параметры функций), либо читаются из `config` непосредственно в классе Action (что допустимо). В модулях `dasmixer/api/calculations/` прямые импорты `config` не добавляются (существующие не удаляются).

---

## Задача 4 — Max CPU Threads

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/config.py` | Добавлено поле `max_cpu_threads: int \| None = None` (None = auto: `cpu_count - 1`) |
| `dasmixer/gui/views/settings_view.py` | Добавлена секция «Processing» с полем «Max CPU Threads» (TextField, hint: «Leave empty for auto») |
| `dasmixer/gui/actions/ion_actions.py` | `_WORKER_COUNT` удалён; worker_count вычисляется как `config.max_cpu_threads or max(1, (os.cpu_count() or 2) - 1)` |

---

## Задача 5 — Настройки логирования

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/config.py` | Добавлены поля: `log_to_file: bool = False`, `log_level: str = "INFO"`, `log_folder: str \| None = None`, `log_separate_workers: bool = False` |
| `dasmixer/main.py` | При запуске вызывается `_apply_logging_config(config)` — настройка root logger через `logging.basicConfig` |
| `dasmixer/gui/views/settings_view.py` | Добавлена секция «Logging»: checkbox «Log operations to file», dropdown «Log level» (DEBUG/INFO/WARNING/ERROR), TextField + кнопка Browse для «Logs folder», checkbox «Separate logs for threads»; метод `_browse_log_folder()`; модульная функция `_apply_logging_config(cfg)` для настройки root logger |
| `dasmixer/api/calculations/spectra/identification_processor.py` | Полностью переписан `_get_worker_logger()`: если `log_separate_workers=True` — per-PID файлы в папке логов, иначе — propagate в root logger; если `log_to_file=False` — возвращает no-op логгер |

### Логика worker-логгера

```
config.log_to_file?
├── False → NullHandler (no-op logger)
└── True
    ├── config.log_separate_workers?
    │   ├── True  → FileHandler per PID (worker_{pid}.log) в log_folder
    │   └── False → propagate=True (логи идут в общий root logger)
    └── Уровень логирования: config.log_level
```

---

## Задача 6 — Переработка диалога импорта по паттерну (ImportPatternDialog)

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | **Полностью переписан** (исходный файл был повреждён subagent'ом с битыми отступами, восстановлен вручную) |

### Изменения

- **Прокрутка:** `ft.Column` внутри контейнера заменён на `ft.ListView` (авто-скролл). Снято ограничение на 20 файлов.
- **Чекбоксы:** Каждый элемент списка — `ft.Row` с `ft.Checkbox` (по умолчанию `value=True`), именем файла и редактируемым `ft.TextField` для Sample ID.
- **Датакласс `FileEntry`:** хранит `path: Path`, `sample_id: str`, `included: bool = True`. Список — `self._file_entries`.
- **Кнопки Select All / Deselect All:** добавлены над списком файлов.
- **Tooltip'ы:** для полей «File pattern» и «Sample ID Pattern» добавлены иконки `ft.Icons.HELP_OUTLINE` с tooltip (текст на английском, с примерами glob-синтаксиса и pattern matching с датами).
- **Активность кнопки Import:**
  - `disabled=True` до нажатия Preview Files
  - `disabled=True`, если у любого включённого файла (checkbox=True) пустой Sample ID
  - `disabled=False`, когда Preview выполнен и все включённые файлы имеют Sample ID
- **Передача данных:** `_start_import` передаёт в callback только `FileEntry` с `included=True`, с учётом отредактированных Sample ID.
- Изменения применяются к одному классу `ImportPatternDialog`, используемому и для MGF (`import_type="spectra"`), и для Identifications (`import_type="identifications"`).

---

## Задача 7 — Диалог загрузки FASTA

### Создаваемые файлы

| Файл | Описание |
|---|---|
| `dasmixer/gui/views/tabs/peptides/dialogs/load_fasta_dialog.py` | **Создан** — `LoadFastaDialog`, модальный диалог с Browse → прогресс-режимом во время загрузки |

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/peptides/fasta_section.py` | **Полностью переписан** — кнопка «Load FASTA» открывает `LoadFastaDialog`; удалён чекбокс «Enrich Data from UniProt»; добавлены методы `save_blast_settings()`, `load_blast_settings()`, `match_proteins_internal()` |

### Основная форма `FastaSection` (после изменений)

```
[Protein Sequence Library]
  Кнопка: Load FASTA            ← открывает LoadFastaDialog
  Текст: «N proteins in database»

[Protein Mapping Settings]
  TextField: BLAST Max Accepts
  TextField: BLAST Max Rejects
```

### `LoadFastaDialog`

- TextField (read_only) + Browse для выбора файла
- Checkbox «Sequences in UniProt format»
- Кнопки: «Load» (запускает загрузку), «Cancel»
- После Load — скрываются поля, показывается ProgressRing + статус
- После завершения — диалог закрывается, основная форма обновляет счётчик

---

## Задача 8 — Реорганизация кнопок Actions (вкладка Peptides)

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/peptides/actions_section.py` | **Полностью переписан** — убран `ExpansionPanelList` «Advanced Options»; все кнопки фиксированы: «Calculate Peptides» (зелёная, первая), под заголовком «Advanced» — «Select Preferred» (иконка `ft.Icons.STAR_OUTLINE`), «Calculate Ion Coverage», «Match Proteins», «Save settings» |
| `dasmixer/gui/views/tabs/peptides/ion_settings_section.py` | Добавлен метод `get_selection_criterion()` |
| `dasmixer/gui/views/tabs/peptides/peptides_tab_new.py` | Удалён `MatchingSection` из layout; два вертикальных блока: (1) Ion Matching Settings + Selection Criterion, (2) Actions + Protein Sequence Library |

### Layout после изменений

```
ResponsiveRow:
   Блок 1: [IonSettingsSection]
           + Selection Criterion (RadioGroup, из бывшего MatchingSection)

   Блок 2: [Calculate Peptides]       ← зелёная, самая первая
           -- Advanced --
           [Select Preferred] [Calculate Ion Coverage]
           [Match Proteins]  [Save settings]
           + FastaSection (содержимое из FastaSection)
```

### Удалённые/перемещённые элементы

- Убран `ExpansionPanelList` «Advanced Options» из `ActionsSection`
- Кнопка «Run Identification Matching» → переименована в «Select Preferred» (`icon=ft.Icons.STAR_OUTLINE`), вынесена из `MatchingSection`
- Кнопка «Match Proteins to Identifications» удалена из `FastaSection`
- Класс `MatchingSection` упразднён (файл `matching_section.py` остаётся, но больше не импортируется)

### Кнопка «Save settings»

По нажатию сохраняет:
1. Текущие параметры Ion Matching Settings
2. Текущие параметры Tool Settings (для всех инструментов)
3. BLAST-настройки (max_accepts, max_rejects)

Логика автосохранения при запуске расчётов остаётся неизменной.

---

## Задача 9 — Сворачивание Tool Settings при смене вкладки

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/peptides/tool_settings_section.py` | Добавлены методы `suspend()` и `resume()`; маркер `_tool_settings_suspended`; в `_build_content()` ссылка `_tool_settings_column` на контент |
| `dasmixer/gui/views/project_view.py` | `_collect_suspendable` переписан на duck typing (проверяет наличие `_is_suspended` или `_tool_settings_suspended` маркер-атрибутов, без `isinstance`); `_on_tab_change` — при уходе с вкладки Peptides сохраняет tool settings перед вызовом suspend |

### Метод `suspend()`

1. Вызывает `save_all_tool_settings()` (фоном)
2. Заменяет `self.content` на placeholder: «Tool Settings (suspended)»
3. Удаляет Flet-контролы карточек из дерева
4. Устанавливает `self._tool_settings_suspended = True`

### Метод `resume()`

1. Перестраивает UI из кешированных данных
2. Устанавливает `self._tool_settings_suspended = False`

### Триггер

Срабатывает только при смене главной вкладки ProjectView (Samples/Proteins/Reports/Plots), не при пролистывании внутри PeptidesTab.

---

## Задача 10 — Sequence Selection Criteria (ОТЛОЖЕНО)

### Статус: ⏸️ Deferred

Детальный анализ несоответствий в цепочке «UI → state → processor → `_get_best_override`» вынесен в:

**`docs/review/SELECTION_CRITERION.md`**

Краткое резюме проблем:
- UI-лейблы («PPM», «Intensity coverage», «Ions matched», «Top 10 ions matched») не соответствуют атрибутам `MatchResult`/`SeqMatchParams` в processor
- `seq_criteria` в `PeptidesTabState` глобальный, но в `tool.settings` хранится per-tool — противоречие
- Нет логики для нескольких выбранных критериев (приоритет?)
- Для de-novo и library инструментов критерии должны различаться

Возобновление — после дополнительного анализа на стороне разработчика.

---

## Задача 11 — Доработка диалога параметров Reports

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/reports/report_item.py` | Удалён legacy `params_field` (TextArea fallback для отчётов без формы). Кнопка `params_btn` видна всегда: если `parameters is None` — `disabled=True` + tooltip «This report has no configurable parameters». Высота диалога рассчитывается динамически: `min(80 + n_fields * 80, 550)`, чтобы диалог не растягивался на всю высоту окна при малом числе полей. |

---

## Итоговая таблица изменяемых файлов

| № | Файл | Статус | Задача |
|---|---|---|---|
| 1 | `dasmixer/api/config.py` | Изменён | 4, 5 |
| 2 | `dasmixer/main.py` | Изменён | 5 |
| 3 | `dasmixer/gui/views/settings_view.py` | Изменён | 4, 5 |
| 4 | `dasmixer/gui/actions/ion_actions.py` | Изменён | 3, 4 |
| 5 | `dasmixer/gui/actions/protein_map_action.py` | Изменён | 3 |
| 6 | `dasmixer/gui/views/tabs/samples/import_handlers.py` | Изменён | 3 |
| 7 | `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | **Переписан** | 6 |
| 8 | `dasmixer/gui/views/tabs/reports/report_item.py` | Изменён | 1, 11 |
| 9 | `dasmixer/gui/views/tabs/reports/reports_tab.py` | Изменён | 1 |
| 10 | `dasmixer/gui/views/tabs/plots/plots_tab.py` | Изменён | 1, 2 |
| 11 | `dasmixer/gui/components/base_table_view.py` | Изменён | 1 |
| 12 | `dasmixer/gui/views/tabs/peptides/dialogs/load_fasta_dialog.py` | **Создан** | 7 |
| 13 | `dasmixer/gui/views/tabs/peptides/fasta_section.py` | **Переписан** | 7, 8 |
| 14 | `dasmixer/gui/views/tabs/peptides/actions_section.py` | **Переписан** | 8 |
| 15 | `dasmixer/gui/views/tabs/peptides/ion_settings_section.py` | Изменён | 8 |
| 16 | `dasmixer/gui/views/tabs/peptides/peptides_tab_new.py` | Изменён | 8 |
| 17 | `dasmixer/gui/views/tabs/peptides/tool_settings_section.py` | Изменён | 9 |
| 18 | `dasmixer/gui/views/project_view.py` | Изменён | 9 |
| 19 | `dasmixer/api/calculations/spectra/identification_processor.py` | Изменён | 5 |
| — | `dasmixer/gui/views/tabs/peptides/matching_section.py` | ⚠️ Не используется (удалить позже) | 8 |
| — | `docs/review/SELECTION_CRITERION.md` | **Создан** (анализ) | 10 |

**Итого:** 1 новый файл, 3 полностью переписанных, 15 изменённых. 1 файл помечен к удалению в будущем.

---

## Критические изменения для разработчиков

### ProgressDialog — единый паттерн для прогресса

Все долгие операции с блокировкой UI должны использовать `ProgressDialog`, а не `AlertDialog` + `ProgressRing`. Компонент находится в `dasmixer/gui/views/tabs/peptides/dialogs/progress_dialog.py`.

### Batch sizes и CPU threads

Хардкод `_BATCH_SIZE` и `_WORKER_COUNT` удалён. Значения читаются из `config` при запуске операции (в GUI-слое: Actions/Handlers). В модулях `dasmixer/api/calculations/` прямые импорты `config` не добавляются.

### Suspend/resume

Механизм suspend/resume теперь работает через duck typing (маркер-атрибуты `_is_suspended`, `_tool_settings_suspended`), а не `isinstance`. При добавлении новых сворачиваемых компонентов достаточно:
1. Реализовать `suspend()` и `resume()` с заменой контента на placeholder
2. Установить соответствующий маркер-атрибут
3. Коллектор `_collect_suspendable` в `project_view.py` найдёт компонент автоматически

### ToolSettingsSection

При уходе с вкладки Peptides параметры всех инструментов **сохраняются** перед сворачиванием. При возврате UI перестраивается из кешированных данных, без запроса к БД.

### ImportPatternDialog

Диалог использует `FileEntry` датакласс и `ListView`. Кнопка Import управляется через `disabled=True/False` в зависимости от состояния (Preview выполнен + все Sample ID заполнены).

### MatchingSection

Класс `MatchingSection` упразднён. Файл `dasmixer/gui/views/tabs/peptides/matching_section.py` остаётся на диске, но больше не импортируется. Можно удалить при cleanup.

### Reports — params_btn

Legacy `params_field` (TextArea) удалён. Кнопка `params_btn` всегда присутствует в UI: если у отчёта нет формы (`parameters is None`) — `disabled=True` с tooltip «This report has no configurable parameters». Высота диалога адаптивная, не фиксированная.

---

**Автор:** Goose AI  
**Дата:** Апрель 2026  
**Версия документа:** 1.0