# Sample Management — единый агрегирующий SQL-запрос: анализ производительности

**Статус:** Отложено — оптимизация запроса вынесена в отдельную задачу, не блокирует реализацию 0.7.0a4
**Дата анализа:** Июль 2026 (спецификация 0.7.0a4)
**Контекст:** `docs/project/spec/0.7.0a4_REQUIREMENTS.md`, ветка работ — оптимизация Manage Samples View

Этот документ фиксирует текущее состояние единого агрегирующего запроса, которым заменяется N+1 вызовов `Project.get_sample_stats()` в `ManageSamplesView`/`SampleDataManager`. Запрос **уже используется** в реализации 0.7.0a4 (принят Developer'ом как рабочий), но имеет резерв по производительности на больших базах — доработка отложена до отдельного анализа.

---

## 1. Проблема, которую решает запрос

До 0.7.0a4:

- `Project.get_sample_stats(sample_id)` — 7 correlated subqueries **на один** sample (`sample_mixin.py:163-212`).
- `SampleDataManager.refresh_all_fresh()` и `ManageSamplesView._rebuild_panels_from_cache()` вызывали этот метод **в цикле по всем sample'ам проекта** — классический N+1.
- На больших проектах (сотни samples, миллионы identifications) полный пересчёт кэша занимал неприемлемое время.

Решение — один SQL-запрос с `GROUP BY sample_id` по всем таблицам сразу, вместо N вызовов с 7 correlated subqueries каждый.

**Важное архитектурное решение (согласовано с Developer):** запрос **всегда** выполняется по **всем** sample'ам проекта целиком, без `LIMIT`/`OFFSET`. Пагинация и фильтрация в UI (Manage Samples View) применяются **над уже полученным результатом** (in-memory, DataFrame/список), а не через SQL — потому что:
- Смысла в SQL-пагинации нет: `LIMIT/OFFSET` не даёt выигрыша (см. замеры в разделе 3).
- Результат целиком (все sample'ы со статистикой) занимает немного памяти даже при сотнях/тысячах sample'ов.
- Фильтрация по имени/subset/outlier/статусу тоже выполняется над результатом в Python.

---

## 2. Текущий запрос

### 2.1. Полный пересчёт кэша (используется вместо цикла `get_sample_stats()` по всем sample'ам)

```sql
WITH sf_counts AS (
    SELECT sample_id, COUNT(*) AS spectra_files_count
    FROM spectre_file
    GROUP BY sample_id
),
if_counts AS (
    SELECT
        sf.sample_id,
        COUNT(*) AS ident_files_count,
        SUM(
            CASE WHEN NOT EXISTS (
                SELECT 1 FROM identification i WHERE i.ident_file_id = idf.id
            ) THEN 1 ELSE 0 END
        ) AS empty_ident_files_count
    FROM identification_file idf
    JOIN spectre_file sf ON idf.spectre_file_id = sf.id
    GROUP BY sf.sample_id
),
ident_counts AS (
    SELECT
        sf.sample_id,
        COUNT(*) AS identifications_count,
        SUM(CASE WHEN i.is_preferred = 1 THEN 1 ELSE 0 END) AS preferred_count,
        SUM(CASE WHEN i.intensity_coverage IS NOT NULL THEN 1 ELSE 0 END) AS coverage_known_count
    FROM identification i
    JOIN spectre s ON i.spectre_id = s.id
    JOIN spectre_file sf ON s.spectre_file_id = sf.id
    GROUP BY sf.sample_id
),
protein_counts AS (
    SELECT sample_id, COUNT(*) AS protein_ids_count
    FROM protein_identification_result
    GROUP BY sample_id
),
base AS (
    SELECT
        smp.id                                          AS sample_id,
        smp.name                                        AS name,
        smp.subset_id                                   AS subset_id,
        sub.name                                        AS subset_name,
        smp.outlier                                     AS outlier,
        smp.additions                                   AS additions,
        COALESCE(sfc.spectra_files_count, 0)             AS spectra_files_count,
        COALESCE(ifc.ident_files_count, 0)               AS ident_files_count,
        COALESCE(ifc.empty_ident_files_count, 0)         AS empty_ident_files_count,
        COALESCE(ic.identifications_count, 0)            AS identifications_count,
        COALESCE(ic.preferred_count, 0)                  AS preferred_count,
        COALESCE(ic.coverage_known_count, 0)             AS coverage_known_count,
        COALESCE(pc.protein_ids_count, 0)                AS protein_ids_count,
        (SELECT COUNT(*) FROM tool)                      AS tools_count
    FROM sample smp
    LEFT JOIN subset sub          ON smp.subset_id = sub.id
    LEFT JOIN sf_counts sfc       ON sfc.sample_id = smp.id
    LEFT JOIN if_counts ifc       ON ifc.sample_id = smp.id
    LEFT JOIN ident_counts ic     ON ic.sample_id = smp.id
    LEFT JOIN protein_counts pc   ON pc.sample_id = smp.id
)
SELECT * FROM base ORDER BY name;
```

Пороги (`min_proteins`, `min_idents`) и статус (`OK`/`WARNING`/`ERROR`) **не считаются в SQL** — статус вычисляется в Python-коде (как и раньше, `_build_sample_header()`), над результатом этого запроса, после чтения порогов из `project_settings`.

### 2.2. Использование в проекте

- Метод-кандидат: `Project.get_all_samples_stats()` (новое имя, без параметра `sample_id` — считает по всем сразу).
- Вызывается **вместо** цикла в `SampleDataManager.refresh_all_fresh()` и `ManageSamplesView._rebuild_panels_from_cache()`.
- Результат построчно апсертится в `sample_status_cache` через `_executemany()` — один batch insert вместо N отдельных `upsert_sample_status_cache()`.
- При обычном открытии вкладки (без нажатия Update) кэш `sample_status_cache` **по-прежнему читается как есть** — этот запрос не заменяет чтение кэша, а заменяет только его **пересчёт**.

---

## 3. Замеры производительности (реальные данные)

Датасет: 130 samples, ~2.6 млн строк в `identification`.

| Вариант выполнения | Время |
|---|---|
| Без `LIMIT`/`OFFSET` (весь запрос целиком, все sample'ы) | **13 секунд** |
| С `LIMIT 20 OFFSET 0` (в конце запроса, после `GROUP BY`) | **8 секунд** |

**Вывод:** `LIMIT`/`OFFSET` почти не ускоряет запрос, потому что все агрегирующие CTE (`ident_counts` в первую очередь) обязаны просканировать **всю** таблицу `identification`, прежде чем можно будет отфильтровать/ограничить результат по `sample`. Отсюда и решение — не пытаться пагинировать через SQL, выполнять запрос целиком и работать с результатом как с готовым набором данных в памяти.

13 секунд на каждый Update — приемлемо как разовая операция по явному нажатию кнопки, но:
- Это узкое место для будущих проектов с ещё большим объёмом данных.
- Основной вклад — CTE `ident_counts`, судя по плану запроса (раздел 4), т.к. это `SCAN i` (полное сканирование `identification`) без использования индекса для группировки.

---

## 4. EXPLAIN QUERY PLAN — сырые данные

```
id,parent,notused,detail
3,0,0,MATERIALIZE sf_counts
10,3,0,SCAN spectre_file USING COVERING INDEX idx_spectre_file_sample
43,0,0,MATERIALIZE if_counts
51,43,0,SCAN sf USING COVERING INDEX idx_spectre_file_sample
53,43,0,SEARCH idf USING COVERING INDEX idx_ident_file_spectre (spectre_file_id=?)
66,43,0,CORRELATED SCALAR SUBQUERY 2
70,66,0,SEARCH i USING COVERING INDEX idx_ident_file (ident_file_id=?)
111,0,0,MATERIALIZE ident_counts
120,111,0,SCAN i
122,111,0,SEARCH s USING INTEGER PRIMARY KEY (rowid=?)
125,111,0,SEARCH sf USING INTEGER PRIMARY KEY (rowid=?)
128,111,0,USE TEMP B-TREE FOR GROUP BY
187,0,0,MATERIALIZE protein_counts
194,187,0,SCAN protein_identification_result USING COVERING INDEX idx_prot_ident_sample
233,0,0,SCAN smp USING INDEX sqlite_autoindex_sample_1
246,0,0,SEARCH sub USING INTEGER PRIMARY KEY (rowid=?)
260,0,0,SEARCH sfc USING AUTOMATIC COVERING INDEX (sample_id=?)
276,0,0,SEARCH ifc USING AUTOMATIC COVERING INDEX (sample_id=?)
293,0,0,SEARCH ic USING AUTOMATIC COVERING INDEX (sample_id=?)
308,0,0,SEARCH pc USING AUTOMATIC COVERING INDEX (sample_id=?)
329,0,0,SCALAR SUBQUERY 6
335,329,0,SCAN tool USING COVERING INDEX sqlite_autoindex_tool_1
349,0,0,SCALAR SUBQUERY 6
355,349,0,SCAN tool USING COVERING INDEX sqlite_autoindex_tool_1
414,0,0,SCALAR SUBQUERY 6
420,414,0,SCAN tool USING COVERING INDEX sqlite_autoindex_tool_1
439,0,0,SCALAR SUBQUERY 6
445,439,0,SCAN tool USING COVERING INDEX sqlite_autoindex_tool_1
459,0,0,SCALAR SUBQUERY 6
465,459,0,SCAN tool USING COVERING INDEX sqlite_autoindex_tool_1
```

### 4.1. Разбор узких мест

1. **`ident_counts` (id=111-128) — главный подозреваемый:**
   - `120,111,0,SCAN i` — полное сканирование таблицы `identification` (2.6 млн строк) **без использования индекса** для JOIN/GROUP BY — это сканирование по rowid без фильтра, т.к. группировка идёт по `sf.sample_id`, которого физически нет в таблице `identification` (она денормализована через `identification → spectre → spectre_file → sample`).
   - `122,111,0,SEARCH s USING INTEGER PRIMARY KEY` и `125,111,0,SEARCH sf USING INTEGER PRIMARY KEY` — для каждой из 2.6 млн строк `identification` выполняется поиск связанной `spectre` и `spectre_file` по PK (rowid) — это O(N log M), но с N=2.6 млн такие переходы (row-by-row nested loop через 2 JOIN) суммарно дают основной вклад в 13 секунд.
   - `128,111,0,USE TEMP B-TREE FOR GROUP BY` — сортировка/группировка через временное B-дерево (нет индекса, покрывающего `GROUP BY sf.sample_id` после JOIN).

2. **`if_counts` (id=43-70):** здесь есть `CORRELATED SCALAR SUBQUERY 2` — по сути, ещё один "мини-N+1" внутри одного CTE: для каждой строки `identification_file` выполняется `SEARCH i USING COVERING INDEX idx_ident_file` (проверка `NOT EXISTS`). Таблица `identification_file` намного меньше, чем `identification`, так что это не критично, но потенциально дублирует работу.

3. **`SCALAR SUBQUERY 6` — пятикратное повторение `SCAN tool`:** подзапрос `(SELECT COUNT(*) FROM tool)` в CTE `base` выполняется **пять раз** — по одному разу на каждый ROW видимо из-за того, как SQLite материализует CTE `base` (сканирование `smp` вместе со всеми LEFT JOIN). Таблица `tool` маленькая, поэтому не критично по времени, но concептуально это лишняя избыточность — константу стоит вынести из тела запроса и посчитать один раз отдельным вызовом (`get_tools_count()` уже существует как отдельный метод).

4. **Автоматические индексы (`AUTOMATIC COVERING INDEX`) на `sfc`/`ifc`/`ic`/`pc`** — SQLite сам создаёт временные индексы для JOIN по материализованным CTE. Это ожидаемо и не является проблемой само по себе.

---

## 5. Направления для будущей оптимизации (не реализуются сейчас)

Зафиксированы как гипотезы для отдельной задачи — не в рамках 0.7.0a4:

1. **Денормализация `sample_id` в `identification`** (или хотя бы в `spectre`) — убрало бы двойной JOIN (`identification → spectre → spectre_file`) в самом тяжёлом CTE `ident_counts`, заменив на прямой `GROUP BY sample_id` с индексом `identification(sample_id)`. Требует миграции схемы и обновления кода записи identifications (`add_identifications_batch`), а также бэкофилла для существующих проектов — весомая задача, не тривиальная правка.
2. **Индекс `identification(spectre_id, is_preferred, intensity_coverage)` (covering)** — может убрать необходимость доступа к самой таблице `identification` целиком, если SQLite сможет использовать covering index вместо `SCAN i`. Стоит проверить на реальных данных, даст ли это ускорение без денормализации.
3. **Вынести `(SELECT COUNT(*) FROM tool)` из CTE `base`** — считать `tools_count` один раз в Python (`get_tools_count()` уже есть) и передавать как константу в статус-калькуляцию, не как часть SQL. Простая правка, вероятно устранит 5-кратный `SCAN tool`.
4. **Материализация `if_counts` через `NOT EXISTS` → `LEFT JOIN ... WHERE ... IS NULL`** — альтернативная формулировка `empty_ident_files_count`, потенциально без `CORRELATED SCALAR SUBQUERY`, стоит сравнить планы.
5. **Кэшировать промежуточный результат ident_counts** отдельной пре-агрегированной таблицей, обновляемой инкрементально при вставке identifications batch (a-la materialized view) — радикальное решение для очень больших проектов, вне рамок текущего цикла разработки.

---

## 6. Решение по срокам

- Текущий запрос (раздел 2) **принят к использованию** в 0.7.0a4 как явное улучшение по сравнению с N+1 (полный пересчёт с 13 сек вместо кратно большего времени при поштучных `get_sample_stats()` в цикле по 130 sample'ам).
- Дальнейшая оптимизация (раздел 5) выносится в отдельный тикет/спецификацию и не блокирует релиз 0.7.0a4.
- При открытии тикета на оптимизацию — начать с пункта 3 (тривиально) и пункта 2 (индекс без миграции схемы), затем пункт 1 (денормализация) как наиболее трудоёмкий, но потенциально самый эффективный вариант.
