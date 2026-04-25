# Этап 13, экспорт данных и мелкие улучшения

## Вкладка Export

Добавить в систему вкладку Data Export

Струкутра:
- System data
  - Содержит флаги (соответствуют таблицам в структуре БД):
    - Samples
    - Subsets
    - Tools
    - Spectra metadata
    - Identification file
    - Spectre file
    - Identification
    - Peptide match
    - Protein identifications
    - Protein quantifications
    - Project settings
  - Кнопка Export (CSV)
- Joined data
  - Флаги:
    - Sample details
    - Identifications
    - Protein identifications
    - Protein Statistics
    - One sample per file
  - Выбор формата данных:
    - CSV
    - XLSX
  - Кнопка Export
- Export MGF
  - Samples (кнопка и список, диалог множественного выбора)
  - By identification (radio group):
    - All
    - All preferred
    - All preferred by tool (Dropdown выбора Tool)
  - Чекбоксы:
    - Write offset from identification
    - Write spectra from identification
    - Write SEQ from identification (Dropdown: canonical/modified)
  - Радио Compression
    - GZIP
    - ZIP (All in one)
    - ZIP (One file per archive)
    - None
  - Кнопка Export
- Export MzTab
  - Выбор образцов
  - Выбор Метода LFQ

## Логика секций

Raw Export - экспорт as is из таблиц, с одним принципиальным исключением: не экспортируются BLOB-поля для spectre и других случаев. 

Для tool.settings и других JSON-данных (sample.additions) разворачиваем в отдельные колонки ключи объекта JSON, если данные в виде объекта. Вложенные объекты развернуть не пытаемся. Если тип данных сложный (объект, список)

Joined exports
Данные системных представлений. Для
- Sample details выводим данные образцов, которые отображаются в `dasmixer/gui/views/manage_samples_view.py`
- Identifications: Project.get_joined_peptide_data
- Protein identifications: Project.get_protein_results_joined
- Protein statistics: Project.get_protein_statistics (Здесь не разделяем по образцам в любом случае)

Если установлен флаг One file per sample, то делаем по выходному файлу указанных типов на каждый образец, т.е. разделяем данные на образцы

Export MGF
- С помощью Pyteomics генерируем MGF-файлы для выбранных образцов с учетом данных идентификаций. В принципе здесь всё должно быть понятно:
- либо сохраняем все данные, либо только спектры, для которых есть preferred-идентификация одним из инструментов
- Если указано, что нужно взять из идентификации charge и/или Seq или учесть isotope offset, то измененные данные также должны быть прописаны в MGF
- Compression позволяет при записи "на ходу" складывать файлы в архив указанного вида и указанной структуры (по одному в gzip, zip либо общий, либо отдельный на каждый файл)

Export MzTab: позволяет экспортировать результирующие идентификации белков и пептидов в формат MzTab. Для этого используется библиотека mztabwriter, она обитает тут рядом: `/home/gluck/PycharmProjects/MZTabWriter`. Экспортируем результирующие данные по образцу за раз. Нехватающие типовые поля добавляем также на эту форму и сохраняем в project_settings

## Общая специфика экспорта

Когда вкладка неактивна, удаляем контролы, введенные данные сохраняем "под рукой", при переходе на вкладку обратно - создаём по новой контролы.

