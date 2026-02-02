# Stage 3.3 Protein Mapping - Final Enhancements

**Дата**: 2026-02-02  
**Статус**: ✅ ЗАВЕРШЕНО

## Обзор доработок

Добавлен полный функционал сопоставления белков с пептидными идентификациями и расчёта метрик качества для protein matches.

## Реализованные изменения

### 1. Схема БД - peptide_match

**Добавлены поля**:
```sql
unique_evidence INTEGER,          -- BOOLEAN: уникальная ли это идентификация для белка
matched_coverage_percent REAL     -- Ion coverage для matched_sequence
```

**Полная структура таблицы**:
```sql
CREATE TABLE peptide_match (
    id INTEGER PRIMARY KEY,
    protein_id TEXT NOT NULL,
    identification_id INTEGER NOT NULL,
    matched_sequence TEXT NOT NULL,
    identity REAL NOT NULL,
    matched_ppm REAL,                    -- PPM для matched_sequence
    matched_theor_mass REAL,
    unique_evidence INTEGER,             -- NEW
    matched_coverage_percent REAL,       -- NEW
    FOREIGN KEY (protein_id) REFERENCES protein(id),
    FOREIGN KEY (identification_id) REFERENCES identification(id)
);
```

### 2. Project API - методы для peptide_match

#### `clear_peptide_matches()`
```python
async def clear_peptide_matches() -> None
```
Очищает все записи в peptide_match (для пересопоставления).

#### `add_peptide_matches_batch()`
```python
async def add_peptide_matches_batch(matches_df: pd.DataFrame) -> None
```

**DataFrame колонки**:
- `protein_id`: str
- `identification_id`: int
- `matched_sequence`: str
- `identity`: float
- `matched_ppm`: float | None
- `matched_theor_mass`: float | None
- `unique_evidence`: bool | None
- `matched_coverage_percent`: float | None

**Примечание**: Без автосохранения для батч-эффективности.

#### `get_peptide_matches()`
```python
async def get_peptide_matches(
    protein_id: str | None = None,
    identification_id: int | None = None
) -> pd.DataFrame
```

Получает peptide matches с опциональной фильтрацией.

#### `update_peptide_match_metrics()`
```python
async def update_peptide_match_metrics(
    match_id: int,
    matched_ppm: float | None = None,
    matched_coverage_percent: float | None = None
) -> None
```

Обновляет метрики для protein match.

**Использование**:
```python
await project.update_peptide_match_metrics(
    match_id=123,
    matched_ppm=5.2,
    matched_coverage_percent=45.8
)
```

### 3. Project API - обновлён get_identifications()

**Добавлен параметр**:
```python
only_prefered: bool = False
```

Если `True`, возвращает только идентификации с `is_preferred = 1`.

**Использование в map_proteins()**:
```python
idents = await project.get_identifications(
    tool_id=tool_id,
    only_prefered=True,  # Только preferred
    offset=0,
    limit=1000
)
```

### 4. UI - FASTA Section (Блок 1)

**Добавлены контролы**:

```
Protein Mapping Settings
├─ ☐ Match preferred only
├─ BLAST Max Accepts: [16]
├─ BLAST Max Rejects: [5]
└─ [Match Proteins to Identifications]
```

**Функциональность**:

#### Настройки BLAST
- **Max Accepts** (по умолчанию 16): максимум принятых совпадений
- **Max Rejects** (по умолчанию 5): максимум отклонённых совпадений
- Сохраняются в `project_settings`:
  - `max_blast_accept`: "16"
  - `max_blast_reject`: "5"

#### Чекбокс "Match preferred only"
- Если включён: сопоставление только для preferred идентификаций
- Если выключен: сопоставление для всех идентификаций

#### Кнопка "Match Proteins to Identifications"
**Действия**:
1. Сохранить BLAST settings
2. Собрать tool settings (min_protein_identity для каждого tool)
3. Очистить существующие matches (`clear_peptide_matches()`)
4. Вызвать `map_proteins()` generator
5. Для каждого батча:
   - Добавить matches через `add_peptide_matches_batch()`
   - Обновить progress
6. Сохранить все изменения
7. Показать результат

**Progress Dialog**:
```
┌──────────────────────────────────────┐
│ Matching Proteins                    │
├──────────────────────────────────────┤
│ Mapping...                           │
│ [████████░░] 80%                     │
│                                      │
│ Mapped 1,234 matches...              │
└──────────────────────────────────────┘
```

### 5. UI - Ion Settings Section (Блок 3)

**Добавлена кнопка**:
```
[Calculate PPM Error and Ion Coverage for Protein Identifications]
```

**Функциональность**:

#### `calculate_protein_match_metrics()`

**Действия**:
1. Сохранить ion settings
2. Получить все peptide_match из БД
3. Проверить наличие matches (если нет → сообщение)
4. Для каждого match:
   - Получить identification (для доступа к spectrum)
   - Получить spectrum (для mz/intensity arrays и pepmass)
   - **Рассчитать PPM**: `calculate_ppm(matched_sequence, pepmass, charge)`
   - **Рассчитать coverage**: `match_predictions()` → `intensity_percent`
   - Обновить через `update_peptide_match_metrics()`
   - Обновлять progress каждые 10 matches
