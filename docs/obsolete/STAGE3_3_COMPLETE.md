# STAGE 3.3 COMPLETE: Peptides Tab Implementation

**Дата**: 2026-02-01  
**Этап**: 3.3 - Разработка интерфейса для работы с пептидами  
**Статус**: ✅ ЗАВЕРШЕНО

## Обзор реализации

Этап 3.3 успешно завершён. Реализован полнофункциональный интерфейс для работы с пептидными идентификациями на вкладке **Peptides**.

## Реализованные компоненты

### 1. Парсер FASTA (`api/inputs/proteins/fasta.py`)

**Класс**: `FastaParser`

**Функциональность**:
- ✅ Валидация FASTA файлов
- ✅ Батч-парсинг больших файлов (по умолчанию 100 записей в батче)
- ✅ Поддержка UniProt формата с извлечением:
  - Protein ID (accession)
  - Gene name (из поля GN=)
  - Full header (fasta_name)
- ✅ Поддержка обычного FASTA формата
- ✅ Заглушка для обогащения данных из UniProt API (для будущей реализации)

**Парсинг UniProt заголовков**:
```
>sp|P12345|PROT_HUMAN Protein name OS=Homo sapiens GN=TEST1 PE=1 SV=1
```
Извлекается:
- `id`: P12345
- `gene`: TEST1
- `fasta_name`: полный заголовок без '>'
- `is_uniprot`: True

**Примеры использования**:
```python
parser = FastaParser("proteins.fasta", is_uniprot=True)

if await parser.validate():
    async for batch in parser.parse_batch(batch_size=100):
        await project.add_proteins_batch(batch)
```

### 2. Функция сопоставления идентификаций (`api/peptides/matching.py`)

**Функция**: `select_preferred_identifications()`

**Статус**: Заглушка для реализации разработчиком

**Сигнатура**:
```python
async def select_preferred_identifications(
    project: Project,
    criterion: str,  # "ppm" or "intensity"
    ion_settings: dict,
    tool_settings: dict[int, dict]
) -> int
```

**Параметры**:
- `criterion`: Критерий выбора ("ppm" - минимальная ошибка PPM, "intensity" - максимальное покрытие интенсивности)
- `ion_settings`: Настройки разметки ионов (типы ионов, потери, PPM threshold)
- `tool_settings`: Настройки для каждого инструмента (max_ppm, min_score, etc.)

**TODO для разработчика**:
- Генерация теоретических фрагментов
- Сопоставление пиков с PPM threshold
- Расчёт покрытия интенсивности
- Обновление is_preferred в БД

### 3. Функция визуализации спектра (`api/spectra/plot_matches.py`)

**Функция**: `plot_ion_match()`

**Функциональность**:
- ✅ Базовая визуализация спектра
- ✅ Отображение последовательности и заряда в заголовке
- ✅ Экспорт в PNG для отображения в UI

**Параметры**:
- `mz_array`: массив m/z значений
- `intensity_array`: массив интенсивностей
- `sequence`: пептидная последовательность
- `charge`: заряд прекурсора
- `ion_types`: типы ионов для сопоставления
- `water_loss`, `nh3_loss`: флаги учёта потерь
- `ppm_threshold`: порог PPM для сопоставления

**TODO для будущей реализации**:
- Полная разметка совпадающих пиков
- Аннотации ионов
- Цветовая кодировка по типам ионов

### 4. Вкладка Peptides (`gui/views/tabs/peptides_tab.py`)

Полностью переработанная вкладка с 5 основными блоками.

#### Блок 1: Загрузка FASTA библиотеки

**UI компоненты**:
- Выбор FASTA файла (FilePicker с фильтром .fasta, .fa)
- ☑ Sequences in UniProt format (по умолчанию включено)
- ☐ Enrich data from UniProt (для будущей функциональности)
- Кнопка "Load Sequences"
- Статус загрузки с количеством белков

**Функциональность**:
- ✅ Валидация FASTA файла перед импортом
- ✅ Progress dialog с отображением прогресса
- ✅ Батч-импорт с обновлением счётчика
- ✅ Сохранение в таблицу `protein`
- ✅ Обработка ошибок с информативными сообщениями

**Пример работы**:
```
Status: Loaded: 1,234 proteins from proteins.fasta
```

#### Блок 2: Настройки инструментов

**UI компоненты** (для каждого tool):
- Max PPM (по умолчанию: 50)
- Min Score (по умолчанию: 0.8)
- Min Ion Intensity Coverage (по умолчанию: 25%)
- ☐ Use protein identification from file
- Min Protein Identity (по умолчанию: 0.75)
- ☐ DeNovo seq correction with search

**Функциональность**:
- ✅ Автозагрузка существующих настроек из `tool.settings`
- ✅ Валидация числовых значений:
  - Max PPM > 0
  - 0 < Min Score <= 1
  - 0 < Coverage <= 100
  - 0 < Protein Identity <= 1
