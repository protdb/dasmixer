# STAGE 8 SPEC: Доработки PlotView, TableView и логики PPM/разметки ионов

> Документ подготовлен на основе `STAGE8_REQUIREMENTS.md` и анализа кода проекта.  
> Статус: **На согласовании**

---

## 1. Обзор задач

| # | Блок | Затрагиваемые файлы |
|---|------|---------------------|
| 1 | Настройка отображаемых столбцов таблицы | `gui/components/base_table_view.py` |
| 2 | Человекочитаемые заголовки столбцов | `gui/components/base_table_view.py` + все три имплементации |
| 3 | Tooltips в ячейках таблицы | `gui/components/base_table_view.py` + `PeptideIonTableView` |
| 4 | Фильтрация по клику на ячейку + `filter_controls` | `gui/components/base_table_view.py` + `PeptideIonTableView` |
| 5 | Экспорт таблицы в CSV/XLSX | `gui/components/base_table_view.py` + API-миксины |
| 6 | Исправление экспорта графиков | `gui/components/base_plot_view.py` |
| 7 | Предпросмотр графика через WebView | `gui/components/base_plot_view.py`, `gui/components/plotly_viewer.py` |
| 8 | Размер графика 1100×700 | `gui/components/base_plot_view.py`, `gui/components/plotly_viewer.py` |
| 9 | Новый флаг графика пептидов: отображение белковых последовательностей | `gui/views/tabs/peptides/peptide_ion_plot_view.py` |
| 10 | Новые параметры разметки ионов: ignore charges, min/max charge | `gui/views/tabs/peptides/ion_settings_section.py` |
| 11 | Доработка `coverage_worker.py`: использование `calculate_ppm_and_charge` | `api/spectra/coverage_worker.py` |
| 12 | Доработка `map_proteins`: override_charge, PPM с учётом заряда | `api/peptides/matching.py`, `api/project/` (мигсины) |

---

## 2. Блок 1–5: Доработки `BaseTableView`

### 2.1 Настройка отображаемых столбцов (шестерёнка)

**Что добавляем:**  
Кнопку-шестерёнку (`ft.IconButton(icon=ft.Icons.SETTINGS)`) над таблицей.

**Условие доступности:** кнопка `disabled=True`, пока `has_data == False`.

**По нажатию:** открывается `ft.AlertDialog` с чекбоксами — по одному на каждый столбец из последнего полученного датафрейма.

**Логика:**
- При построении таблицы (`_update_table_from_dataframe`) сохраняем полный список столбцов в `self._all_columns: list[str]`.
- Видимые столбцы — в `self._visible_columns: set[str]`; по умолчанию равен `self._all_columns`.
- При повторном рендере таблицы из датафрейма показываем только столбцы из `_visible_columns`.
- `get_data()` **не вызывается повторно** — таблица перестраивается из последнего закэшированного датафрейма `self._last_df`.

**Изменения в `BaseTableView`:**
- Добавить поле `self._last_df: Optional[pd.DataFrame] = None`.
- Добавить поле `self._all_columns: list[str] = []`.
- Добавить поле `self._visible_columns: set[str] = set()`.
- Добавить поле `self._column_settings_button: Optional[ft.IconButton] = None`.
- Добавить метод `_show_column_settings_dialog()`.
- Добавить метод `_apply_column_visibility()` — перестраивает таблицу из `self._last_df`.
- В `_build_ui()` добавить строку над `data_container` с кнопкой-шестерёнкой.
- В `_update_table_from_dataframe` сохранять `self._last_df = df`, заполнять `_all_columns` и `_visible_columns` (если пустой).

---

### 2.2 Человекочитаемые заголовки

**Что добавляем в `BaseTableView`:**
```python
header_name_mapping: dict[str, str] = {}
```
Атрибут класса, переопределяется в подклассах.

**Логика в `_update_table_from_dataframe`:**  
При построении заголовков `ft.DataColumn` берём `header_name_mapping.get(col, col)` вместо `col`.

**Реализация в подклассах:**  
Для каждой из трёх таблиц заполнить словарь, опираясь на поля SQL-схемы:

