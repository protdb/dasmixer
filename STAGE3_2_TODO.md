# TODO для завершения этапа 3.2

## Критически важно: Добавить метод в Project класс

Необходимо добавить метод `get_spectra_idlist` в класс `Project` в файле `api/project/project.py`.

### Где добавить

После метода `get_spectrum_full` (примерно строка 700), перед комментарием `# Identification file operations`.

### Код для добавления

```python
async def get_spectra_idlist(
    self,
    spectra_file_id: int,
    by: str = "seq_no"
) -> dict[int | str, int]:
    """
    Get mapping from seq_no or scans to spectrum database IDs.
    
    This method is essential for identification import workflow:
    1. Parse identification file (contains seq_no or scans references)
    2. Get mapping: seq_no/scans -> spectrum DB ID
    3. Enrich identification DataFrame with spectre_id
    4. Add identifications to database
    
    Args:
        spectra_file_id: Spectra file ID to get mapping for
        by: Field to use as key - "seq_no" or "scans"
        
    Returns:
        Dict mapping seq_no/scans value to spectrum database ID
        
    Raises:
        ValueError: If 'by' parameter is invalid
        
    Example:
        >>> # After importing spectra file
        >>> mapping = await project.get_spectra_idlist(file_id, by="scans")
        >>> # mapping = {1234: 5, 1235: 6, ...}  scans -> spectrum_id
        >>> 
        >>> # Use in identification import
        >>> ident_df['spectre_id'] = ident_df['scans'].map(mapping)
        >>> await project.add_identifications_batch(ident_df)
    """
    if by not in ("seq_no", "scans"):
        raise ValueError(
            f"Invalid 'by' parameter: {by}. Must be 'seq_no' or 'scans'"
        )
    
    query = f"""
        SELECT id, {by}
        FROM spectre
        WHERE spectre_file_id = ?
        AND {by} IS NOT NULL
    """
    
    rows = await self._fetchall(query, (spectra_file_id,))
    
    # Create mapping: seq_no/scans -> spectrum_id
    return {row[by]: row['id'] for row in rows}
```

Полный код также находится в файле `api/project/project_spectra_mapping.py`.

---

## Что реализовано

### ✅ API и конфигурация
- [x] `api/config.py` - системные настройки
- [x] `api/inputs/__init__.py` - автоматическая регистрация парсеров
- [ ] **ВАЖНО:** Добавить метод `get_spectra_idlist` в `api/project/project.py`

### ✅ Точка входа
- [x] `main.py` - единая точка входа с Typer

### ✅ CLI команды
- [x] `cli/commands/project.py` - создание проекта
- [x] `cli/commands/subset.py` - управление группами (add/delete/list)
- [x] `cli/commands/import_data.py` - импорт данных:
  - mgf-pattern (работает)
  - mgf-file (работает)
  - ident-pattern (заглушка)
  - ident-file (заглушка)

### ✅ GUI компоненты
- [x] `gui/components/plotly_viewer.py` - универсальный просмотр графиков
- [x] `gui/components/progress_dialog.py` - диалог прогресса

### ✅ GUI приложение
- [x] `gui/app.py` - главное приложение с меню
- [x] `gui/views/start_view.py` - стартовый экран
- [x] `gui/views/project_view.py` - контейнер проекта с вкладками

### ✅ GUI вкладки
- [x] `gui/views/tabs/samples_tab.py` - управление образцами и группами (базовая версия)
- [x] `gui/views/tabs/peptides_tab.py` - просмотр идентификаций (заглушка)
- [x] `gui/views/tabs/proteins_tab.py` - заглушка
- [x] `gui/views/tabs/analysis_tab.py` - заглушка

---

## Что осталось доделать

### 1. Добавить метод в Project
- [ ] Добавить `get_spectra_idlist` в `api/project/project.py`

### 2. Доработать GUI - вкладка Samples
- [ ] Создать полноценную таблицу образцов (DataTable)
- [ ] Реализовать выбор и удаление групп
- [ ] Создать диалог импорта данных (`gui/dialogs/import_dialog.py`)
- [ ] Интегрировать импорт спектров через GUI
- [ ] Отображение статуса загрузки

### 3. Доработать GUI - вкладка Peptides
- [ ] Реализовать поиск идентификаций
- [ ] Таблица результатов поиска
- [ ] Интеграция с `plot_matches.py` для отображения графиков
- [ ] Использование `PlotlyViewer` для графиков разметки ионов

### 4. Тестирование CLI
- [ ] Создать тестовые данные (MGF файлы)
- [ ] Протестировать создание проекта
- [ ] Протестировать управление группами
- [ ] Протестировать импорт спектров (pattern и file)

### 5. Тестирование GUI
- [ ] Запуск GUI приложения
- [ ] Создание/открытие проекта
- [ ] Управление группами через GUI
- [ ] Проверка последних проектов

### 6. Интеграция
- [ ] Убедиться что все импорты работают корректно
- [ ] Проверить асинхронные операции
- [ ] Протестировать прогресс-бары

---

## Известные ограничения текущей версии

1. **Импорт данных через GUI** - пока только через CLI
2. **Таблица образцов** - упрощенная версия, нет полного функционала
3. **Идентификации** - нет импорта и просмотра (ждем парсеры)
4. **Графики разметки ионов** - интеграция не завершена

---

## Как протестировать текущую версию

### CLI

```bash
# Создать проект
python main.py test_project.dasmix create

# Добавить группу
python main.py test_project.dasmix subset add --name "Treatment"

# Список групп
python main.py test_project.dasmix subset list

# Импорт MGF файла
python main.py test_project.dasmix import mgf-file \
    --file /path/to/file.mgf \
    --sample-id "Sample1" \
    --group Control
```

### GUI

```bash
# Запуск GUI
python main.py

# Открыть существующий проект
python main.py test_project.dasmix
```

---

## Следующие шаги

1. **Срочно:** Добавить метод `get_spectra_idlist` в Project
2. Завершить диалог импорта для GUI
3. Полностью реализовать вкладку Samples
4. Интегрировать графики в вкладку Peptides
5. Написать интеграционные тесты
6. Протестировать на реальных данных

---

## Вопросы для обсуждения

1. Нужно ли сейчас доделывать полноценный импорт через GUI или можно пока оставить через CLI?
2. Какие тестовые данные будут предоставлены?
3. Нужны ли изменения в структуре GUI?
