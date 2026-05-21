# Спецификация Этапа 5: Система отчетов

## Обзор

Этап 5 завершает основной функционал приложения реализацией системы генерации, хранения, просмотра и экспорта отчетов. Система отчетов представляет собой модульную архитектуру с поддержкой плагинов, интеграцией с базой данных проекта и интерактивным просмотром через pywebview.

## Архитектура системы отчетов

### Общая концепция

Отчет (Report) - это модуль, который:
1. Получает данные из проекта
2. Выполняет анализ/обработку
3. Генерирует результаты в виде графиков (Plotly) и/или таблиц (pandas DataFrame)
4. Сохраняет результаты в БД проекта
5. Предоставляет интерфейсы для просмотра и экспорта

### Основные компоненты

```
api/reporting/
├── __init__.py
├── base.py                 # Базовый класс BaseReport
├── registry.py             # Registry для отчетов
├── viewer.py               # Обертка для pywebview
├── templates/              # Jinja2 шаблоны
│   └── report.html.j2
└── reports/                # Конкретные реализации
    ├── __init__.py
    └── sample_report.py    # Пример отчета

gui/views/tabs/reports/
├── __init__.py
├── reports_tab.py          # Главная вкладка
├── shared_state.py         # Разделяемое состояние
├── settings_section.py     # Общие настройки
└── report_item.py          # Компонент для одного отчета
```

---

## 1. Изменения в схеме БД

### Файл: `api/project/schema.py`

#### 1.1. Модификация таблицы `generated_reports`

**Старая структура (удалить):**
```sql
CREATE TABLE IF NOT EXISTS generated_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime TEXT NOT NULL,
    settings TEXT,
    plot BLOB,
    table_data BLOB
);
```

**Новая структура:**
```sql
CREATE TABLE IF NOT EXISTS generated_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    plots BLOB,
    tables BLOB,
    project_settings TEXT,
    tools_settings TEXT,
    report_settings TEXT
);

CREATE INDEX IF NOT EXISTS idx_generated_reports_name ON generated_reports(report_name);
CREATE INDEX IF NOT EXISTS idx_generated_reports_created ON generated_reports(created_at);
```

#### 1.2. Новая таблица `report_parameters`

```sql
CREATE TABLE IF NOT EXISTS report_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT UNIQUE NOT NULL,
    parameters TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_parameters_name ON report_parameters(report_name);
```

---

## 2. План реализации

### Этап 1: Базовая инфраструктура
1. Обновить схему БД
2. Создать базовый класс `BaseReport`
3. Создать `ReportRegistry`
4. Создать `ReportMixin` для Project
5. Создать HTML шаблон

### Этап 2: Пример и viewer
1. Создать `SampleReport`
2. Создать `ReportViewer`
3. Тестирование

### Этап 3: GUI
1. Создать компоненты вкладки Reports
2. Интегрировать в главное окно

### Этап 4: Тестирование
1. Интеграционное тестирование
2. Исправление багов

Полная детальная спецификация будет создана в следующем сообщении из-за ограничений.