5. Сохранить все изменения
6. Показать результат

**Progress Dialog**:
```
┌──────────────────────────────────────┐
│ Calculating Protein Metrics          │
├──────────────────────────────────────┤
│ Calculating...                       │
│ [███████░░░] 70%                     │
│                                      │
│ 700/1000...                          │
└──────────────────────────────────────┘
```

## Workflow использования

### Полный workflow обработки данных:

```
1. Загрузка FASTA библиотеки
   ↓
2. Импорт спектров (Samples tab)
   ↓
3. Импорт идентификаций (Samples tab)
   ↓
4. Calculate Ion Coverage (для identifications)
   ↓
5. Run Identification Matching (выбор preferred)
   ↓
6. Match Proteins to Identifications (BLAST)
   ↓
7. Calculate PPM/Coverage for Protein Identifications
   ↓
8. Готовые данные для анализа
```

### Подробно по этапам:

#### Этап 1-3: Загрузка данных (Samples tab)
Импорт спектров и идентификаций из файлов.

#### Этап 4: Calculate Ion Coverage
```
Peptides Tab → Ion Matching Settings
  → Ion types: b, y
  → PPM: 20, Charges: 1,2
  → Calculate Ion Coverage → Only Missing
```

**Результат**: Поле `intensity_coverage` заполнено для всех identifications.

#### Этап 5: Run Identification Matching
```
Peptides Tab → Preferred Selection
  → Criterion: Intensity coverage
  → Run Identification Matching
```

**Результат**: Для каждого спектра выбрана одна preferred идентификация (is_preferred=1).

#### Этап 6: Match Proteins
```
Peptides Tab → Protein Sequence Library
  → Load FASTA (если ещё не загружена)
  → ☐ Match preferred only (можно включить)
  → BLAST Max Accepts: 16
  → BLAST Max Rejects: 5
  → Match Proteins to Identifications
```

**Результат**: Таблица `peptide_match` заполнена связями peptide-protein.

**Данные в peptide_match**:
- `protein_id`, `identification_id` - связь
- `matched_sequence` - последовательность из белка
- `identity` - процент идентичности
- `unique_evidence` - True если это единственное совпадение для данной идентификации
- `matched_theor_mass` - теоретическая масса matched_sequence
- `matched_ppm`, `matched_coverage_percent` - пока NULL

#### Этап 7: Calculate Protein Metrics
```
Peptides Tab → Ion Matching Settings
  → Calculate PPM Error and Ion Coverage for Protein Identifications
```

**Результат**: Поля `matched_ppm` и `matched_coverage_percent` заполнены для всех matches.

## Технические детали

### Использование map_proteins()

```python
from api.peptides.matching import map_proteins

# Подготовка tool_settings
tool_settings = {
    1: {'min_protein_identity': 0.75},
    2: {'min_protein_identity': 0.80}
}

# Запуск mapping
async for matches_df, count, tool_id in map_proteins(
    project,
    tool_settings,
    only_prefered=False,
    batch_size=1000
):
    # matches_df содержит:
    # - protein_id
    # - identification_id
    # - matched_sequence
    # - identity
    # - unique_evidence
    # - matched_theor_mass
    # - matched_ppm (None)
    # - matched_coverage_percent (None - заполняется позже)
    
    await project.add_peptide_matches_batch(matches_df)
    print(f"Added {count} matches for tool {tool_id}")

await project.save()
```

### Расчёт PPM для matched_sequence

```python
from utils.ppm import calculate_ppm

# Для каждого match
matched_ppm = calculate_ppm(
    sequence=match['matched_sequence'],  # Из белковой БД
    pepmass=spectrum['pepmass'],         # Экспериментальная m/z
    charge=spectrum['charge']            # Заряд
)
```

**Примечание**: `calculate_ppm()` поддерживает модификации в последовательности.

### Расчёт coverage для matched_sequence

```python
from api.spectra.ion_match import match_predictions, IonMatchParameters

# Параметры
params = IonMatchParameters(
    ions=['b', 'y'],
    tolerance=20.0,  # PPM
    mode='largest',
    water_loss=False,
    ammonia_loss=False
)

# Расчёт
result = match_predictions(
    params=params,
    mz=spectrum['mz_array'].tolist(),
    intensity=spectrum['intensity_array'].tolist(),
    charges=spectrum['charge'],
    sequence=match['matched_sequence']  # Последовательность из белка
)

matched_coverage = result.intensity_percent
```

## Новые настройки проекта

### project_settings

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `max_blast_accept` | string | "16" | BLAST maxAccepts |
| `max_blast_reject` | string | "5" | BLAST maxRejects |
| `fragment_charges` | string | "1,2" | Заряды фрагментов |
| `ion_types` | string | "b,y" | Типы ионов |
| `water_loss` | string | "0" | H₂O потери |
| `nh3_loss` | string | "0" | NH₃ потери |
| `ion_ppm_threshold` | string | "20" | PPM threshold |

## Структура данных peptide_match

