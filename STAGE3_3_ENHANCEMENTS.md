# Stage 3.3 Enhancements: Ion Coverage Calculation

**Дата**: 2026-02-01  
**Статус**: ✅ ЗАВЕРШЕНО

## Обзор изменений

Добавлен функционал расчёта покрытия интенсивности спектра ионами (ion intensity coverage) для всех идентификаций в проекте.

## Реализованные изменения

### 1. Схема БД (`api/project/schema.py`)

**Добавлено поле** в таблицу `identification`:
```sql
intensity_coverage REAL  -- Percentage of spectrum intensity matched by theoretical ions
```

**Назначение**: Хранит процент интенсивности спектра, совпадающий с теоретическими ионами последовательности.

### 2. Project API (`api/project/project.py`)

#### Обновлён метод `add_identifications_batch()`

Теперь поддерживает колонку `intensity_coverage` в DataFrame:
```python
identifications_df: DataFrame with columns:
    - intensity_coverage: float | None  # NEW
```

#### Добавлен метод `update_identification_coverage()`

```python
async def update_identification_coverage(
    self,
    identification_id: int,
    intensity_coverage: float
) -> None:
    """
    Update intensity coverage for an identification.
    
    Args:
        identification_id: Identification ID
        intensity_coverage: Percentage of spectrum intensity matched by ions
    """
```

**Использование**:
```python
await project.update_identification_coverage(ident_id, 45.8)
```

**Примечание**: Не выполняет автосохранение для эффективности батч-операций. Вызывающий код должен вызвать `save()` после обновления пакета идентификаций.

#### Добавлен метод `set_preferred_identification()`

```python
async def set_preferred_identification(
    self,
    spectre_id: int,
    identification_id: int
) -> None:
    """
    Set preferred identification for a spectrum.
    
    Resets is_preferred to False for all identifications of this spectrum,
    then sets it to True for the specified identification.
    """
```

**Логика**:
1. `UPDATE identification SET is_preferred = 0 WHERE spectre_id = ?`
2. `UPDATE identification SET is_preferred = 1 WHERE id = ?`
3. Автосохранение

**Использование**:
```python
await project.set_preferred_identification(spectrum_id=123, identification_id=456)
```

### 3. Ion Matching (`api/spectra/ion_match.py`)

#### Обновлён `IonMatchParameters`

**Изменено**:
```python
tolerance: float = 20.0  # PPM tolerance (было: Th tolerance)
```

#### Обновлён `match_predictions()`

**Изменено** при вызове `get_fragment_matches()`:
```python
matches = get_fragment_matches(
    frags,
    mz,
    intensity,
    tolerance_type='ppm',  # Было: 'th'
    tolerance_value=params.tolerance,
    mode=params.mode,
)
```

**Теперь tolerance передаётся в PPM**, что соответствует настройкам UI.

### 4. UI - Peptides Tab (`gui/views/tabs/peptides_tab.py`)

#### Добавлено в секцию Ion Matching Settings

**Новое поле**:
```python
self.fragment_charges_field = ft.TextField(
    label="Fragment Charges (comma-separated)",
    value="1,2",
    hint_text="e.g., 1,2,3",
    width=250
)
```

**Новая кнопка**:
```python
self.calc_coverage_btn = ft.ElevatedButton(
    content=ft.Text("Calculate Ion Coverage"),
    icon=ft.Icons.CALCULATE,
    on_click=lambda e: self.page.run_task(self.calculate_ion_coverage, e)
)
```

**Layout**:
```
Ion Matching Settings
├─ Ion Types: ☐a ☑b ☐c ☐x ☑y ☐z
├─ Losses: ☐Water ☐Ammonia
├─ PPM Threshold: [20]  Fragment Charges: [1,2]
└─ [Calculate Ion Coverage]
```

#### Обновлён `load_ion_settings()`

Добавлена загрузка настройки `fragment_charges` из `project_settings`:
```python
fragment_charges = await self.project.get_setting('fragment_charges', '1,2')
self.fragment_charges_field.value = fragment_charges
```

#### Обновлён `save_ion_settings()`

Добавлено сохранение `fragment_charges`:
```python
await self.project.set_setting('fragment_charges', charges_str)
```

#### Новый метод `calculate_ion_coverage()`

Показывает модальное окно с выбором:
- **Only Missing**: Рассчитать только для идентификаций где `intensity_coverage IS NULL`
- **All Identifications**: Пересчитать для всех идентификаций

**Модальное окно**:
```
┌─────────────────────────────────────────┐
│ Calculate Ion Coverage                  │
├─────────────────────────────────────────┤
│ Calculate intensity coverage for        │
│ identifications:                        │
│                                         │
│ This will use the current ion matching │
│ settings.                               │
├─────────────────────────────────────────┤
│ [Cancel] [Only Missing] [All]          │
└─────────────────────────────────────────┘
```

#### Новый метод `_run_coverage_calculation()`

**Параметры**:
- `recalculate_all: bool` - пересчитывать все или только с NULL

**Логика**:
1. Сохранить настройки ионов
2. Парсить заряды из поля (валидация формата)
3. Создать `IonMatchParameters` с текущими настройками
4. Получить идентификации для обработки (с фильтром или без)
5. Для каждой идентификации:
   - Загрузить спектр через `get_spectrum_full()`
   - Определить заряд (из спектра или первый из списка)
   - Вызвать `match_predictions()`
   - Получить `result.intensity_percent`
   - Обновить через `update_identification_coverage()`
   - Обновлять прогресс каждые 10 идентификаций
6. Сохранить изменения: `await project.save()`
7. Показать результат