- `PeptideIonTableView.header_name_mapping` — маппинг технических имён полей `peptide_identification` + связанных таблиц (например: `identification_id → ID`, `spectre_id → Spectrum`, `seq_no → Seq#`, `canonical_sequence → Protein Sequence`, `intensity_coverage → Ion Coverage, %` и т.д.)
- `ProteinIdentificationsTableView.header_name_mapping` — поля `protein_result`/`protein_map`
- `ProteinStatisticsTableView.header_name_mapping` — поля агрегированной статистики

> **Вопрос к разработчику:** Нужен полный список отображаемых столбцов и желаемые названия для каждой таблицы, либо разрешение сформировать их самостоятельно по именам полей.
> **Ответ**: придумай самостоятельно, я потом поправлю в реализации.
---

### 2.3 Tooltips в ячейках

**Что добавляем в `BaseTableView`:**  
Сигнатура `get_data` расширяется опционально:
```python
async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
```
>**Примечание (code style)**: НЕ используй Optional, используй pd.DataFrame | None = None

Второй элемент кортежа — `tooltips_df` или `None`. Столбцы `tooltips_df` совпадают по названию с основным df, строки соответствуют по индексу.

**Логика в `_update_table_from_dataframe`:**  
Принимает дополнительный параметр `tooltips_df: pd.DataFrame | None = None`.  
При наличии `tooltips_df` — при создании `ft.DataCell` вместо `ft.Text(display_value)` создаём `ft.Tooltip(message=tooltip_text, content=ft.Text(display_value))`.
> **Примечание:** нужно учитывать, что для столбца в tooltips_df может не быть соответствующей колонки. Т.е. tooltip опционален. 
> Я бы предложил сделать отдельный метод `get_tooltip(column_name: str, idx: Any) -> str | None` и соответствующую логику заполнения контента ячейки:
```python
tooltip = self.get_tooltip(column, idx)
if tooltip:
    ft.Tooltip(message=tooltip_text, content=ft.Text(display_value))
else:
    ft.Text(display_value)
```
> Это позволит собрать всю логику работы с тултипами в одном методе и обработать все ситуации (нет tooltips_df; он есть, но нет столбца для текущей ячейки; столбец есть, но в нём np.nan вместо значения; есть нормальное значение для тултипа)

**Реализация в `PeptideIonTableView`:**  
В `get_data`:
- Если `sequence` длиннее 31 символа — обрезаем до 30 символов + `"…"` в основном df.
- В `tooltips_df` для столбца `sequence` — полное значение.
- Для остальных столбцов `tooltips_df` не требуется (или `None` в соответствующих ячейках).

**Вопрос:** Обратная совместимость — текущие имплементации возвращают только `DataFrame`. Предлагается оставить возможность возвращать просто `DataFrame` (без кортежа), проверяя тип результата в вызывающем коде. Альтернатива — добавить отдельный метод `get_tooltips_df()`. Какой вариант предпочтителен?
> **Ответ**: не требуется учитывать обратную совместимость, проект ещё не опубликован. Просто вносим правки во все три имплементации и не переживаем на этот счет.


---

### 2.4 Фильтрация по клику на значение в ячейке

**Что добавляем в `BaseTableView`:**
```python
column_filter_mapping: dict[str, str] = {}
# ключ — имя столбца в df (техническое), значение — ключ в self.filter
```

```python
filter_controls: dict[str, ft.Control] = {}
# ключ — ключ фильтра, значение — UI-контрол (Dropdown или TextField)
# заполняется в _build_filter_view() подкласса через регистрацию
```

**Новые методы в `BaseTableView`:**
- `get_filters_from_ui()`: итерируется по `filter_controls`, читает `.value` каждого контрола, обновляет `self.filter`. Вызывается вместо/вместе с `_update_filters_from_ui()`.
- `async set_filters_in_ui(filter_key: str, value)`: устанавливает значение в контрол `filter_controls[filter_key]`, вызывает `_load_table_data()`.

**Логика при клике на ячейку:**  
Если `col` присутствует в `column_filter_mapping` — `ft.DataCell` создаётся с `on_tap` (либо через `ft.GestureDetector`):
```python
on_tap=lambda e, col=col, val=str(value): page.run_task(self.set_filters_in_ui, column_filter_mapping[col], val)
```
Визуально — ячейка выглядит как кликабельная ссылка (цвет, подчёркивание): `ft.Text(display_value, color=ft.Colors.BLUE_600, text_decoration=ft.TextDecoration.UNDERLINE)`.

