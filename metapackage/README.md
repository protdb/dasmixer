# DASMixer

DASMixer — кроссплатформенное десктопное приложение для сравнительной протеомики.

Этот метапакет устанавливает все компоненты DASMixer:

- **dasmixer-core** — API для работы с проектами, вычисления и импорт данных
- **dasmixer-gui** — графический интерфейс (Flet)
- **dasmixer-cli** — CLI-инструменты для управления проектами

## Установка

```bash
pip install dasmixer
```

## Использование

```bash
# Запустить GUI
dasmixer

# Открыть проект в GUI
dasmixer path/to/project.dasmix

# CLI-инструменты
dasmixer-cli --help
dasmixer-cli create path/to/project.dasmix
dasmixer-cli subset list path/to/project.dasmix
```

Подробнее: https://github.com/protdb/dasmixer