**Progress Dialog**:
```
┌─────────────────────────────────────────┐
│ Calculating Ion Coverage                │
├─────────────────────────────────────────┤
│ Calculating coverage...                 │
│ [███████░░░] 70%                        │
│                                         │
│ Processed 700/1000 identifications...   │
└─────────────────────────────────────────┘
```

**Обработка ошибок**:
- Невалидный формат зарядов → SnackBar
- Нет идентификаций → SnackBar "No identifications to process"
- Ошибка при обработке конкретной идентификации → логируется, но продолжается обработка
- Общая ошибка → SnackBar с описанием

## Настройки проекта

### Новые ключи в `project_settings`

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `fragment_charges` | string | "1,2" | Заряды фрагментов через запятую |

### Существующие ключи (без изменений)

| Ключ | Тип | По умолчанию |
|------|-----|--------------|
| `ion_types` | string | "b,y" |
| `water_loss` | string | "0" |
| `nh3_loss` | string | "0" |
| `ion_ppm_threshold` | string | "20" |

## Workflow использования

### 1. Настройка параметров

```
Peptides Tab → Ion Matching Settings
├─ Выбрать типы ионов (b, y)
├─ Включить потери (опционально)
├─ Задать PPM threshold (20)
└─ Задать заряды фрагментов (1,2)
```

### 2. Расчёт покрытия

```
Нажать "Calculate Ion Coverage"
  ↓
Выбрать режим:
  - Only Missing: быстрее, только новые идентификации
  - All: полный пересчёт
  ↓
Ожидание (progress dialog)
  ↓
Результат: "Successfully calculated coverage for N identifications"
```

### 3. Использование результатов

Поле `intensity_coverage` теперь доступно:
- В функции `select_preferred_identifications()` для выбора по критерию "intensity"
- В SQL запросах для фильтрации и анализа
- Для отчётов и экспорта

## Технические детали

### Использование match_predictions()

```python
from api.calculations.spectra.ion_match import IonMatchParameters, match_predictions

# Подготовка параметров
params = IonMatchParameters(
    ions=['b', 'y'],
    tolerance=20.0,  # PPM
    mode='largest',
    water_loss=False,
    ammonia_loss=False
)

# Получение спектра
spectrum = await project.get_spectrum_full(spectrum_id)

# Расчёт
result = match_predictions(
    params=params,
    mz=spectrum['mz_array'].tolist(),
    intensity=spectrum['intensity_array'].tolist(),
    charges=2,  # или [1, 2]
    sequence="PEPTIDE"
)

# Результат
coverage = result.intensity_percent  # Процент покрытия
num_matches = len(result.fragment_matches)  # Количество совпадений
```

### Batch Updates без автосохранения

Для эффективности `update_identification_coverage()` не вызывает `save()`:

```python
# ❌ Медленно - сохранение после каждого UPDATE
for ident_id, coverage in zip(ids, coverages):
    await project.update_identification_coverage(ident_id, coverage)

# ✅ Быстро - одно сохранение в конце
for ident_id, coverage in zip(ids, coverages):
    await project.update_identification_coverage(ident_id, coverage)
await project.save()  # Одно сохранение для всех
```

## Тестирование

### Ручное тестирование

1. **Загрузить проект** с идентификациями
2. **Настроить ионы**: выбрать b,y, PPM=20, заряды=1,2
3. **Запустить "Calculate Ion Coverage"**
4. **Выбрать "Only Missing"**
5. **Дождаться завершения** (progress dialog)
6. **Проверить результат**: запрос `SELECT id, intensity_coverage FROM identification`
7. **Повторить** с "All Identifications" - должно пересчитать

### SQL проверка

```sql
-- Посмотреть покрытие
SELECT id, sequence, intensity_coverage 
FROM identification 
WHERE intensity_coverage IS NOT NULL
LIMIT 10;

-- Статистика
SELECT 
    COUNT(*) as total,
    COUNT(intensity_coverage) as with_coverage,
    AVG(intensity_coverage) as avg_coverage,
    MIN(intensity_coverage) as min_coverage,
    MAX(intensity_coverage) as max_coverage
FROM identification;
```

## Известные ограничения

1. **Производительность**: Обработка по одной идентификации (не батчами для генерации фрагментов)
2. **Заряд прекурсора**: Если `charge IS NULL` в спектре, использует первый заряд из списка
3. **Ошибки обработки**: При ошибке на конкретной идентификации - пропускается, продолжается обработка

## Следующие шаги

Для разработчика в `select_preferred_identifications()`:
- Использовать `intensity_coverage` для выбора по критерию "intensity"
- Применять фильтр `min_ion_intensity_coverage` из tool settings
- Вызывать `set_preferred_identification()` для установки выбранной идентификации

## Итоговый чеклист

### API
- [x] `api/project/schema.py` - добавлено поле `intensity_coverage`
- [x] `api/project/project.py` - метод `update_identification_coverage()`
- [x] `api/project/project.py` - метод `set_preferred_identification()`
- [x] `api/project/project.py` - обновлён `add_identifications_batch()`
- [x] `api/spectra/ion_match.py` - tolerance в PPM вместо Th

### GUI
- [x] `gui/views/tabs/peptides_tab.py` - поле Fragment Charges
- [x] `gui/views/tabs/peptides_tab.py` - кнопка Calculate Ion Coverage
- [x] `gui/views/tabs/peptides_tab.py` - модальное окно выбора режима
- [x] `gui/views/tabs/peptides_tab.py` - функция расчёта с progress dialog
- [x] Загрузка/сохранение настройки fragment_charges

### Документация
- [x] `STAGE3_3_ENHANCEMENTS.md` - описание изменений

---

**Готово к использованию!** 🎉