**Реализация в `PeptideIonTableView`:**
```python
column_filter_mapping = {
    'scans': 'scans',
    'spectre_id': 'spectre_id',
    'identification_id': 'identification_id',
}
```
При инициализации заполнить `filter_controls`:
```python
self.filter_controls = {
    'scans': self.scans_field,
    'spectre_id': self.seq_no_field,  # уточнить маппинг
    'identification_id': self.identification_id_field,
}
```

> **Вопрос к разработчику:** Уточнить, как именно должны регистрироваться `filter_controls` — в `_build_filter_view()` подкласса явным присвоением `self.filter_controls[...] = ...`, или базовый класс предоставляет метод-регистратор? Также нужно уточнить: `spectre_id` и `seq_no` — это одно и то же поле или разные? По коду фильтра они различаются.

> **Ответ:** давай в _build_filter_view() для простоты - это раз; два: spectre_id, seq_no, scans - это три разных идентификатора спектра (spectre_id - глобальный ID в таблице; seq_no - номер спектра в файле; scans - идентификатор спектра в файле по собственной нумерации. Это три разных поля с разными сценариями использования, разные инструменты завязываются на разные поля)
---

### 2.5 Экспорт таблицы в CSV/XLSX

**Что добавляем:**  
Кнопку `Export` рядом с элементами пагинации (в `pagination_row`).

**Диалог экспорта** (`ft.AlertDialog`):
- `ft.RadioGroup` с вариантами `CSV` и `XLSX`
- `ft.Checkbox` "Technical headers" (по умолчанию `False`)
- Кнопки "Export" и "Cancel"

**Логика экспорта:**
1. Запрашиваем данные: `await self.get_data(limit=-1, offset=0)` — без пагинации.
2. Применяем переименование при `technical_headers == False`: `df.rename(columns=self.header_name_mapping)`.
3. Запрашиваем путь через `await ft.FilePicker().save_file(file_name="export.csv", allowed_extensions=["csv"])` (актуальный async API Flet).
4. Сохраняем через pandas: `df.to_csv(path)` или `df.to_excel(path, index=False)`.

**Изменения в API (Project-миксинах):**  
В методах `get_joined_peptide_data`, `get_protein_results_joined`, `get_protein_statistics` — добавить обработку `limit=-1`:
```python
if limit != -1:
    query += f" LIMIT {limit} OFFSET {offset}"
```

> **Вопрос к разработчику:** Для `get_total_count` в `ProteinStatisticsTableView` сейчас возвращается `999999` — это временная заглушка. Нужно ли реализовать настоящий COUNT-запрос в рамках этого этапа?

> **Ответ**: да, давай сразу сделаем
---

## 3. Блок 6–9: Доработки `BasePlotView` и `PlotlyViewer`

### 3.1 Исправление экспорта графиков

**Текущая проблема:**  
В `base_plot_view.py::_on_export` используется устаревший паттерн: `FilePicker` добавляется в `page.overlay`, вызывается `await file_picker.save_file(...)`. По актуальной документации Flet FilePicker больше **не требует добавления в `page.overlay`** — достаточно `await ft.FilePicker().save_file(...)`.

**Что исправить:**
- В `_on_export` заменить:
  ```python
  # Было (некорректно):
  file_picker = ft.FilePicker()
  self.page.overlay.append(file_picker)
  self.page.update()
  result = await file_picker.save_file(...)
  
  # Должно быть:
  result = await ft.FilePicker().save_file(
      file_name=f"plot_{self.current_entity_id}.{format_ext}",
      allowed_extensions=[format_ext]
  )
  ```
- Запись файла: `self.current_figure.write_image(result.path, format=format_ext)` (проверить, что `result` — это `FilePickerResultEvent`, а не строка; в актуальном API `save_file()` возвращает путь как строку либо `None`).

> **Вопрос к разработчику:** Для PNG/SVG экспорта через `figure.write_image()` требуется `kaleido`. Уточнить, добавлена ли зависимость. Если нет — добавить в pyproject.toml.

> **Ответ**: добавлена и используется (отображение графиков внутри модуля уже делается через to_image(), который без kaleido не работает)
---

### 3.2 Предпросмотр через WebView из PlotView

