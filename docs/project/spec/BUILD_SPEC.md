# Спецификация: build.py — универсальный скрипт сборки DASMixer

**Статус:** На согласовании  
**Дата:** 2026-06-24  
**Версия требований:** BUILD_REQUIREMENTS.md

---

## 1. Общее

Единый Python-скрипт `build.py` в корне репозитория. Запускается в активном virtualenv Poetry:

```
poetry run python build.py <command> [args]
# или после poetry env activate:
python build.py <command> [args]
```

Использует **Typer** для CLI. Никаких внешних зависимостей, кроме уже присутствующих в окружении (`twine`, `gh`, `pyinstaller`).

---

## 2. Константы и конфигурация (топ файла)

```python
REPO_ROOT = Path(__file__).resolve().parent

PACKAGES = ["dasmixer-core", "dasmixer-gui", "dasmixer-cli", "metapackage"]
# Порядок важен: core → gui → cli → metapackage

PYPI_PACKAGE_NAMES = ["dasmixer-core", "dasmixer-gui", "dasmixer-cli", "dasmixer"]
# Имена на PyPI (metapackage публикуется как 'dasmixer')

ISCC_PATH = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
CHANGELOG_DIR = REPO_ROOT / "docs" / "project" / "changes"

TESTPYPI_CHECK_URL = "https://test.pypi.org/pypi/{name}/{version}/json"
PYPI_URL = "https://pypi.org/project/{name}/"
TESTPYPI_URL = "https://test.pypi.org/project/{name}/"
```

---

## 3. Вспомогательные функции

### 3.1 `get_current_version() -> str`

Читает текущую версию из `dasmixer-core/pyproject.toml` (первое вхождение `version = "..."`).  
Завершает скрипт с ошибкой, если версия не найдена.

### 3.2 `validate_version(version: str) -> None`

Проверяет, что строка соответствует паттерну `^\d+\.\d+\.\d+` (PEP 440 совместимый префикс: `1.2.3`, `0.6.0rc1`, `0.6.0a2`).  
При несоответствии — `typer.Exit(1)` с сообщением об ошибке.

### 3.3 `set_version(version: str) -> None`

Делегирует в `build_tools/set_version.py`:

```python
import subprocess
result = subprocess.run(
    [sys.executable, str(REPO_ROOT / "build_tools" / "set_version.py"), version],
    check=True
)
```

При ненулевом коде возврата — завершиться с ошибкой.

### 3.4 `build_python_packages() -> list[Path]`

Собирает все четыре пакета по очереди (`PACKAGES`).  
Для каждого:
```python
subprocess.run(["poetry", "build"], cwd=REPO_ROOT / pkg, check=True)
```

После сборки собирает список всех файлов `*.whl` и `*.tar.gz` из `{pkg}/dist/` каждого пакета.  
Возвращает список `Path`-объектов найденных артефактов.  
Если список пуст — завершиться с ошибкой `"No build artifacts found"`.

### 3.5 `check_artifacts(artifacts: list[Path]) -> None`

Проверяет, что для каждого пакета из `PACKAGES` есть хотя бы один артефакт.  
Если нет — завершиться с ошибкой с указанием, какой пакет не собрался.

### 3.6 `upload_to_testpypi(artifacts: list[Path]) -> None`

```python
subprocess.run(["twine", "upload", "--repository", "testpypi", *map(str, artifacts)], check=True)
```

### 3.7 `upload_to_pypi(artifacts: list[Path]) -> None`

```python
subprocess.run(["twine", "upload", *map(str, artifacts)], check=True)
```

### 3.8 `check_testpypi_availability(version: str, timeout_sec: int = 120) -> None`

Проверяет доступность всех четырёх пакетов на TestPyPI.  
Для каждого имени из `PYPI_PACKAGE_NAMES`:

- Формирует URL: `https://test.pypi.org/pypi/{name}/{version}/json`
- Делает GET-запрос (через `urllib.request`, без сторонних библиотек)
- Если статус 200 — пакет доступен
- Если не 200 — ждёт 5 секунд, повторяет, пока не истечёт `timeout_sec`
- Если истёк таймаут — завершиться с ошибкой с указанием имени пакета

Выводит прогресс: `"Waiting for dasmixer-core {version} on TestPyPI... (30s)"`.

### 3.9 `build_windows_installer(version: str) -> Path`

**Шаг 1 — PyInstaller:**

```python
subprocess.run(
    ["pyinstaller", "dasmixer.spec", "--clean", "-y"],
    cwd=REPO_ROOT,
    check=True
)
```

Проверяет наличие `dist/dasmixer/dasmixer.exe` после сборки.  
Если нет — завершиться с ошибкой.

**Шаг 2 — Inno Setup:**

```python
subprocess.run([ISCC_PATH, "dasmixer.iss"], cwd=REPO_ROOT, check=True)
```

Ожидаемый артефакт: `dist/setup/DASMixer{version}-setup.exe`  
(имя берётся из `dasmixer.iss`: `OutputBaseFilename=DASMixer{#MyAppVersion}-setup`).  
Если файл не найден — завершиться с ошибкой.

Возвращает `Path` к `.exe` файлу.

### 3.10 `archive_installer(exe_path: Path) -> Path`

Упаковывает `.exe` в `.zip` рядом с ним:
```python
zip_path = exe_path.with_suffix(".zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(exe_path, exe_path.name)
```
Возвращает `Path` к `.zip`.

### 3.11 `create_github_release(version: str, exe_path: Path, artifacts: list[Path]) -> str`

**Читает changelog:**  
Файл `docs/project/changes/v{version}.md`.  
Если файл не существует — завершиться с ошибкой `"Changelog not found: docs/project/changes/v{version}.md"`.

**Создаёт release через `gh`:**

```python
subprocess.run([
    "gh", "release", "create",
    f"v{version}",
    "--title", f"DASMixer v{version}",
    "--notes-file", str(changelog_path),
    str(exe_path),           # .exe установщик
    *map(str, artifacts),    # все .whl и .tar.gz
], cwd=REPO_ROOT, check=True)
```

> `gh release create` создаёт тег автоматически, если он не существует.

После создания получает URL release:
```python
result = subprocess.run(
    ["gh", "release", "view", f"v{version}", "--json", "url", "--jq", ".url"],
    capture_output=True, text=True, check=True, cwd=REPO_ROOT
)
release_url = result.stdout.strip()
```

Возвращает URL.

---

## 4. Команды Typer

### 4.1 `build.py set-version <version>`

**Описание:** Только обновляет версию во всех файлах проекта.

**Алгоритм:**
1. `validate_version(version)`
2. `set_version(version)`
3. Вывести: `"Version updated to {version}"`

**Завершается с ошибкой:** если `set_version` вернул ненулевой код.

---

### 4.2 `build.py pypi [version] [--prod]`

**Описание:** Собирает Python-пакеты и загружает на PyPI (Test по умолчанию, прод при `--prod`).

**Сигнатура:**
```python
@app.command()
def pypi(
    version: Optional[str] = typer.Argument(None),
    prod: bool = typer.Option(False, "--prod", help="Upload to production PyPI"),
):
```

**Алгоритм:**
1. Если `version` передан:
   - `validate_version(version)`
   - `set_version(version)`
2. `artifacts = build_python_packages()`
3. `check_artifacts(artifacts)`
4. Если `--prod`:
   - `upload_to_pypi(artifacts)`
   - Вывести ссылки на PyPI для всех пакетов из `PYPI_PACKAGE_NAMES`
5. Иначе (TestPyPI):
   - `upload_to_testpypi(artifacts)`
   - Вывести ссылки на TestPyPI для всех пакетов

**Завершается с ошибкой:** при любой ошибке сборки или загрузки.

---

### 4.3 `build.py internal [version]`

