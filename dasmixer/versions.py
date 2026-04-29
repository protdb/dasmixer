"""Version constants for DASMixer project."""

# Версия приложения DASMixer
APP_VERSION = "0.2.0"

# Версия схемы файла проекта (.dasmix).
# Поднимается только тогда, когда меняется схема БД.
# Может отставать от APP_VERSION.
PROJECT_VERSION = "0.2.0"

# Минимальная версия проекта, для которой возможна миграция.
# Проекты ниже этой версии не открываются с миграцией.
MIN_SUPPORTED_PROJECT_VERSION = "0.1.0"