**Что добавить в `BasePlotView`:**  
Кнопку "Preview in WebView" рядом с кнопками Save/Export.

```python
self.webview_button = ft.ElevatedButton(
    content=ft.Text("Preview"),
    icon=ft.Icons.OPEN_IN_NEW,
    on_click=lambda e: self._launch_webview(),
    disabled=True  # активируется после генерации графика
)
```

**Логика `_launch_webview()`:**  
Уже реализована в `PlotlyViewer.launch_interactive()` через `multiprocessing.Process`. Из `BasePlotView` вызвать аналогично:
```python
def _launch_webview(self):
    from gui.components.plotly_viewer import show_webview
    import multiprocessing
    p = multiprocessing.Process(target=show_webview, args=(self.current_figure, self.title))
    p.start()
```

Так как `PlotlyViewer` уже отображает кнопку "Interactive Mode", нужно уточнить: должна ли кнопка "Preview" в `BasePlotView` дублировать её функционал, или речь о вызове WebView непосредственно из блока PlotView (минуя `PlotlyViewer`)?

> **Вопрос к разработчику:** Кнопка "Interactive Mode" уже есть в `PlotlyViewer`, который встраивается в `preview_container` при вызове `_display_plot`. Таким образом, интерактивный режим уже доступен после генерации графика. Нужна ли отдельная кнопка на уровне `BasePlotView`, или достаточно существующей в `PlotlyViewer`? Если дополнительная кнопка всё же нужна — уточнить её расположение (в строке кнопок рядом с Save/Export).
>
> **Ответ**:Кнопка сейчас не отображается на UI. Перепроверь в коде, как она и где. Но при этом в любом случае она должна быть рядом с Save/Export.
---

### 3.3 Размер графика 1100×700

**Изменения в `BasePlotView._display_plot`:**
```python
viewer = PlotlyViewer(
    figure=fig,
    width=1100,   # было 800
    height=700,   # было 500
    ...
)
```

**Изменения в `PlotlyViewer.__init__`:**  
Обновить дефолтные значения: `width: int = 1100`, `height: int = 700`.

---

### 3.4 Флаг отображения последовательностей в белках (график пептидов)

**Что добавить в `PeptideIonPlotView._build_plot_settings_view`:**
```python
self.show_protein_sequences_cb = ft.Checkbox(
    label="Show sequences in proteins",
    value=self.plot_settings.get('show_protein_sequences', False)
)
```

**`get_default_settings`:**
```python
return {
    'show_title': True,
    'show_legend': True,
    'show_protein_sequences': False,
}
```

**`_update_settings_from_ui`:**
```python
self.plot_settings['show_protein_sequences'] = self.show_protein_sequences_cb.value
```

**Логика в `generate_plot`:**  
Если `show_protein_sequences == True` и для спектра есть данные `matched_sequence != canonical_sequence` — вызывать дополнительную функцию отрисовки для `matched_sequence`.

> **Вопрос к разработчику:** Требования упоминают: "для случаев когда `canonical_sequence != matched_sequence` отрисовываем также графики `matched_sequence`" и "В заголов[ке]..." — требования обрезаны. Необходимо уточнить:
> 1. Что именно должно быть в заголовке?
> 2. Оба графика рисуются на одном `Figure` (как subplots) или в отдельных?
> 3. `canonical_sequence` и `matched_sequence` уже присутствуют в данных, возвращаемых `project.get_spectrum_plot_data()`? Если нет — какой метод проекта их предоставляет?

> **Ответ**:
> 1. Формат заголовка: `f'{"★ " if is_preferred else ""}{tool} | {sequence} {"(matched)" if matched_seq else ""} | PPM: {ppm}'`. Сейчас там ещё Score, его убираем.
> 2. Один subplot, показываем все графики
> 3. нет, нужно расширить project.get_spectrum_plot_data(), добавить в сигнатуру - get_matched=False, в теле, опционально, более сложный запрос с left_join к таблице peptide_match 
---

## 4. Блок 10–12: PPM и разметка ионов

### 4.1 Новые параметры разметки ионов в UI

**Файл: `gui/views/tabs/peptides/ion_settings_section.py`**

Добавить три новых элемента управления:

```python
# Чекбокс (по умолчанию включён)
self.ignore_spectre_charges_cb = ft.Checkbox(
    label="Ignore spectre charges",
    value=True
)

# Поля для задания диапазона зарядов
self.min_precursor_charge_field = ft.TextField(
    label="Min precursor charge",
    value="1",
    width=150,
    keyboard_type=ft.KeyboardType.NUMBER
)
self.max_precursor_charge_field = ft.TextField(
    label="Max precursor charge",
    value="4",
    width=150,
    keyboard_type=ft.KeyboardType.NUMBER
)
```

Расположить в `_build_content()` — в отдельной строке `ft.Row` под существующими полями.

**Сохранение/загрузка (`save_settings` / `load_data`):**  
- `ignore_spectre_charges` → ключ `'ignore_spectre_charges'` (bool → `'1'`/`'0'`)
- `min_precursor_charge` → ключ `'min_precursor_charge'` (int → str)
- `max_precursor_charge` → ключ `'max_precursor_charge'` (int → str)

**Синхронизация в `PeptidesTabState`:**  
Добавить поля в `shared_state.py`:
```python
ignore_spectre_charges: bool = True
min_precursor_charge: int = 1
max_precursor_charge: int = 4
```

**`get_ion_match_parameters`:**  
Расширить или добавить отдельный метод `get_charge_parameters() -> dict` для передачи в `coverage_worker`.

---

### 4.2 Доработка `coverage_worker.py`

**Файл: `api/spectra/coverage_worker.py`**

**Сигнатура `process_identification_batch` расширяется:**
```python
def process_identification_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
    ignore_spectre_charges: bool = True,
    min_charge: int = 1,
    max_charge: int = 4,
) -> list[dict]:
```

**Логика расчёта PPM:**  
Заменить текущий блок вычисления `ppm` и `theor_mass`:

```python
from utils.ppm import calculate_ppm_and_charge

if pepmass is None:
    ppm = None
    override_charge = None
    theor_mass = calculate_theor_mass(sequence)
else:
    if not ignore_spectre_charges and charge is not None:
        _min_charge = charge
        _max_charge = charge
    else:
        _min_charge = min_charge
        _max_charge = max_charge
    
    ppm, override_charge, theor_mass = calculate_ppm_and_charge(
        sequence=sequence,
        pepmass=pepmass,
        min_charge=_min_charge,
        max_charge=_max_charge,
    )
```

**Результат:** в возвращаемый словарь добавить поле `override_charge`:
```python
results.append({
    'id': ident_id,
    'ppm': ppm,
    'theor_mass': theor_mass,
    'override_charge': override_charge,   # новое поле
    'intensity_coverage': ...,
    ...
})
```

**Место вызова `process_identification_batch`:**  
Найти место, откуда вызывается воркер (вероятно, в `gui/views/tabs/peptides/ion_calculations.py` или `actions_section.py`) — передать новые параметры из `PeptidesTabState`.

**Место записи результата:**  
Метод `project.put_identification_data_batch()` должен принимать и записывать `override_charge`. Необходимо проверить наличие поля `override_charge` в схеме таблицы идентификаций.

> **Вопрос к разработчику:** Есть ли поле `override_charge` в схеме БД (таблица `peptide_identification`)? Если нет — необходимо добавить миграцию схемы.
> 
> **Ответ**: поле в схему добавлено, миграции не требуются.
---

### 4.3 Доработка `map_proteins` (белковые идентификации)

**Файл: `api/peptides/matching.py`**

**Контекст:**  
Сейчас в `map_proteins` вычисляются:
```python
match_ppm = calculate_ppm(row['TargetMatchSeq'], row['pepmass'], row['charge'])
```
Здесь `row['charge']` — оригинальный заряд спектра. Требуется использовать `override_charge`, если он доступен, и применять `calculate_ppm_and_charge` для случаев, когда заряд неизвестен.

**Изменения в `map_proteins`:**

1. В запросе данных (`get_identifications`) добавить выборку поля `override_charge`:
   ```python
   for _, row in batch_data[['id', 'canonical_sequence', 'pepmass', 'override_charge']].iterrows():
   ```

