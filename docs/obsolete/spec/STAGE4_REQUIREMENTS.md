# Доработки этапа 4

## Фаза 4_1

Эти доработки нужны для дальнейшей интеграции функционала.

### Универсальное представление данных

Реализуется отдельным методом get_joined_peptide_data() в Project, который добавляет возможность фильтровать данные. SQL для основного запроса:
```sql
select
sb.sample, sb.subset, sb.sample_id, sb.id as subset_id, s.seq_no, s.scans, s.charge, s.rt, s.pepmass, s.intensity, id.*, mp.*
from
spectre as s
left join
(select sm.id as sample_id, f.id as spectre_file_id, sm.name as sample, sb.name as subset, sb.id as subset_id 
from sample sm, subset sb, spectre_file f where sm.subset_id = sb.id and f.sample_id = sm.id) as sb
on sb.spectre_file_id = s.spectre_file_id
left join
    (select i.spectre_id, t.name as tool, t.id as tool_id i.id as identification_id, i.sequence, i.canonical_sequence, i.ppm, i.is_preferred 
     from identification i, tool t where t.id = i.tool_id) as id 
        on id.spectre_id = s.id
left join
    (select m.matched_sequence, m.matched_ppm, m.protein_id, m.identification_id, m.unique_evidence, p.gene
     from peptide_match m, protein p where p.id = m.protein_id) as mp on mp.identification_id = id.identification_id
```

Должен быть доступен фильтр (опциональные параметры запроса) по:
- is_preferred (is_preferred = true)
- sequence_identified (sequence is not null)
- protein_identified (protein_id is not null)
- sample
- subset
- sample_id
- subset_id
- sequence (через LIKE)
- canonical_sequence (через LIKE)
- matched_sequence (через LIKE)
- seq_no
- scans
- tool
- tool_id

### Финализация просмотра графиков спектров.

Вкладка Peptides, блок Search and view Identifications. Нужно:
- сделать вывод данных в таблице и фильтр на основе project.get_joined_peptide_data(), который описан выше
- При клике по строке в таблице должен перерисовываться график. График должен отрисовываться с помощью функции `make_full_spectrum_plot` из `api/spectra/plot_flow.py`
- В качетсве входных параметров передаются параметры разметки ионов, параметры выбранного спектра, значения sequence, текст заголовков.
- Для этого делаем ещё метод в project, который по id спектра отдает все необходимые для отрисовки данные (включая массивы для самого спектра)
- Отрисовываются данные всегда по одному спектру и всем идентификациям этого спектра.
- Спектр показываем с возможностью интерактивного просмотра (см. `gui/components/plotly_viewer.py`)

### Изменения в логике работы кнопок

Сейчас по вкладке peptides разбросано много разных кнопок, что на самом деле крайне неудобно. Нужно упростить логику
для пользователя.
- Создать блок "Actions", в котором есть кнопка "Calculate peptides" и `ft.ExpansionPanel` (свернут по умолчанию) с заголовком "Advanced options"
- Все кнопки со страницы кроме Load sequences переезжают в Advanced options
- Рядом с кнопкой Load sequences показываем количество строк в таблице protein, чтобы было понятно, сколько белков сейчас есть в БД
- ПО кнопке Calculate peptides выполняется следующая последовательность действий (уже реализованных и навешанных на разные кнопки):
  - Match proteins to identifications
  - Calculate Ion coverage
  - Calculate PPM and... for protein identifications
  - Run identification matching

### Расширенное управление инструментами

Там же на вкладке peptides в блоке Tool Settings для каждого из инструментов должно быть можно прописать минимальную и максимальную длину пептида (применительно к canonical_sequence)

Параметры нужно пробросить в функцию `select_preferred_identifications()` и фильтровать этим критериям идентификации (слишком короткие и слишком длинные отбрасываются). По умолчанию - от 7 до 30.

### Расширение данных о белках

В БД нужно расширить таблицу protein, добавив поля:
- name
- uniprot_data (хранится как объект UniprotData в pickle и gzip, получен из библиотеки uniprot_meta_tool)

### Изменение структуры таблицы tool

Нужно в tool (и в диалог создания tool на вкладке samples) изменить принцип работы с полями.
Сейчас в таблице есть name (заполняется пользователем) и type (выбирается парсер).
Вместо type нужно создать и использовать новое поле parser. А поле type должно принимать одно из двух значений по выбору пользователя:
- Library
- De Novo

## Фаза 4_2

На этой фазе создаем из не очень работающей заготовки вкладку "Идентификации белков". Пользовательский интерфейс:
- Блок "Protein detection": Позволяет задать основные настройки поиска достоверных идентификаций белков:
  - Мин кол-во пептидов
  - Мин кол-во уникальных пептидов
  - Кнопка "Calculate protein identifications": вызывает функцию `find_protein_identifications()` из `api/proteins/map_identifications.py`, сохраняет данные в `protein_identifications_result`
- Блок "Label-free quantification", содержит параметры расчета алгоритмов квантификации. Содержит контролы:
  - Чекбокс emPAI
  - Чекбокс iBAQ
  - Чекбокс NSAF
  - Чекбокс Top3
  - emPAI base value (число, по умолчанию 10)
  - Выпадающий список Enzyme (пока одно значение, trypsin)
  - Минимальная и максимальная длина теоретического пептида (по умолчанию 7-30)
  - Числовое поле max clevage sites (по умолчанию 2)
  - Кнопка Calculate LFQ: функция `calculate_lfq()` из `api/proteins/lfq.py`
- Таблица данных: показывается объединение данных из таблиц `protein_identification_result` и `protein_quantification result`. Таблица должна содержать:
  - sample
  - subset
  - protein_id
  - gene
  - weight
  - peptide_count
  - unique_evidence_count
  - coverage_percent
  - EmPAI
  - iBAQ
  - NSAF
  - Top3

Доработки project:
- Добавить методы получения/сохранения данных protein_identification_result, protein_quantification_result, а также методы для их очистки в случае если нужно выполнить повторный расчет значений
- Добавить вызов представления для отображения таблицы данных
- Добавить метод получения идентифицированных белков, используемый при расчете LFQ (см. #TODO в функции calculate_lfq())
- Добавить поле intensity_sum (REAL, nullable) в таблицу protein_identification_result (никаких миграций, только изменение схемы).

Технические детали:
- Необходимо обратить внимание на текущую реализацию вкладки пептидов, модуль `gui/views/tabs/peptides`, делать технически максимально близко к нему, т.е.:
  - использовать такие же контролы
  - разделить на модули в такой же логике