**Описание:** Сборка Windows-установщика для внутреннего распространения (тестировщикам).

**Сигнатура:**
```python
@app.command()
def internal(
    version: Optional[str] = typer.Argument(None),
):
```

**Ограничение платформы:**  
В начале команды:
```python
if sys.platform != "win32":
    typer.echo("Error: 'internal' command is only available on Windows.", err=True)
    raise typer.Exit(1)
```

**Алгоритм:**
1. Если `version` передан:
   - `validate_version(version)`
   - `set_version(version)`
2. `current_version = get_current_version()`
3. `exe_path = build_windows_installer(current_version)`
4. `zip_path = archive_installer(exe_path)`
5. Вывести:
   ```
   Installer: dist/setup/DASMixer{version}-setup.exe
   Archive:   dist/setup/DASMixer{version}-setup.zip
   ```

**Завершается с ошибкой:** при любой ошибке сборки или отсутствии артефактов.

---

### 4.4 `build.py release <version>`

**Описание:** Полный release-цикл: версия → пакеты → (Windows) → GitHub → PyPI.

**Сигнатура:**
```python
@app.command()
def release(
    version: str = typer.Argument(...),
):
```

**Алгоритм:**

#### Шаг 0 — Валидация
1. `validate_version(version)`
2. `current_version = get_current_version()`
3. Если `version == current_version`:
   - Запросить подтверждение через `typer.confirm`:  
     `"Version {version} is already set. Are you sure you want to release without bumping?"`  
   - При отказе — `raise typer.Exit(0)`
4. Проверить наличие changelog: `docs/project/changes/v{version}.md`  
   Если нет — завершиться с ошибкой (`"Changelog not found: ..."`)
5. Запросить финальное подтверждение:  
   `"You are about to publish DASMixer v{version} to GitHub and PyPI. Proceed?"`  
   При отказе — `raise typer.Exit(0)`

#### Шаг 1 — Обновление версии
6. Если `version != current_version`: `set_version(version)`

#### Шаг 2 — Сборка Python-пакетов
7. `artifacts = build_python_packages()`
8. `check_artifacts(artifacts)`

#### Шаг 3 — Windows (только если `sys.platform == "win32"`)

```python
if sys.platform == "win32":
    exe_path = build_windows_installer(version)
    # create_github_release включает exe_path
    release_url = create_github_release(version, exe_path, artifacts)
else:
    typer.echo("Skipping Windows build (not on Windows).")
    release_url = None
```

> На не-Windows платформе GitHub release **не создаётся** (т.к. установщика нет).  
> Это поведение принято как допустимое — release создаётся только при сборке под Windows.

#### Шаг 4 — TestPyPI
9. `upload_to_testpypi(artifacts)`
10. `check_testpypi_availability(version)`

#### Шаг 5 — PyPI (прод)
11. `upload_to_pypi(artifacts)`

#### Шаг 6 — Итог
Вывести:
```
=== Release DASMixer v{version} complete ===

GitHub Release: {release_url}           # только если создавался
PyPI:           https://pypi.org/project/dasmixer/{version}/
```

**Полностью завершается с ошибкой при:**
- Любой ошибке сборки (`subprocess.CalledProcessError`)
- Отсутствии артефактов любого пакета
- Отсутствии changelog
- Таймауте ожидания доступности на TestPyPI
- Ошибке создания GitHub release

---

## 5. Обработка ошибок — общие правила

- Все `subprocess.run(..., check=True)` перехватываются на уровне команды:
  ```python
  except subprocess.CalledProcessError as e:
      typer.echo(f"Error: command failed with exit code {e.returncode}", err=True)
      raise typer.Exit(1)
  ```
- Промежуточные шаги выводят заголовок перед выполнением:
  ```
  --- Building dasmixer-core ---
  --- Building Windows installer (PyInstaller) ---
  --- Uploading to TestPyPI ---
  ```
- Успешные шаги подтверждаются: `"✓ dasmixer-core built successfully"`

---