2. При расчёте `matched_ppm`:
   ```python
   eff_charge = row.get('override_charge') or row.get('charge')
   if eff_charge is not None:
       match_ppm = calculate_ppm(row['TargetMatchSeq'], row['pepmass'], int(eff_charge))
       match_theor_mass = calculate_theor_mass(row['TargetMatchSeq'])
   else:
       match_ppm, _, match_theor_mass = calculate_ppm_and_charge(
           row['TargetMatchSeq'], row['pepmass']
       )
   ```

3. В результирующий словарь записать `matched_theor_mass` (уже есть) и `matched_ppm` (уже есть). Убедиться, что значения корректны.

**Изменения в `project.get_identifications`:**  
Убедиться, что метод возвращает поле `override_charge` из таблицы `peptide_identification`.

> **Вопрос к разработчику:** Требования также упоминают "вынести [логику разметки белковых идентификаций] из gui". Уточнить: имеется в виду, что вся логика batch-обработки для `peptide_match` сейчас находится непосредственно в UI-коде (в каком-то из tab/section файлов)? Нужно ли её вынести в отдельный модуль API, аналогично `coverage_worker.py`? Если да — в какой файл?
> 
> **Ответ**: да, она сейчас внутри логики UI. Давай вынесем это туда же в `coverage_worker` как отдельную функцию 

---

## 5. Вопросы, требующие ответа перед реализацией

| # | Вопрос | Блок | Ответ                                                                       |
|---|--------|------|-----------------------------------------------------------------------------|
| Q1 | Требуемые человекочитаемые названия столбцов для каждой из трёх таблиц: согласовать или предоставить список | Блок 2 | Сформулируй сам                                                             |
| Q2 | Обратная совместимость `get_data`: возвращать `tuple[df, tooltips_df]` или добавить отдельный метод `get_tooltips_df()`? | Блок 3 | никакой обратной совместимости!                                             |
| Q3 | Как регистрировать `filter_controls` в подклассах: явное присвоение в `_build_filter_view` или метод-регистратор в базовом классе? | Блок 4 | явное присвоение в `_build_filter_view`                                     |
| Q4 | Нужна ли полноценная реализация `get_total_count` для `ProteinStatisticsTableView` (сейчас заглушка `999999`)? | Блок 5 | Нужна                                                                       |
| Q5 | Добавлена ли зависимость `kaleido` в `pyproject.toml`? | Блок 6 | Да, всё ОК                                                                  |
| Q6 | Нужна ли кнопка "Preview in WebView" на уровне `BasePlotView`, если `PlotlyViewer` уже показывает "Interactive Mode"? | Блок 7 | Не показывает, по крайней мере сейчас; лучше добавить её в общий ряд кнопок |
| Q7 | Что должно быть в заголовке графика при `show_protein_sequences = True`? На одном Figure или отдельные subplots? | Блок 9 | Тот же Figure |
| Q8 | Есть ли `canonical_sequence` и `matched_sequence` в данных `get_spectrum_plot_data()`? | Блок 9 | Нет, метод нужно доработать |
| Q9 | Есть ли поле `override_charge` в схеме таблицы `peptide_identification` (БД)? | Блок 11 | Да |
| Q10 | Логика batch-обработки `peptide_match` находится в GUI-коде? В каком файле? Нужен ли отдельный модуль API? | Блок 12 | Найди где-то в sections, там напрямую вызывается `match_predictions`. Переносим в coverage_worker |

---

## 6. Структура изменений по файлам

```
gui/
  components/
    base_table_view.py          — столбцы, заголовки, tooltips, filter_controls, экспорт
    base_plot_view.py           — fix FilePicker, webview-кнопка, размер 1100×700
    plotly_viewer.py            — обновить дефолтный размер
  views/tabs/peptides/
    ion_settings_section.py     — 3 новых контрола, сохранение/загрузка
    peptide_ion_table_view.py   — header_name_mapping, tooltips, column_filter_mapping, filter_controls
    peptide_ion_plot_view.py    — флаг show_protein_sequences, логика generate_plot
    shared_state.py             — 3 новых поля
  views/tabs/proteins/
    protein_identifications_table_view.py  — header_name_mapping
    protein_statistics_table_view.py        — header_name_mapping, fix get_total_count
api/
  spectra/
    coverage_worker.py          — новые параметры, calculate_ppm_and_charge, override_charge
  peptides/
    matching.py                 — override_charge в map_proteins
  project/
    mixins/ (идентификации)     — limit=-1, возврат override_charge
```