- ✅ Сохранение настроек в JSON поле `tool.settings`
- ✅ Визуальное разделение по инструментам (цветные контейнеры)

**Хранение**:
```json
{
  "max_ppm": 50.0,
  "min_score": 0.8,
  "min_ion_intensity_coverage": 25.0,
  "use_protein_from_file": false,
  "min_protein_identity": 0.75,
  "denovo_correction": false
}
```

#### Блок 3: Настройки разметки ионов

**UI компоненты**:
- Ion Types: ☐a ☑b ☐c ☐x ☑y ☐z (по умолчанию: b, y)
- Losses: ☐ Water loss (H₂O), ☐ Ammonia loss (NH₃)
- PPM Threshold: 20

**Функциональность**:
- ✅ Глобальные настройки (применяются ко всем инструментам)
- ✅ Сохранение в `project_settings`
- ✅ Автозагрузка при открытии вкладки
- ✅ Валидация:
  - Хотя бы один тип иона выбран
  - PPM Threshold > 0

**Хранение** (в project_settings):
- `ion_types`: "b,y" (строка)
- `water_loss`: "1" или "0"
- `nh3_loss`: "1" или "0"
- `ion_ppm_threshold`: "20"

#### Блок 4: Выбор оптимальной идентификации

**UI компоненты**:
- Selection Criterion:
  - ○ PPM error
  - ● Intensity coverage (по умолчанию)
- Кнопка "Run Identification Matching"

**Функциональность**:
- ✅ Валидация и сохранение всех настроек (tool + ion)
- ✅ Сборка параметров для функции matching
- ✅ Progress dialog с индикацией выполнения
- ✅ Вызов `select_preferred_identifications()`
- ✅ Отображение результата (количество обработанных спектров)

**Обработка ошибок**:
- Валидация настроек инструментов
- Валидация настроек ионов
- Обработка ошибок выполнения

#### Блок 5: Поиск и просмотр идентификаций

**UI компоненты для поиска**:
- Фильтр по Sample (All Samples + список)
- Фильтр по Tool (All Tools + список)
- Search by: Sequence Number / Scans / Sequence / Canonical Sequence
- Поле ввода значения поиска
- Кнопка "Search"

**Таблица результатов**:
| Seq# | Sample | Tool | Sequence | Score | PPM | Pref | View |
|------|--------|------|----------|-------|-----|------|------|
| 1234 | Sample1 | PowerNovo2 | PEPTIDE... | 0.95 | 2.3 | ★ | 👁 |

Колонки:
- **Seq#**: Номер спектра в файле
- **Sample**: Название образца
- **Tool**: Инструмент идентификации
- **Sequence**: Пептидная последовательность (обрезается до 20 символов)
- **Score**: Оценка качества идентификации
- **PPM**: Ошибка массы прекурсора
- **Pref**: Звёздочка для preferred идентификации
- **View**: Кнопка просмотра графика

**Функциональность**:
- ✅ Динамическое построение SQL запроса с фильтрами
- ✅ Поиск по различным полям:
  - seq_no, scans: точное совпадение (числа)
  - sequence, canonical_sequence: LIKE поиск (подстрока)
- ✅ Лимит 100 результатов
- ✅ Автоматическое отображение графика для первого результата
- ✅ Обновление фильтров при изменении данных

**График ионной разметки**:
- ✅ Отображение спектра (mz/intensity)
- ✅ Информация о последовательности
- ✅ Информация о tool, score, PPM
- ✅ Экспорт Plotly figure в PNG
- ✅ Отображение через ft.Image (base64)

**Обработка ошибок**:
- Валидация типов данных для поиска
- Обработка ошибок запроса
- Обработка ошибок построения графика

## Интеграция и lifecycle

### did_mount()
При монтировании вкладки:
1. ✅ Загрузка списка инструментов (`refresh_tools()`)
2. ✅ Загрузка настроек ионов (`load_ion_settings()`)
3. ✅ Обновление фильтров поиска (`refresh_search_filters()`)

### Обновление при переключении
Вкладка реагирует на изменения в других вкладках (например, добавление tools в Samples).

## Тестирование

### Интеграционные тесты

**Файл**: `test_stage3_3.py`

**Результаты**:
```
✅ test_fasta_parser_validation - PASSED
✅ test_fasta_parser_parsing - PASSED
✅ test_project_protein_storage - PASSED
✅ test_tool_settings_storage - PASSED
✅ test_ion_settings_storage - PASSED
✅ test_fasta_parser_invalid_file - PASSED
```

**Покрытие**:
- Валидация FASTA файлов
- Парсинг UniProt и обычных заголовков
- Хранение белков в БД
- Хранение и загрузка настроек tool
- Хранение и загрузка настроек ионов
- Обработка некорректных файлов

### Тестовые данные

**Файл**: `TEST_DATA/test.fasta`