После полного цикла обработки:

```python
{
    'id': 1,
    'protein_id': 'P12345',
    'identification_id': 456,
    'matched_sequence': 'PEPTIDEK',           # Из белковой БД
    'identity': 1.0,                           # 100% совпадение
    'matched_ppm': 5.2,                        # Рассчитан
    'matched_theor_mass': 500.3,               # Из pyteomics
    'unique_evidence': 1,                      # Уникальное совпадение
    'matched_coverage_percent': 45.8           # Рассчитан
}
```

## Обновлённые файлы

### API
1. `api/project/schema.py` - поля в peptide_match
2. `api/project/project.py` - 4 новых метода:
   - `clear_peptide_matches()`
   - `add_peptide_matches_batch()`
   - `get_peptide_matches()`
   - `update_peptide_match_metrics()`
   - обновлён `get_identifications()` - параметр only_prefered

### GUI
3. `gui/views/tabs/peptides_tab.py` - добавлены:
   - BLAST settings controls
   - "Match Proteins" button
   - "Calculate Protein Metrics" button
   - Функции обработки

## Итоговый чеклист

### Схема БД
- [x] peptide_match.unique_evidence
- [x] peptide_match.matched_coverage_percent

### Project API
- [x] clear_peptide_matches()
- [x] add_peptide_matches_batch()
- [x] get_peptide_matches()
- [x] update_peptide_match_metrics()
- [x] get_identifications() - параметр only_prefered

### UI Peptides Tab
- [x] BLAST Max Accepts field
- [x] BLAST Max Rejects field
- [x] Match preferred only checkbox
- [x] Match Proteins button
- [x] Calculate Protein Metrics button
- [x] load_blast_settings()
- [x] save_blast_settings()
- [x] match_proteins_to_identifications()
- [x] calculate_protein_match_metrics()

### Интеграция
- [x] map_proteins() вызывается из UI
- [x] Результаты сохраняются в peptide_match
- [x] PPM рассчитывается через utils.ppm
- [x] Coverage рассчитывается через match_predictions

## Примеры использования

### 1. Сопоставление белков

```python
# В UI: нажать "Match Proteins to Identifications"

# Программно:
from api.peptides.matching import map_proteins

tool_settings = {tool_id: {'min_protein_identity': 0.75}}

await project.clear_peptide_matches()

async for matches_df, count, tool_id in map_proteins(
    project, tool_settings, only_prefered=False
):
    await project.add_peptide_matches_batch(matches_df)

await project.save()
```

### 2. Расчёт метрик для matches

```python
# В UI: нажать "Calculate PPM Error and Ion Coverage..."

# Программно:
matches = await project.get_peptide_matches()

for _, match in matches.iterrows():
    # Получить данные
    ident = await project.get_identifications(identification_id=match['identification_id'])
    spectrum = await project.get_spectrum_full(ident['spectre_id'])
    
    # Рассчитать PPM
    ppm = calculate_ppm(match['matched_sequence'], spectrum['pepmass'], spectrum['charge'])
    
    # Рассчитать coverage
    result = match_predictions(params, mz, intensity, charge, match['matched_sequence'])
    coverage = result.intensity_percent
    
    # Обновить
    await project.update_peptide_match_metrics(
        match['id'],
        matched_ppm=ppm,
        matched_coverage_percent=coverage
    )

await project.save()
```

### 3. Анализ результатов

```sql
-- Белки с уникальными пептидами
SELECT protein_id, COUNT(*) as peptides, SUM(unique_evidence) as unique_count
FROM peptide_match
GROUP BY protein_id
HAVING unique_count > 0;

-- Средние метрики
SELECT 
    AVG(identity) as avg_identity,
    AVG(matched_ppm) as avg_ppm,
    AVG(matched_coverage_percent) as avg_coverage
FROM peptide_match
WHERE matched_ppm IS NOT NULL;

-- Лучшие совпадения
SELECT protein_id, matched_sequence, identity, matched_ppm, matched_coverage_percent
FROM peptide_match
WHERE identity > 0.95 
  AND matched_coverage_percent > 50
ORDER BY matched_coverage_percent DESC
LIMIT 10;
```

## Производительность

### Batch Operations
- **map_proteins()**: обрабатывает по 1000 идентификаций за батч
- **Сохранение**: одно сохранение после всех обновлений батча
- **Progress**: обновление каждые 10 записей

### Оптимизация
- `update_peptide_match_metrics()` без автосохранения
- `update_identification_coverage()` без автосохранения
- Вызывающий код делает `await project.save()` после батча

## Известные ограничения

1. **BLAST параметры**: Глобальные для всех tools
2. **Повторное mapping**: Полная очистка таблицы peptide_match
3. **Заряд**: Если NULL в spectrum, использует первый из списка charges
4. **Одиночные UPDATE**: Каждая запись обновляется отдельным запросом (но без автосохранения)

## Следующие шаги

Данные в `peptide_match` готовы для:
- Построения protein identifications
- Расчёта LFQ метрик
- Сравнительного анализа
- Отчётов и визуализации

---

## ✅ Все доработки завершены и готовы к использованию!