## 6. Структура файла build.py

```python
#!/usr/bin/env python3
"""
build.py — DASMixer unified build script.

Commands:
    set-version <version>   — Update version in all project files
    pypi [version] [--prod] — Build and upload Python packages to PyPI
    internal [version]      — Build Windows installer (Windows only)
    release <version>       — Full release pipeline
"""

import sys
import subprocess
import zipfile
import urllib.request
import time
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="DASMixer build tool")

# --- Constants ---
REPO_ROOT = Path(__file__).resolve().parent
# ...

# --- Helper functions ---
def get_current_version() -> str: ...
def validate_version(version: str) -> None: ...
def set_version(version: str) -> None: ...
def build_python_packages() -> list[Path]: ...
def check_artifacts(artifacts: list[Path]) -> None: ...
def upload_to_testpypi(artifacts: list[Path]) -> None: ...
def upload_to_pypi(artifacts: list[Path]) -> None: ...
def check_testpypi_availability(version: str, timeout_sec: int = 120) -> None: ...
def build_windows_installer(version: str) -> Path: ...
def archive_installer(exe_path: Path) -> Path: ...
def create_github_release(version: str, exe_path: Path, artifacts: list[Path]) -> str: ...

# --- Commands ---
@app.command("set-version")
def cmd_set_version(version: str = typer.Argument(...)): ...

@app.command("pypi")
def cmd_pypi(version: Optional[str] = typer.Argument(None),
             prod: bool = typer.Option(False, "--prod")): ...

@app.command("internal")
def cmd_internal(version: Optional[str] = typer.Argument(None)): ...

@app.command("release")
def cmd_release(version: str = typer.Argument(...)): ...

if __name__ == "__main__":
    app()
```

---

## 7. Зависимости окружения

Скрипт предполагает, что в активном окружении доступны:

| Инструмент | Откуда |
|---|---|
| `python` | активный Poetry venv |
| `poetry` | глобально или в PATH |
| `twine` | в venv (`pip install twine`) |
| `pyinstaller` | в venv |
| `gh` (GitHub CLI) | глобально, авторизован |
| `ISCC.exe` | установлен Inno Setup 6 в стандартный путь |

Токены PyPI берутся из `~/.pypirc` (стандарт twine). Скрипт их не трогает.

---

## 8. Файловая структура артефактов

```
dasmixer/                          # repo root
├── build.py                       # NEW — этот скрипт
├── build_tools/
│   └── set_version.py             # существующий (делегирование)
├── dasmixer-core/dist/
│   ├── dasmixer_core-X.Y.Z.whl
│   └── dasmixer_core-X.Y.Z.tar.gz
├── dasmixer-gui/dist/
│   └── ...
├── dasmixer-cli/dist/
│   └── ...
├── metapackage/dist/
│   └── ...
└── dist/
    ├── dasmixer/                  # PyInstaller output
    │   ├── dasmixer.exe
    │   └── _internal/
    └── setup/                     # Inno Setup output
        ├── DASMixer{version}-setup.exe
        └── DASMixer{version}-setup.zip   # NEW — archive_installer()
```

---

## 9. Открытые вопросы (решены)

| Вопрос | Решение |
|---|---|
| Как создавать GitHub release? | `gh release create` (тег создаётся автоматически) |
| Проверка TestPyPI — как? | HTTP GET к `/pypi/{name}/{version}/json`, статус 200 |
| Порядок шагов в `release` | версия → пакеты → [Windows+GitHub] → TestPyPI → PyPI |
| Имя zip-архива | `exe_path.with_suffix(".zip")` |
| Версия в `pypi [version]` | обновить через `set_version`, затем собрать |
| Расположение `build.py` | корень репозитория |
| `poetry build` — как запускать | `subprocess.run(["poetry", "build"], cwd=pkg_dir)` |
| Токены PyPI | из `~/.pypirc`, скрипт не трогает |
| `release` без Windows | GitHub release не создаётся, только PyPI |
