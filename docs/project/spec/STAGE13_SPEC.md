# STAGE 13 — Детальная спецификация доработок

**Статус:** Draft  
**Дата:** Апрель 2026  
**На основе:** `STAGE13_REQUIREMENTS.md`, анализ кода, `MASTER_SPEC_NEW.md`

---

## Содержание

1. [Модальный диалог экспорта](#1-модальный-диалог-экспорта)
2. [Вкладка Plots — кнопка Select All](#2-вкладка-plots--кнопка-select-all)
3. [Окно настроек — Batch sizes](#3-окно-настроек--batch-sizes)
4. [Окно настроек — Max CPU Threads](#4-окно-настроек--max-cpu-threads)
5. [Окно настроек — Логирование](#5-окно-настроек--логирование)
6. [Диалог импорта по паттерну (Samples)](#6-диалог-импорта-по-паттерну-samples)
7. [Вкладка Peptides — диалог загрузки белковых последовательностей](#7-вкладка-peptides--диалог-загрузки-белковых-последовательностей)
8. [Вкладка Peptides — перемещение кнопок Actions](#8-вкладка-peptides--перемещение-кнопок-actions)
9. [Вкладка Peptides — сворачивание Tool Settings](#9-вкладка-peptides--сворачивание-tool-settings)
10. [Вкладка Peptides — Sequence selection criteria](#10-вкладка-peptides--sequence-selection-criteria)
11. [Вкладка Reports — диалог параметров](#11-вкладка-reports--диалог-параметров)
12. [Открытые вопросы](#12-открытые-вопросы)

---

## 1. Модальный диалог экспорта

### 1.1 Описание

Все операции экспорта в приложении должны показывать модальный диалог с индикатором прогресса:
- Экспорт таблиц (XLSX) — из вкладок Peptides, Proteins
- Сохранение графиков (PNG/SVG) — из вкладок Peptides, Proteins
- Экспорт отчётов — вкладка Reports (HTML/DOCX/XLSX)
- Экспорт нескольких графиков в Word — вкладка Plots

### 1.2 Текущее состояние кода

В `plots_tab.py` экспорт в Word (`_export_plots_to_word`) показывает лишь короткий `show_snack`, но не блокирующий диалог. В `report_item.py` (`_on_export`) используется `_show_loading()` — простой `AlertDialog` с `ProgressRing` без статуса. Оба не соответствуют требованиям.

Готовый компонент прогресса: `dasmixer/gui/views/tabs/peptides/dialogs/progress_dialog.py` — `ProgressDialog`. Поддерживает:
- `update_progress(value, title, subtitle, processed, total)` 
- `complete(message)`
- `close()`
- `stop_requested` (флаг для прерывания)

### 1.3 Требуемое поведение

**Общее:**
- Диалог показывается до начала операции, не снимается до завершения
- UI блокируется (modal=True)
- Loader (ProgressRing или ProgressBar) виден постоянно
- Есть строка статуса (что происходит сейчас)
- При многоэтапных операциях или нескольких файлах — счётчик прогресса

**Для экспорта графиков (Plots → Export to Word):**
- Этапы: "Loading plot X/N...", "Rendering PNG X/N...", "Building document...", "Saving..."
- Показывается `ProgressBar` (determinate), значение от 0 до 1
- По завершении — сообщение об успехе с именем файла

**Для экспорта отчётов (Reports → Export):**
- Этапы: "Loading report...", "Exporting HTML...", "Exporting DOCX...", "Exporting XLSX..."
- ProgressBar indeterminate при однофайловом экспорте
- При пакетном экспорте (Export All Selected) — счётчик X/N

### 1.4 Компоненты для изменения

| Файл | Метод | Что изменить |
|---|---|---|
| `plots_tab.py` | `_export_plots_to_word` | Заменить `show_snack` на `ProgressDialog` с этапами |
| `report_item.py` | `_on_export` | Заменить `_show_loading` (без статуса) на `ProgressDialog` с этапами |
| `reports_tab.py` | `_export_all_to_folder` | Добавить `ProgressDialog` с прогрессом по отчётам X/N |

### 1.5 Вопросы к разделу 1

> **Вопрос 1.1:** Требуется ли также диалог прогресса при экспорте таблиц из PeptideIonTableView, ProteinsTab? Там уже есть механизм экспорта, или это пока только "Export to Excel" кнопки, которых ещё нет?

> Ответ: Кнопки есть, Экспорт реализован на уровне BaseTableView, см. `dasmixer/gui/components/base_table_view.py`

> **Вопрос 1.2:** Нужна ли кнопка "Cancel" / "Stop" в диалоге экспорта (аналогично `stoppable=True` в `ProgressDialog` для расчётов), или экспорт всегда доводится до конца?

> Ответ: нет, не нужна, но диалог должен закрываться в случае ошибки, а сама ошибка должна отображаться в snake_bar
---

## 2. Вкладка Plots — кнопка Select All

### 2.1 Текущее состояние

`plots_tab.py` — заголовок (`header`) содержит кнопки "Export Selected to Word" и Refresh. Список `PlotItemCard` хранится в `plots_list` (ListView). Каждый `PlotItemCard` имеет `ft.Checkbox` и метод `_on_plot_selected`. Выбранные ID хранятся в `self.selected_ids: set[int]`.

### 2.2 Реализация

**Добавить в `header` кнопку:**

```python
ft.ElevatedButton(
    content=ft.Text("Select All"),
    icon=ft.Icons.SELECT_ALL,
    on_click=lambda e: self._on_select_all(),
)
```

**Метод `_on_select_all`:**
- Перебрать все карточки `PlotItemCard` в `plots_list.controls`
- Установить `card.checkbox.value = True` у каждой
- Добавить все `plot_info["id"]` в `self.selected_ids`
- Вызвать `self.plots_list.update()`

**Также добавить кнопку "Deselect All"** (снять все отметки), либо сделать одну кнопку-тоггл.

### 2.3 Вопросы к разделу 2

> **Вопрос 2.1:** Нужна ли кнопка "Deselect All" / "Clear Selection", или достаточно только "Select All"? Логично иметь обе.

> Ответ: Пусть будет, давай 
---

## 3. Окно настроек — Batch sizes

### 3.1 Текущее состояние

`settings_view.py` содержит 4 поля `TextField` для batch sizes (spectra, identification, identification_processing, protein_mapping). Значения читаются из `config.*` при построении UI и сохраняются в `config.*` при нажатии Save. **Проблема:** эти значения сохраняются в config, но не передаются в функции, которые реально выполняют батчевую обработку.

**Где используются batch sizes в коде:**

- `ion_actions.py:IonCoverageAction` — `_BATCH_SIZE = 20000` (хардкод, строка 13)
- `protein_map_action.py:MatchProteinsAction` — `batch_size=5000` (хардкод, строка в вызове `map_proteins`)
- `import_handlers.py` — batch_size при импорте MGF и идентификаций

### 3.2 Требуемые изменения

Принцип из требований: **все параметры должны передаваться через GUI, не через прямое обращение к `config` внутри `dasmixer/api/calculations`**.

**Поток данных:**
```
config → GUI (settings_view при старте) → сохранено в config → 
при запуске операции GUI читает config и передаёт параметры явно в Action/функцию
```

**Конкретные изменения:**

1. **`IonCoverageAction.run()`** — добавить параметр `batch_size: int`. В `ion_actions.py` убрать константу `_BATCH_SIZE = 20000`, читать из параметра. В вызывающем коде (ActionsSection / IonCalculations) передавать `batch_size=config.identification_processing_batch_size`.

2. **`MatchProteinsAction.run()`** — добавить параметр `batch_size: int`. Передавать `batch_size=config.protein_mapping_batch_size` из вызывающего кода.

3. **`import_handlers.py`** — импорт MGF и идентификаций: читать `config.spectra_batch_size` и `config.identification_batch_size` в GUI-слое (в `ImportPatternDialog._start_import` или `import_handlers`), передавать как явный аргумент.

4. **В модулях `dasmixer/api/calculations/`** — убрать любые `from dasmixer.api.config import config` (проверить их наличие).

### 3.3 Вопросы к разделу 3

> **Вопрос 3.1:** В `identification_processor.py` логгер пишет в `~/.cache/dasmixer/worker_logs/`. Это значит, что worker-процессы уже имеют косвенную зависимость от файловой системы (не от config). Нужно ли переделать путь к логам на передаваемый параметр, или достаточно сохранить текущее поведение?

> Ответ: Пока сохраняем. Я ещё подумаю над этим функционалом (логирование воркеров), это будет отдельная порция доработок 

> **Вопрос 3.2:** Что считать "модулями `dasmixer/api/calculations`"? Входит ли в запрет прямого config-импорта также `dasmixer/api/inputs/`?

> Ответ: Текущие импорты можно оставить, т.е. сознательно убирать их сейчас не надо - но надо не добавлять. 

---

## 4. Окно настроек — Max CPU Threads

### 4.1 Текущее состояние

В `ion_actions.py`: `_WORKER_COUNT = max(1, (os.cpu_count() or 2) - 1)` — хардкод на уровне модуля (строка 13).  
В `AppConfig` поля `max_cpu_threads` нет.

### 4.2 Требуемые изменения

**В `config.py`:**
```python
max_cpu_threads: int | None = None  # None = auto (cpu_count - 1)
```

**В `settings_view.py` — добавить секцию "Processing":**
- Поле `TextField` "Max CPU Threads" с hint_text "Leave empty for auto (cpu_count - 1)"
- Пустое значение = None = авто
- При сохранении: None если пусто, иначе int > 0

**В `ion_actions.py`:**
```python
# Убрать константу на уровне модуля
# Читать при запуске:
from dasmixer.api.config import config
worker_count = config.max_cpu_threads or max(1, (os.cpu_count() or 2) - 1)
```

Либо, следуя принципу из п.3: передавать `max_workers` явным параметром из GUI.

> Давай при создании конфига/первом запуске определять дефолтное. Вероятно здесь нужен подход с default_factory из Pydantic

### 4.3 Вопросы к разделу 4

> **Вопрос 4.1:** По принципу "проброс через GUI": означает ли это, что `IonCoverageAction.run()` должен принимать `max_workers: int` явным аргументом? Или чтение `config.max_cpu_threads` в `ion_actions.py` допустимо, поскольку это не `dasmixer/api/calculations`?

в Action можно смотреть на конфигурацию 

---

## 5. Окно настроек — Логирование

### 5.1 Текущее состояние

Логгер worker-процессов: `identification_processor.py:_get_worker_logger()` — всегда пишет в `~/.cache/dasmixer/worker_logs/`, уровень DEBUG, без возможности настройки.

В `main.py` и остальном GUI отдельный логгер не настроен (только `print()`).

В `AppConfig` полей для логирования нет.

### 5.2 Требуемые изменения

**В `config.py` — добавить поля:**
```python
log_to_file: bool = False
log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
log_folder: str | None = None  # None = ~/.cache/dasmixer/logs/
```

**В `settings_view.py` — добавить секцию "Logging":**
- `ft.Checkbox` — "Log operations to file" (связан с `log_to_file`)
- `ft.Dropdown` — "Log level" с вариантами: DEBUG, INFO, WARNING, ERROR (связан с `log_level`)
- `ft.TextField` + кнопка Browse папку — "Logs folder" (связан с `log_folder`)

**В `main.py` — при запуске приложения настраивать root logger:**
```python
from dasmixer.api.config import config
import logging

if config.log_to_file:
    log_dir = Path(config.log_folder) if config.log_folder else Path.home() / ".cache" / "dasmixer" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / f"dasmixer_{datetime.now().strftime('%Y%m%d')}.log",
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
```

**Worker-логгер в `identification_processor.py`:**
- Если `config.log_to_file` и `log_folder` заданы → использовать указанную папку
- Уровень брать из `config.log_level`
- Либо: передавать `log_dir` и `log_level` как параметры в `process_identificatons_batch` (тогда это нарушает принцип "не import config в calculations")

### 5.3 Вопросы к разделу 5

> **Вопрос 5.1:** Нужно ли изменять worker-логгер в `identification_processor.py`, чтобы папка и уровень брались из настроек? Если да — передаём через параметры batch-функции (т.е. нужно добавить `log_dir: str | None = None, log_level: str = "DEBUG"` в `process_identificatons_batch`)?

> Давай так. А) привязываем логирование воркеров к общим настройкам системного логера; б) делаем отдельный checkbo в настройках "Separate logs for threads", и если он стоит, то создаются отдельные лог-файлы для воркеров (с общим уровнем логирования), если не стоит - логи воркеров падают в общий лог. 

> **Вопрос 5.2:** Нужен ли единый лог-файл для всего приложения (GUI + workers), или worker-логи остаются отдельными per-PID файлами (как сейчас)?

> См. ответ выше. Делаем опционально - логирование GUI+Workers (если флага нет), логирование воркеров каждого в свой файл если флаг Separte logs for threads стоит

> **Вопрос 5.3:** Должны ли уже существующие `print()` в коде GUI заменяться на `logging.getLogger(__name__).debug(...)` в рамках этой задачи, или это отдельная работа?

> Отдельная, пока print'ы не трогаем 

---

## 6. Диалог импорта по паттерну (Samples)

### 6.1 Текущее состояние

`import_pattern_dialog.py` — список найденных файлов отображается через `ft.ListTile` в `ft.Column` с ограничением в 20 элементов (строка 249: `for file_path, sample_id in found_files[:20]`). Нет прокрутки (колонка вставлена в `ft.Container(height=200)`), нет чекбоксов, нет возможности редактировать Sample ID вручную, кнопка Import всегда активна после предпросмотра.

### 6.2 Требуемые изменения

#### 6.2.1 Прокрутка и чекбоксы

Заменить `ft.Column` внутри контейнера на `ft.ListView` (scroll автоматически). Снять ограничение на 20 файлов.

Каждый элемент списка — `ft.Row` с:
1. `ft.Checkbox` (по умолчанию `value=True`) 
2. `ft.Text` — имя файла
3. `ft.TextField` — поле Sample ID (редактируемое, начальное значение из pattern matching)

**Структура элемента:**
```python
@dataclass
class FileEntry:
    path: Path
    sample_id: str
    included: bool = True
```

Хранить список `FileEntry` в `self._file_entries: list[FileEntry]`.

#### 6.2.2 Активность кнопки Import

Кнопка Import:
- **Неактивна** до выполнения Preview Files
- **Неактивна**, если хотя бы у одного включённого файла (checkbox=True) пустой Sample ID
- **Активна**, когда Preview выполнен и все включённые файлы имеют не пустой Sample ID

Проверка после каждого изменения чекбокса или поля Sample ID.

> И после каждого нажатия Preview files, проблема может быть с параметрами патернов

#### 6.2.3 Подсказки (tooltips)

Для полей "File pattern" и "Sample ID Pattern" добавить иконку-вопрос (`ft.Icons.HELP_OUTLINE`, размер 16, цвет GREY) с `tooltip`:

**File pattern tooltip:**
```
Шаблон поиска файлов с поддержкой glob-синтаксиса.
Примеры:
  *.mgf — все MGF-файлы в папке
  **/*.mgf — рекурсивный поиск
  sample_*.csv — файлы с префиксом
```

**Sample ID pattern tooltip:**
```
Шаблон для извлечения идентификатора образца из имени файла.
Используйте {id} для обозначения части имени, которая станет Sample ID.
Примеры:
  {id}.mgf — для файла "Sample1.mgf" → ID = "Sample1"
  sample_{id}.csv — для "sample_ABC.csv" → ID = "ABC"
  {id}_results.csv — для "S01_results.csv" → ID = "S01"
```

> Здесь два примечания: 1) текст в GUI на английском; 2) в ample ID pattern вставь пример, где в имени файла есть дата и она игнорируется (с символом "*")

**Реализация:**
```python
ft.Row([
    ft.TextField(label="File pattern", ...),
    ft.Tooltip(
        message="...",
        content=ft.Icon(ft.Icons.HELP_OUTLINE, size=16, color=ft.Colors.GREY_600)
    )
], spacing=4)
```

#### 6.2.4 Передача отфильтрованных данных при импорте

`_start_import` — передавать в callback только те файлы, где `FileEntry.included=True`, с учётом отредактированных Sample ID из TextFields.

#### 6.2.5 Применение к обоим типам импорта

Изменения применяются к одному классу `ImportPatternDialog`, который используется как для MGF (import_type="spectra"), так и для Identifications (import_type="identifications").

### 6.3 Вопросы к разделу 6

> **Вопрос 6.1:** Что делать с файлами, у которых pattern matching не смог определить Sample ID (сейчас показывается "UNKNOWN")? Оставлять с пустым полем (и блокировать Import до ввода вручную), или скрывать их из списка автоматически?

> оставлять заблокированными, т.к. именно эти случаи нам и надо отловить и именно во избежание таких случаев нужно блокировать 

> **Вопрос 6.2:** При ручном редактировании Sample ID в поле — нужно ли проверять уникальность, или допустимо импортировать несколько файлов под одним Sample ID (они станут несколькими spectra_files для одного образца)?

> Уникальность не проверяем, может быть несколько файлов на один образец 

> **Вопрос 6.3:** Нужна ли кнопка "Select All / Deselect All" для чекбоксов в списке файлов?

> А давай, пусть будут 

---

## 7. Вкладка Peptides — диалог загрузки белковых последовательностей

### 7.1 Текущее состояние

`fasta_section.py` — блок "Protein Sequence Library" содержит:
- `TextField` для пути к файлу (read_only) + кнопка Browse
- `Checkbox` "Sequences in UniProt format"
- `Checkbox` "Enrich data from UniProt" (`fasta_enrich_uniprot_cb`)
- Кнопка "Load Sequences"
- Текст со статусом/числом белков

### 7.2 Требуемые изменения

#### 7.2.1 Удаление чекбокса "Enrich Data from UniProt"

Удалить `fasta_enrich_uniprot_cb` полностью из UI и из логики `load_fasta_file`. Параметр `enrich_from_uniprot` в `FastaParser` передавать как `False` (или убрать вовсе, если функционал не нужен).

#### 7.2.2 Вынос загрузки файла в модальный диалог

Кнопка "Load FASTA" на основной форме открывает модальный диалог `LoadFastaDialog`. Внутри диалога:

- `TextField` (read_only) + кнопка Browse для выбора файла
- `Checkbox` "Sequences in UniProt format"
- Кнопки: "Load" (запускает загрузку), "Cancel"
- После нажатия Load — диалог переходит в режим прогресса (`ProgressDialog`-style): скрываются поля, показывается `ProgressRing` + строка статуса
- После завершения — диалог закрывается, основная форма обновляет счётчик

**Основная форма `FastaSection` после изменений:**
```
[Protein Sequence Library]
  Кнопка: Load FASTA   ← открывает LoadFastaDialog
  Текст: "N proteins in database" (или "No proteins loaded")

[Protein Mapping Settings]
  TextField: BLAST Max Accepts
  TextField: BLAST Max Rejects
```

**Класс `LoadFastaDialog`** — отдельный класс в `dasmixer/gui/views/tabs/peptides/dialogs/load_fasta_dialog.py`.

### 7.3 Вопросы к разделу 7

> **Вопрос 7.1:** При повторной загрузке FASTA — нужно ли предупреждать пользователя, что существующие белки будут заменены (или добавлены к имеющимся)? Текущая логика использует `add_proteins_batch` — это дополнение или замена?

> Пока не предупреждаем. Логику добавления нескольких файлов (и сохранения белков в принципе) доработаем отдельно 

> **Вопрос 7.2:** Нужно ли после загрузки FASTA автоматически предлагать запустить "Match Proteins"?

> Нет
---

## 8. Вкладка Peptides — перемещение кнопок Actions

### 8.1 Текущее состояние

**`actions_section.py`:** содержит кнопку "Calculate Peptides" (главный workflow) и `ExpansionPanelList` "Advanced Options" с кнопками:
- "Calculate Ion Coverage"
- "Run Identification Matching"  
- "Match Proteins to Identifications"

**`matching_section.py`:** содержит секцию "Preferred Identification Selection" с:
- `RadioGroup` (PPM error / Intensity coverage) — Selection Criterion
- Кнопка "Run Identification Matching" (дубликат из Advanced Options)

**`fasta_section.py`:** содержит кнопку "Match Proteins to Identifications" (дубликат из Advanced Options).

**Текущий layout (`peptides_tab_new.py`):**
```
ResponsiveRow:
  - Column: [ActionsSection, MatchingSection]
  - IonSettingsSection
  - FastaSection
ToolSettingsSection
SearchSection
```

### 8.2 Требуемые изменения

#### 8.2.1 Новый layout

Два вертикальных блока в `ResponsiveRow`:

**Блок 1: Ion Matching Settings**
- Весь контент из `IonSettingsSection` 
- Снизу: "Selection Criterion" (RadioGroup, перенесённый из MatchingSection)

**Блок 2: Actions + Protein Sequence Library**
- Блок Actions (кнопки, фиксированные, не в ExpansionPanel):
  - Кнопка **"Select Preferred"** (иконка `ft.Icons.STAR_OUTLINE`) — переименована из "Run Identification Matching"
  - Кнопка **"Calculate Peptides"** (главная, зелёная) — без изменений
  - Кнопка **"Calculate Ion Coverage"** (была в Advanced Options)
  - Кнопка **"Match Proteins to Identifications"** (была в Advanced Options)
  - Кнопка **"Save settings"** — новая (см. 8.2.3)
- Блок Protein Sequence Library (содержимое из FastaSection после изменений из п.7)

> Зеленую кнопку Calculate Peptides оставляем самой первой, над другими кнопками. Другие кнопки идут под маленьким загловоком "Advanced"

#### 8.2.2 Удаление дублирующих элементов

- Убрать `ExpansionPanelList` "Advanced Options" из `ActionsSection`
- Убрать кнопку "Run Identification Matching" из `MatchingSection` (остаётся только RadioGroup с Selection Criterion, который переносится в блок Ion Settings)
- Убрать кнопку "Match Proteins to Identifications" из `FastaSection`
- Класс `MatchingSection` либо упрощается до хранения только RadioGroup, либо упраздняется

#### 8.2.3 Кнопка "Save settings"

По нажатию кнопки "Save settings":
1. Сохраняются текущие значения из `IonSettingsSection` (в project settings)
2. Сохраняются текущие значения из `ToolSettingsSection` (в tool.settings)
3. Показывается `show_snack` "Settings saved"

Логика сохранения при запуске (автосохранение при каждом запуске расчётов) остаётся неизменной.

#### 8.2.4 Переименование кнопки

`actions_section.py` (или в новом месте): кнопка переименовывается:
- **Было:** "Run Identification Matching" 
- **Стало:** "Select Preferred" с `icon=ft.Icons.STAR_OUTLINE`

### 8.3 Вопросы к разделу 8

> **Вопрос 8.1:** Кнопка "Calculate Peptides" запускает полный workflow (Match Proteins → Ion Coverage → Select Preferred). После перестановки — должны ли отдельные кнопки "Select Preferred", "Calculate Ion Coverage", "Match Proteins to Identifications" быть видны всегда (для ручного запуска каждого шага), или они скрыты за каким-то "Advanced" тоглом?

> Видны всегда. 

> **Вопрос 8.2:** Перемещение `SelectionCriterion` из `MatchingSection` в нижнюю часть `IonSettingsSection` — это означает, что класс `MatchingSection` удаляется полностью? Или он остаётся, но только как держатель RadioGroup?

> Можно удалить целиком для простоты 

> **Вопрос 8.3:** Кнопка "Save settings" сохраняет параметры Ion Matching и Tool Settings. Нужно ли ей также сохранять BLAST-настройки из FastaSection (max_accepts, max_rejects)?

> Да, сохраняем всё 

---

## 9. Вкладка Peptides — сворачивание Tool Settings

### 9.1 Текущее состояние

`ToolSettingsSection` — контейнер с карточками для каждого инструмента. Монтируется в `peptides_tab_new.py` как `self.sections['tool_settings']`. Никакой логики suspend/resume нет. При переходе на другую вкладку `ProjectView` (Proteins, Reports и т.д.) полный Flet-граф остаётся в памяти.

В `project_view.py` реализована логика suspend/resume для `BaseTableAndPlotView` (заменяет содержимое на placeholder при уходе с вкладки).

### 9.2 Требуемые изменения

#### 9.2.1 Механизм suspend/resume для ToolSettingsSection

Реализовать по аналогии с `BaseTableAndPlotView.suspend()` / `BaseTableAndPlotView.resume()`:

**При "сворачивании" (переход на другую вкладку внутри PeptidesTab или уход с PeptidesTab):**
1. Сохраняем параметры всех инструментов (вызываем `save_all_tool_settings()` фоново)
2. Заменяем `self.content` на `ft.Container(height=50, content=ft.Text("Tool Settings (suspended)", color=ft.Colors.GREY_400))`
3. Удаляем Flet-контролы карточек

**При "разворачивании" (возврат):**
1. Восстанавливаем контент из кешированных данных (не перечитывая из БД)
2. Или перестраиваем UI из `state.tool_settings_controls`

#### 9.2.2 Триггер сворачивания

Вариант: сворачивать `ToolSettingsSection` при смене активной вкладки ProjectView. В `project_view.py` в методе `_on_tab_change` добавить вызов suspend/resume для PeptidesTab.

#### 9.2.3 Альтернативный подход

Вместо полного удаления контролов — использовать `ft.ExpansionTile` или просто `visible=False` для `tools_container`. Это проще, но не даёт выигрыша по памяти.

### 9.3 Вопросы к разделу 9

> **Вопрос 9.1:** Сворачивание должно происходить только при переключении на другую главную вкладку (Samples/Proteins/Reports/Plots), или также при переходе внутри PeptidesTab (например, прокрутке к таблице)?

> Только переключение главной вкладки. при пролистывании глубокого смысла в этом нет. 

> **Вопрос 9.2:** Какой уровень оптимизации нужен — просто `visible=False` (быстро, просто), или полное удаление из Flet-дерева (более агрессивно, но сложнее)?

> Удаление из дерева, как для таблиц
---

## 10. Вкладка Peptides — Sequence selection criteria

### 10.1 Текущее состояние

В `tool_settings_section.py` есть контролы `match_correction_ppm`, `match_correction_intensity`, `match_correction_ions`, `match_correction_top10` (строки 183–197). Они сохраняются в `tool.settings['match_correction_criteria']` и передаются в pipeline.

В `identification_processor.py:process_identificatons_batch` параметр `seq_criteria` имеет тип `Literal["peaks", "top_peaks", "coverage"]` (строка 129). Хелпер `_get_best_override` принимает строки: `"coverage"`, `"intensity_percent"`, `"max_ion_matches"`, `"top10_intensity_matches"` (строки 57–59).

В `ion_actions.py`: `seq_criteria = state.seq_criteria` (строка 45 в `run()`), но в `PeptidesTabState` (shared_state.py) нужно проверить, какое значение хранится.

**Несоответствие:** кнопки в UI называются "PPM", "Intensity coverage", "Ions matched", "Top 10 ions matched", но в processor используются строки "peaks", "top_peaks", "coverage". Это и есть "заглушка под один вариант".

### 10.2 Требуемые изменения

#### 10.2.1 Анализ цепочки

Нужно пройти путь параметра от UI до `_get_best_override`:

```
ToolSettingsSection.controls['match_correction_*'] 
  → save_tool_settings → tool.settings['match_correction_criteria']  
  → get_tool_settings_for_matching → tool_settings[tool_id]
  → IonCoverageAction.run → state.seq_criteria
  → process_identificatons_batch(seq_criteria=...)
  → process_single_ident → SeqFixer/MatchResult
  → _get_best_override(criteria=...)
```

#### 10.2.2 Приведение имён в соответствие

Нужно определить корректный маппинг:

| UI label | Текущий код | Правильное значение для `_get_best_override` |
|---|---|---|
| PPM | "ppm" | "abs_ppm" (атрибут SeqMatchParams) — **особый случай**: минимум PPM |
| Intensity coverage | "intensity_coverage" | "intensity_percent" (атрибут MatchResult) |
| Ions matched | "ions_matched" | "max_ion_matches" (атрибут MatchResult) |
| Top 10 ions matched | "top10_ions_matched" | "top10_intensity_matches" (атрибут MatchResult) |

**Текущий `_get_best_override`:** сортирует по `(-getattr(row[1], criteria), row[0].abs_ppm)`. Для "ppm" `row[1]` — это `MatchResult`, у которого нет `abs_ppm`. Нужно специальный случай или другая логика.

#### 10.2.3 Что именно "один вариант"

Вероятно, сейчас `seq_criteria` в `state` захардкожено в одно из значений и не берётся из UI. Нужно:
1. Найти, как `state.seq_criteria` устанавливается (проверить `shared_state.py`)
2. Убедиться, что значение берётся из `tool.settings['match_correction_criteria']` при запуске
3. Если критерий один выбирается из нескольких — уточнить логику (первый выбранный? приоритет?)

### 10.3 Вопросы к разделу 10

> **Вопрос 10.1:** Selection criterion используется для сравнения нескольких override-вариантов при de-novo коррекции (`seq_results.override`). Для library search (без override) этот параметр не применяется. Нужно ли разделить настройку для de-novo и library инструментов?

> **Вопрос 10.2:** Когда выбрано несколько критериев (несколько чекбоксов), как их применять: лексикографически по приоритету, или только первый selected?

> **Вопрос 10.3:** Элемент `seq_criteria` в `PeptidesTabState` — он глобальный для всех инструментов, или per-tool? По логике кода (`state.seq_criteria` один), критерий единый, но в `tool.settings` хранится per-tool. Это противоречие нужно устранить.

> Ответ сразу по всем: давай пока это изменение отложим целиком, его нужно будет чуть подробнее на моей стороне проанализировать. пункт 10 НЕ делаем. Опиши состояние и текущие результаты анализа (вот всё, что по п.10 у тебя тут написано) в отдельный документ docs/review/SELECTION_CRITERION.md и пока забываем.
---

## 11. Вкладка Reports — диалог параметров

### 11.1 Текущее состояние

`report_item.py:_on_open_params` — создаёт `ft.AlertDialog` с фиксированной шириной `container.width = 420`. Высота не задана явно — определяется содержимым. Однако при большом количестве параметров диалог может выходить за границы экрана или вести себя непредсказуемо.

Кнопка Parameters всегда активна (`self.params_btn` создаётся без `disabled=True`), даже если у отчёта нет параметров (`_has_form = False` → params_btn не создаётся). Но при `_has_form = False` кнопки Parameters нет совсем (используется TextArea legacy). Случай "form is present but empty" не обрабатывается отдельно.

### 11.2 Требуемые изменения

#### 11.2.1 Адаптивный размер диалога

Вместо фиксированного размера — динамический по количеству компонентов формы:

**Подход:** `ReportForm.get_container()` возвращает `ft.Container`. Нужно знать число полей формы.

```python
# В report_item.py._on_open_params:
n_fields = len(form_ref.get_values())  # число параметров
height = min(80 + n_fields * 70, 600)  # ~70px на поле, максимум 600
container.height = height
```

Либо: убрать ограничения высоты совсем и позволить AlertDialog растягиваться, добавив `scroll=ft.ScrollMode.AUTO` к content Column в `ReportForm`.

> Не совсем. Сейчас даже если в диалоге 2-3 поля, он растягивается на всю высоту окна и поля разбрасывает по всей высоте. Нужно чтобы было компактнее.

#### 11.2.2 Деактивация кнопки Parameters

Если у отчёта нет параметров (`parameters = None`):
- Кнопка "Parameters" показывается, но `disabled=True`
- Убрать legacy TextArea (params_field) — унифицировать UI

```python
# В report_item._build_content():
self.params_btn = ft.ElevatedButton(
    content=ft.Text("Parameters"),
    icon=ft.Icons.SETTINGS,
    on_click=self._on_open_params,
    disabled=not self._has_form,  # деактивировать если нет формы
)
```

### 11.3 Вопросы к разделу 11

> **Вопрос 11.1:** Нужно ли полностью удалить legacy TextArea (params_field) или оставить его как fallback для отчётов без типизированной формы? Сейчас все встроенные отчёты имеют `parameters` форму или `parameters = None`.

> Давай уберем fallback 

> **Вопрос 11.2:** При `disabled=True` для кнопки Parameters — нужно ли добавить tooltip типа "This report has no configurable parameters"?

> Давай, не повредит 

---

## 12. Открытые вопросы

Сводный список всех вопросов из разделов выше:

### По экспорту (раздел 1)
1. Нужен ли диалог прогресса при экспорте таблиц из PeptideIonTableView, ProteinsTab? _да, на уровне BaseTableView_
2. Нужна ли кнопка Cancel в диалоге экспорта? _Нет_

### По Plots (раздел 2)
3. Нужна ли также кнопка "Deselect All"? _Да_

### По Batch sizes (раздел 3)
4. Нужно ли переделать путь к worker-логам как передаваемый параметр? _Логика сложнее, описана выше_
5. Распространяется ли запрет на прямой import config также на `dasmixer/api/inputs/`? _Существующие не удаляем_

### По CPU threads (раздел 4)
6. `ion_actions.py` — читать config напрямую допустимо, или передавать max_workers явным параметром из GUI? _Допустимо_

### По логированию (раздел 5)
7. Worker-логгер в identification_processor — нужно ли передавать log_dir/log_level как параметры? _Нужно + логика сложнее_
8. Единый лог-файл или per-PID worker-логи? _по выбору, логику описал_
9. Заменять ли существующие `print()` на `logging` в рамках этого этапа? _нет_

### По диалогу импорта (раздел 6)
10. Файлы с неопределённым Sample ID ("UNKNOWN") — оставлять с пустым полем или скрывать? _оставляем, подсвечиваем_
11. Нужна ли проверка уникальности Sample ID? _нет_
12. Нужна ли кнопка "Select All / Deselect All" для чекбоксов в списке файлов? _да_

### По FASTA диалогу (раздел 7)
13. При повторной загрузке — добавление к существующим или замена? _оставляем логику как есть, потом разберемся_
14. Автопредложение запустить "Match Proteins" после загрузки? _нет_

### По Actions (раздел 8)
15. Отдельные кнопки (Select Preferred, Calculate Ion Coverage, Match Proteins) — всегда видны или за "Advanced" тоглом? _всегда видны; отделены подзаголовком_
16. Класс `MatchingSection` — удаляется полностью или упрощается? _удаляется_
17. Кнопка "Save settings" — сохранять ли BLAST-настройки? _да_

### По ToolSettings (раздел 9)
18. Триггер сворачивания — только при смене главной вкладки или также внутри PeptidesTab? _только главной вкладки_
19. Достаточно ли `visible=False` или нужно удаление из Flet-дерева? _удаление_

### По Sequence selection criteria (раздел 10)
20. Разделить критерий для de-novo и library инструментов? _игнорируем п.10_
21. Несколько выбранных критериев — как применять? _игнорируем п.10_
22. `seq_criteria` глобальный или per-tool — нужно устранить противоречие? _игнорируем п.10_

### По Reports dialog (раздел 11)
23. Удалять legacy TextArea или оставлять как fallback? _удалить_
24. Tooltip для деактивированной кнопки Parameters? _да_

---

## Приложение A: Зависимости между задачами

```
Раздел 3 (Batch sizes) → Раздел 4 (CPU threads) [оба требуют изменений config.py и settings_view.py]
Раздел 5 (Logging) → config.py, main.py, identification_processor.py
Раздел 7 (FASTA dialog) → Раздел 8 (Actions layout) [FastaSection меняется в обоих]
Раздел 8 (Actions layout) → Раздел 10 (Sequence criteria) [matching_section может удаляться]
Раздел 1 (Export dialog) → независимо
Раздел 2 (Select All) → независимо
Раздел 6 (Import dialog) → независимо
Раздел 9 (ToolSettings suspend) → зависит от project_view.py
Раздел 11 (Reports dialog) → независимо
```

## Приложение B: Файлы, затрагиваемые изменениями

| Файл | Разделы |
|---|---|
| `dasmixer/api/config.py` | 3, 4, 5 |
| `dasmixer/gui/views/settings_view.py` | 3, 4, 5 |
| `dasmixer/main.py` | 5 |
| `dasmixer/api/calculations/spectra/identification_processor.py` | 3, 5 |
| `dasmixer/gui/actions/ion_actions.py` | 3, 4 |
| `dasmixer/gui/actions/protein_map_action.py` | 3 |
| `dasmixer/gui/views/tabs/plots/plots_tab.py` | 1, 2 |
| `dasmixer/gui/views/tabs/reports/report_item.py` | 1, 11 |
| `dasmixer/gui/views/tabs/reports/reports_tab.py` | 1 |
| `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | 6 |
| `dasmixer/gui/views/tabs/peptides/fasta_section.py` | 7, 8 |
| `dasmixer/gui/views/tabs/peptides/actions_section.py` | 8 |
| `dasmixer/gui/views/tabs/peptides/matching_section.py` | 8, 10 |
| `dasmixer/gui/views/tabs/peptides/ion_settings_section.py` | 8, 10 |
| `dasmixer/gui/views/tabs/peptides/tool_settings_section.py` | 9, 10 |
| `dasmixer/gui/views/tabs/peptides/peptides_tab_new.py` | 8, 9 |
| `dasmixer/gui/views/tabs/peptides/shared_state.py` | 10 |
| `dasmixer/gui/views/project_view.py` | 9 |
| **Новые файлы** | |
| `dasmixer/gui/views/tabs/peptides/dialogs/load_fasta_dialog.py` | 7 |
