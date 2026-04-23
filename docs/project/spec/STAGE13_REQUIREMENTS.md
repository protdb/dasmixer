# Этап 13, экспорт данных и мелкие улучшения

## Вкладка Export

Добавить в систему вкладку Export

Струкутра:
- Raw data exprot
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
- Joined exprots
  - Флаги:
    - Sample details
    - Identifications
    - Protein identifications
    - Protein statistics
    - Split per sample
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

Логика секций:
Raw Export - экспорт идентификаций ка