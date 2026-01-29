# Quick Start Guide - Этап 3.2

## 🚨 КРИТИЧНО: Сначала выполни это!

### Добавь метод в Project класс

**Файл:** `api/project/project.py`

**Где:** После метода `get_spectrum_full` (строка ~700), перед `# Identification file operations`

**Что вставить:** См. файл `api/project/project_patch.py` или скопируй из `api/project/project_spectra_mapping.py`

---

## ✅ Быстрый тест CLI

```bash
# 1. Создать проект
python main.py test.dasmix create

# 2. Добавить группу
python main.py test.dasmix subset add --name "Test" --color "#FF5733"

# 3. Список групп
python main.py test.dasmix subset list

# 4. Импорт MGF (если есть тестовый файл)
python main.py test.dasmix import mgf-file \
    --file path/to/file.mgf \
    --sample-id "Sample1" \
    --group Control
```

---

## 🎨 Быстрый тест GUI

```bash
# Запуск GUI
python main.py

# Или открыть проект сразу
python main.py test.dasmix
```

**Что проверить:**
- ✅ Создание проекта через "Create New Project"
- ✅ Открытие проекта через "Open Project"
- ✅ Список недавних проектов на стартовом экране
- ✅ Вкладка Samples: добавление группы
- ✅ Вкладка Samples: список групп с количеством образцов

---

## 📋 Что работает

### CLI ✅
- ✅ Создание проекта
- ✅ Управление группами (add/delete/list)
- ✅ Импорт MGF (file и pattern)
- ⚠️ Импорт идентификаций (заглушка)

### GUI ✅
- ✅ Создание/открытие проектов
- ✅ Стартовый экран с недавними проектами
- ✅ Меню приложения
- ✅ Вкладки (Samples/Peptides/Proteins/Analysis)
- ✅ Samples: добавление групп
- ⚠️ Samples: импорт данных (через CLI)
- ⚠️ Peptides: поиск (заглушка)
- ⚠️ Графики (заглушка)

---

## ❌ Что НЕ работает (TODO)

1. **Импорт через GUI** - используй CLI
2. **Таблица образцов** - placeholder
3. **Удаление групп** - кнопка не работает
4. **Поиск идентификаций** - нет данных
5. **Графики** - не интегрированы

---

## 📚 Документация

- **Полная спецификация:** `docs/project/spec/STAGE3_2_SPEC.md`
- **Детальное резюме:** `docs/project/STAGE3_2_SUMMARY.md`
- **TODO список:** `STAGE3_2_TODO.md`
- **Патч для Project:** `api/project/project_patch.py`

---

## 🐛 Проблемы?

1. **"Project not initialized"** → Добавь метод `get_spectra_idlist` в Project
2. **"Parser not found"** → Проверь что MGF парсер зарегистрирован в `api/inputs/__init__.py`
3. **GUI не запускается** → Проверь что все зависимости установлены: `poetry install`
4. **Ошибка импорта** → Проверь что файл MGF существует и корректен

---

## 🎯 Следующие шаги

1. ⚠️ Добавь метод в Project
2. Протестируй CLI
3. Протестируй GUI
4. Создай диалог импорта для GUI
5. Доделай таблицу образцов

---

## 💡 Советы

- Используй CLI для импорта данных (GUI импорт не готов)
- Смотри логи в консоли при ошибках
- Конфиг хранится в `~/.config/dasmixer/config.json` (Linux)
- Проекты - это файлы SQLite с расширением `.dasmix`

---

**Готов приступать!** 🚀
