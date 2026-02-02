# Stage 3.3 Quick Start Guide

## Что реализовано

Вкладка **Peptides** с 5 блоками функциональности:

### 1. Загрузка FASTA библиотеки ✅
- Выбор .fasta/.fa файлов
- Поддержка UniProt формата
- Опция обогащения из UniProt (заглушка)
- Progress indicator
- Сохранение в таблицу `protein`

### 2. Настройки инструментов ✅
Для каждого tool:
- Max PPM (50)
- Min Score (0.8)
- Min Ion Intensity Coverage (25%)
- Use protein from file (checkbox)
- Min Protein Identity (0.75)
- DeNovo correction (checkbox)

Хранится в `tool.settings` (JSON)

### 3. Настройки ионов ✅
- Ion types: a, b, c, x, y, z (по умолчанию: b, y)
- Losses: H₂O, NH₃
- PPM Threshold (20)

Хранится в `project_settings`

### 4. Выбор оптимальной идентификации ✅
- Критерий: PPM error / Intensity coverage
- Кнопка "Run Identification Matching"
- Вызывает `select_preferred_identifications()` (заглушка)

### 5. Поиск и просмотр ✅
- Фильтры: Sample, Tool
- Поиск по: seq_no, scans, sequence, canonical_sequence
- Таблица результатов с preferred маркером
- График спектра с последовательностью

## Быстрый тест

```bash
# Запустить интеграционные тесты
python test_stage3_3.py

# Все тесты должны пройти:
# ✓ FASTA validation
# ✓ FASTA parsing
# ✓ Protein storage
# ✓ Tool settings storage
# ✓ Ion settings storage
# ✓ Invalid file handling
```

## Тестовые данные

`TEST_DATA/test.fasta` - 5 белков в UniProt формате

## Основные файлы

**API:**
- `api/inputs/proteins/fasta.py` - парсер FASTA
- `api/peptides/matching.py` - функция matching (TODO)
- `api/spectra/plot_matches.py` - визуализация спектра

**GUI:**
- `gui/views/tabs/peptides_tab.py` - вкладка Peptides (900+ строк)

**Тесты:**
- `test_stage3_3.py` - интеграционные тесты
- `TEST_DATA/test.fasta` - тестовые данные

## Что делать дальше

### Для разработчика (этап 4):

Реализовать `api/peptides/matching.py`:

```python
async def select_preferred_identifications(
    project: Project,
    criterion: str,  # "ppm" or "intensity"
    ion_settings: dict,
    tool_settings: dict[int, dict]
) -> int:
    # TODO: Implement
    # 1. Generate theoretical fragments
    # 2. Match peaks with PPM threshold
    # 3. Calculate intensity coverage
    # 4. Select best by criterion
    # 5. Update is_preferred in DB
    pass
```

Реализовать `api/spectra/plot_matches.py` - полную разметку ионов:

```python
def plot_ion_match(...) -> go.Figure:
    # TODO: Implement
    # 1. Match theoretical fragments to peaks
    # 2. Annotate matched peaks
    # 3. Color-code by ion type
    pass
```

### Для агента (этап 5):

- Интеграция pywebview для интерактивных графиков
- GUI для белковых идентификаций
- GUI для отчётов

## Известные ограничения

1. UniProt enrichment - только заглушка
2. Повторная загрузка FASTA - не поддерживается
3. График - базовая версия без аннотаций
4. Matching функция - заглушка

## Используемые паттерны

Следует стилю `samples_tab.py`:
- Async методы с `page.run_task()`
- Progress dialogs
- SnackBar уведомления
- Валидация ввода
- Обработка ошибок

## Структура вкладки

```python
PeptidesTab
  ├─ Section 1: FASTA Loading
  ├─ Section 2: Tool Settings
  ├─ Section 3: Ion Settings
  ├─ Section 4: Matching
  └─ Section 5: Search & View
```

Каждая секция независима и имеет свои методы.