Содержит 5 белков:
- 4 UniProt (sp) записи
- 1 TrEMBL (tr) запись
- Различные форматы заголовков
- С наличием и отсутствием gene names

## Архитектурные особенности

### Паттерны кода

**Следование samples_tab.py**:
- ✅ Асинхронные методы для работы с БД
- ✅ Использование `self.page.run_task()` для event handlers
- ✅ Progress dialogs для долгих операций
- ✅ SnackBar для уведомлений
- ✅ Валидация пользовательского ввода
- ✅ Обработка ошибок с try-except
- ✅ Логирование через utils.logger

### Организация кода

**Структура класса PeptidesTab**:
```python
class PeptidesTab(ft.Container):
    def __init__()
    def _build_content()
    def did_mount()
    async def _load_initial_data()
    
    # Секция 1: FASTA
    def _build_fasta_section()
    async def browse_fasta_file()
    async def load_fasta_file()
    
    # Секция 2: Tool Settings
    def _build_tools_settings_section()
    async def refresh_tools()
    def _create_tool_settings_controls()
    def _validate_tool_settings()
    async def save_tool_settings()
    
    # Секция 3: Ion Settings
    def _build_ion_settings_section()
    async def load_ion_settings()
    async def save_ion_settings()
    
    # Секция 4: Matching
    def _build_matching_section()
    async def run_identification_matching()
    
    # Секция 5: Search & View
    def _build_search_section()
    async def refresh_search_filters()
    async def search_identifications()
    async def view_identification()
```

**Разделение по секциям**: Каждый блок UI имеет свой `_build_*_section()` метод и связанные методы обработки.

### Работа с данными

**Настройки инструмента** (tool.settings JSON):
```python
{
    "max_ppm": 50.0,
    "min_score": 0.8,
    "min_ion_intensity_coverage": 25.0,
    "use_protein_from_file": False,
    "min_protein_identity": 0.75,
    "denovo_correction": False
}
```

**Настройки ионов** (project_settings):
- Хранятся как отдельные ключ-значение пары
- Загружаются/сохраняются через `project.get_setting()` / `project.set_setting()`
- Используются глобально для всех инструментов

**Белки** (таблица protein):
```sql
CREATE TABLE protein (
    id TEXT PRIMARY KEY,
    is_uniprot INTEGER NOT NULL DEFAULT 0,
    fasta_name TEXT,
    sequence TEXT,
    gene TEXT
)
```

## Ограничения и TODO

### Текущие ограничения

1. **Обогащение UniProt**: Реализована только заглушка
2. **Повторная загрузка FASTA**: Не поддерживается (только одна загрузка)
3. **Интерактивные графики**: Используются статические PNG (pywebview в этапе 5)
4. **Функция matching**: Заглушка для разработчика

### Для будущей реализации

1. **api/peptides/matching.py**:
   - Генерация теоретических фрагментов
   - PPM-based matching
   - Расчёт покрытия интенсивности
   - Обновление is_preferred в БД

2. **api/spectra/plot_matches.py**:
   - Полная разметка совпадающих пиков
   - Аннотации ионов
   - Цветовая кодировка

3. **api/inputs/proteins/fasta.py**:
   - UniProt API интеграция
   - Обогащение данных (full_name, organism, etc.)

4. **Интерфейс**:
   - Интерактивные графики через pywebview
   - Экспорт результатов поиска
   - Массовые операции с идентификациями

## Файловая структура

### Новые файлы

```
api/
  inputs/
    proteins/
      __init__.py          # Новый модуль
      fasta.py             # Парсер FASTA
  peptides/
    __init__.py            # Новый модуль
    matching.py            # Функция matching (заглушка)
  spectra/
    plot_matches.py        # Обновлено: добавлен plot_ion_match()

gui/
  views/
    tabs/
      peptides_tab.py      # Полностью переработан

TEST_DATA/
  test.fasta               # Тестовые данные

test_stage3_3.py           # Интеграционные тесты
STAGE3_3_COMPLETE.md       # Этот документ
```

### Обновлённые файлы

- `api/spectra/plot_matches.py`: Добавлена функция `plot_ion_match()`
- `gui/views/tabs/peptides_tab.py`: Полная переработка (было 52 строки → стало 900+ строк)

## Выводы

Этап 3.3 успешно завершён. Реализован полнофункциональный интерфейс для работы с пептидными идентификациями со следующими возможностями:

✅ Загрузка белковых библиотек (FASTA)  
✅ Настройка параметров идентификации для каждого инструмента  
✅ Настройка параметров разметки ионов  
✅ Запуск процесса выбора оптимальных идентификаций  
✅ Поиск идентификаций по различным критериям  
✅ Визуализация спектров с последовательностями  

Код хорошо структурирован, протестирован и готов к интеграции с функциональностью этапа 4 (реализация matching алгоритмов разработчиком).

---

**Следующий этап**: Этап 4 - Реализация алгоритмов сопоставления и белковой идентификации (разработчик)
