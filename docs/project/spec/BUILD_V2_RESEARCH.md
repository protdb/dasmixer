# BUILD_V2_RESEARCH.md — Расширение сборочного пайплайна DASMixer

**Статус:** исследование (предварительный анализ, реализация не проводилась)  
**Дата:** 2026-09-01  
**Цель:** спроектировать единый процесс сборки: Windows (InnoSetup) + PyPI + Conda + Snap + AppImage одной командой `build.py release`, заложить `--add` для расширения релиза новыми артефактами, отдельная команда `build.py conda`, задел под macOS.

---

## 1. Что есть сейчас

### 1.1. `build.py` (команды)

| Команда | Описание |
|---|---|
| `set-version <ver>` | Через `build_tools/set_version.py` синхронизирует версию в 8 файлах (pyproject, versions.py, metapackage, dasmixer.iss) |
| `pypi [ver] [--prod]` | Poetry build всех 4 пакетов → twine upload (TestPyPI или PyPI) |
| `internal [ver]` | Только Windows: PyInstaller (`dasmixer.spec`) → Inno Setup (`dasmixer.iss`) → готовый .exe инсталлятор |
| `release <ver>` | bump версии → build wheels → Windows internal → `gh release create` → TestPyPI → PyPI |

**Ограничения текущего `release`:**
- Собирает Windows-инсталлятор только если `sys.platform == "win32"` (иначе пропускает). Нет ни Linux-, ни macOS-веток.
- Нет понятия "расширить существующий релиз" (`--add`).
- Нет conda, appimage, snap, macOS.

### 1.2. `dasmixer.spec` (PyInstaller)

- Onedir-сборка под **Windows x64**.
- **Жёстко Windows-специфичен:** подключает `clr_loader/ffi/dlls/amd64`, `webview/lib` (.NET DLL), `webview.platforms.winforms/edgechromium`, `clr`, `pythonnet`, иконка `.ico`.
- **Безусловно исключает** Linux- и macOS-зависимости: `webview.platforms.gtk`, `webview.platforms.cocoa`, `gi`, `objc`.
- PyInstaller **не подхватывает GObject Introspection typelibs** (GTK/WebKit) автоматически — на Linux нужно ручное указание datas для `/usr/lib/.../girepository-1.0/*.typelib`.

### 1.3. `dasmixer.iss` (Inno Setup)

- Windows-only инсталлятор: ассоциация `.dasmix` через реестр, desktop/start-menu ярлыки, uninstaller.
- Версия синхронизируется через `set_version.py`.

### 1.4. `build_tools/set_version.py`

- Синхронизирует версию в: `dasmixer-core/pyproject.toml`, `dasmixer-gui/pyproject.toml`, `dasmixer-cli/pyproject.toml`, `metapackage/pyproject.toml`, корневой `pyproject.toml`, `versions.py`, metapackage `__init__.py`, `dasmixer.iss`.
- **Не трогает** (пока нет): snapcraft.yaml, conda meta.yaml.

### 1.5. Зависимости по платформам

Уже разделены в `dasmixer-core/pyproject.toml` и `dasmixer-gui/pyproject.toml` через `sys_platform` markers:

```
dasmixer-core:
  proteins → npysearch (Linux/Mac) | npysearch-win (Windows)

dasmixer-gui:
  pywebview[gtk] (Linux) | pywebview (Windows)
  pythonnet (Windows only)
```

**Нет ветки для `sys_platform == 'darwin'`** — pywebview на macOS требует pyobjc-фреймворков (Cocoa, WebKit), которых нет в зависимостях.

---

## 2. Целевая архитектура

### 2.1. Новая раскладка файлов

```
packaging/
├── appimage/
│   ├── dasmixer.desktop          # Exec=dasmixer %f, MimeType=application/x-dasmix, Icon=dasmixer
│   ├── dasmixer.appdata.xml      # AppStream metadata (опционально)
│   └── AppRun                    # генерируется при сборке (линк на entrypoint)
├── snap/
│   └── snapcraft.yaml            # strict confinement, base: core24, extension: gnome
├── conda/
│   ├── meta.yaml                 # {% set version = "..." %} — синхронизируется set_version.py
│   ├── build.sh                  # linux: pip install локальных .whl
│   └── bld.bat                   # windows: pip install локальных .whl
└── macos/
    └── entitlements.plist         # задел под codesign (untested)

dasmixer.spec                      # platform-conditional
dasmixer.iss                       # без изменений (Windows-only)

build_tools/
├── set_version.py                 # + snapcraft.yaml, conda/meta.yaml
└── wsl_bootstrap.sh               # NEW: инициализация WSL-окружения для Linux-сборки
```

### 2.2. Целевые команды `build.py`

```
build.py set-version <version>
build.py pypi [version] [--prod]
build.py internal [version]                        # Windows installer (существующая)
build.py linux [version] [--appimage] [--snap]     # NEW, только на Linux
build.py conda [version] [--label dev|main]         # NEW, платформа = текущая
build.py release <version> [--add] [--wsl-dist DISTRO]  # расширенная
```

**`build.py linux`** (только `sys.platform == "linux"`):
1. `pyinstaller dasmixer.spec` (Linux-ветка) → `dist/dasmixer/` (onedir).
2. `linuxdeploy` + `linuxdeploy-plugin-gtk` → `dist/DASMixer-{version}-x86_64.AppImage`.
3. `snapcraft` (strict, `extension: gnome`) → `dist/dasmixer_{version}_amd64.snap`.

**`build.py conda`** (любая платформа):
1. `conda-build packaging/conda` (использует собранные wheel из `*/dist/*.whl`, не ждёт PyPI).
2. При `--label` — `anaconda upload` в личный/лабораторный канал Anaconda.org.

**`build.py release <version> [--add] [--wsl-dist DISTRO]`:**

*Без `--add`* (основной запуск, ожидаем на Windows-хосте):
1. Bump версии (`set_version`, changelog check).
2. `poetry build` — 4 wheel/tar.gz.
3. `gh release create v{version}` с инсталлятором и wheel'ами (Windows-артефакты — на Windows; на Linux: сразу AppImage/Snap — корректно, но команда рассчитана на Windows-хост).
4. Shell-вызов в WSL: `wsl.exe -d <distro> poetry run python build.py release {version} --add`.
5. Conda-build на текущей (Windows) машине → `gh release upload` + `anaconda upload`.
6. Тестовая загрузка на TestPyPI → проверка доступности → продакшн PyPI.

*С `--add`* (append-режим — вызывается изнутри WSL автоматически, либо вручную на другой ОС/машине для дозаливки):
- **Не трогает версию/changelog.**
- **Не создаёт новый релиз** (`gh release upload` вместо `gh release create`).
- Собирает артефакты **только для текущей платформы** (Linux → appimage+snap+conda; macOS в будущем → .app).
- Прикрепляет к уже существующему `v{version}`.

### 2.3. `dasmixer.spec` — платформенная условность

Общий блок + платформенные ветки:

```python
# Общие datas (cross-platform):
datas = [
    # assets, jinja2 templates, peptacular data, flet_desktop/app/flet,
    # choreographer/resources
]

# Windows-специфичные datas/binaries:
if sys.platform == "win32":
    datas += [
        (SITE / "webview" / "lib", ...),
        (SITE / "clr_loader" / "ffi" / "dlls" / "amd64", ...),
    ]
    hiddenimports += ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr", "pythonnet"]
    excludes += ["webview.platforms.gtk", "webview.platforms.cocoa", "gi"]

# Linux-специфичные:
elif sys.platform == "linux":
    datas += [
        ("/usr/lib/x86_64-linux-gnu/girepository-1.0", "gi_typelibs"),  # GI typelibs
    ]
    hiddenimports += [
        "webview.platforms.gtk",
        "gi", "gi.repository.Gtk", "gi.repository.WebKit2",
    ]
    excludes += ["webview.platforms.cocoa", "webview.platforms.winforms", "webview.platforms.edgechromium", "clr", "pythonnet"]

# macOS-задел (untested):
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa", "gi", "objc"]
    excludes += ["webview.platforms.gtk", "webview.platforms.winforms", "clr", "pythonnet"]
    # + BUNDLE() вместо COLLECT() для .app
    # + .icns вместо .ico
```

### 2.4. Conda-сборка на основе PyPI

**Принцип:** рецепт `packaging/conda/meta.yaml` описывает conda-пакет, чей build-скрипт делает `pip install` локально собранных `.whl`-файлов, которые уже лежат в `*/dist/`. Никаких зависимостей через conda solver (кроме conda-forge пакетов, реально присутствующих: flet, pandas, numpy, plotly, python и др. — они будут в `requirements: run` для корректного solver-окружения, но ряд протеомных зависимостей, **отсутствующих в conda-forge**, будут поставлены через pip внутри build-скрипта).

**Отсутствуют в conda-forge** (проверено `conda search`):
- `npysearch` / `npysearch-win`
- `peptacular`
- `mztabwriter`
- `uniprot-meta-tool`
- `html-for-docx`
- `smart-round`

Эти 6 пакетов будут установлены через `pip install` в `build.sh`/`bld.bat` и указаны как `pip:` зависимости в `meta.yaml` (conda-build не может резолвить их через conda channels, но разрешит через pip subdependency).

**Платформенность:** пакет не `noarch` — зависит от `sys_platform`-селекторов (разные pywebview/npysearch для Windows vs Linux). `meta.yaml` использует селекторы `# [win]` и `# [linux]`, `build.sh`/`bld.bat` различают, какой именно набор wheel'ов включать.

**PEP 440 dev-суффиксы vs conda-версии:** Conda не парсит `.dev1` корректно (сравнение версий ломается). Возможные решения:
- Для пре-релизов: нормализовать версию в `meta.yaml` — `0.7.1a4.dev1` → `0.7.1a4dev1` (без точки перед `dev`).
- Для финальных релизов (без `.dev`): использовать версию как есть.
- Публиковать пре-релизы с `--label dev`, финальные — в `main`.

Нужно реализовать конвертер версий в `build.py` или `set_version.py`.

---

## 3. Ключевые подводные камни и риски

### 3.1. PyInstaller на Linux: GI typelibs

PyInstaller **не подхватывает GObject Introspection typelibs** автоматически (через import tracing их не отследить — они загружаются runtime через `gi.repository` introspection). Нужны:

```python
datas += [
    ("/usr/lib/x86_64-linux-gnu/girepository-1.0", "gi_typelibs"),
]
hiddenimports += [
    "gi",
    "gi.repository.Gtk",        # или Gtk-3.0, зависит от версии pygobject
    "gi.repository.WebKit2",     # или WebKit-4.1/6.0 — зависит от версии webkit2gtk
    "gi.repository.GLib",
    "gi.repository.GObject",
    "gi.repository.Gio",
    "gi.repository.Gdk",
    "gi.repository.GdkPixbuf",
]
```

**Проверять строго нельзя без реальной машины.** На этой машине (Ubuntu 24.04) GTK runtime (libgtk-3-0, libwebkit2gtk-4.1-0) установлены, но PyInstaller-бандл может падать на чистой системе без dev-пакетов. Это проверяется в spike (см. раздел 5).

### 3.2. glibc/ABI-совместимость AppImage

Правило экосистемы AppImage: **сборка на самом старом поддерживаемом дистрибутиве** (иначе бинарники, слинкованные с новым glibc, не запустятся на старых системах). При сборке на Ubuntu 22.04 — совместимость с Ubuntu 22.04+, Debian 12+, Fedora 35+. При сборке на Ubuntu 24.04 — падение на 22.04 и ниже.

**Решение:** WSL-дистрибутив для сборки явно задан как **Ubuntu-22.04** (параметризуется `--wsl-dist`, по умолчанию `Ubuntu-22.04`, а не голый `Ubuntu`). Bootstrap-скрипт `wsl_bootstrap.sh` настраивает окружение внутри этого дистрибутива.

### 3.3. GTK/WebKit: конфликт версий между PyInstaller-бандлом и Snap

PyInstaller onedir-бандл на Linux может включать копии системных GTK/WebKit .so. Snap, в свою очередь, через `extension: gnome` подключает свои GTK/WebKit библиотеки как content-snap (`gnome-42-2204` для core22, свежий gnome для core24 с Ubuntu 24.04).

Если в PyInstaller-бандле уже есть свои GTK/WebKit .so, **возможен конфликт версий** ("double load") при запуске внутри snap: приложение загрузит бандловые .so, snap подменит окружение своими, рантайм-поведение непредсказуемо (сегфолты, падения при работе с GUI).

**Рассматриваемые варианты (выбор после spike):**

| Вариант | AppImage | Snap | Сложность |
|---|---|---|---|
| A. Тянуть GTK/WebKit в PyInstaller-бандл везде | Работает (linuxdeploy-plugin-gtk) | **Риск конфликта с gnome extension** | Средняя |
| B. Исключать GTK/WebKit из бандла для snap, тянуть для AppImage | Работает | Работает (полагается на gnome extension) | Высокая (разные профили сборки) |
| C. Исключать везде, snap — полагается на gnome, AppImage — тянет через linuxdeploy | Работает | Работает | Высокая |

**Выбор отложен до результатов spike** (задача 4 в плане).

### 3.4. Headless Chrome (kaleido/choreographer) внутри strict snap

`_ensure_chrome()` в `main.py:103` качает Chrome в `{app_dir}/chrome` при первом запуске и ставит `BROWSER_PATH`. Внутри strict-песочницы snap нужны:

- `network` plug (скачивание Chrome).
- `browser-support` plug (для Chrome runtime — проверка: может ли Chrome запускаться как headless внутри snap без `--no-sandbox`? Типичная проблема snap'ов с GUI — необходимость проброса `--no-sandbox` при запуске headless Chrome, но kaleido управляет этим самостоятельно, поэтому нужен реальный тест в snap-окружении после сборки.)

**Проверяется в ручном spike** (задача 3 в плане).

### 3.5. `gh auth` в WSL — отдельная сессия

Windows-хост аутентифицирован в `gh` через GitHub CLI (или GITHUB_TOKEN env). WSL-окружение — это отдельный пользовательский профиль, `gh auth status` может быть `not logged in`. Нужно либо:

- Прокидывать `GH_TOKEN`/`GITHUB_TOKEN` из Windows-окружения в WSL через `wsl.exe -u root export GH_TOKEN=...`.
- Настроить `gh auth login` внутри WSL при bootstrap — интерактивный шаг невозможен в автоматическом режиме, поэтому env-переменная предпочтительнее.

`build.py release` должен читать `GH_TOKEN` (или аналогичный env) и прокидывать его в `wsl.exe` invocation.

### 3.6. Единый git-снимок между Windows и WSL

Артефакты одного релиза (`vX.Y.Z`) должны строиться из **одного и того же коммита**. WSL монтирует Windows-файловую систему через `/mnt/c/` — при `wsl.exe ... bash -lc "cd /mnt/c/Users/.../dasmixer && poetry run python build.py release ... --add"` используется **тот же рабочий каталог**, что и на Windows-хосте. Это корректно.

**Нюанс:** Poetry в WSL хранит venv вне `/mnt/c/` (по умолчанию `~/.cache/pypoetry/virtualenvs/`), что правильно — venv из Windows несовместим бинарно с Linux-ядром.

### 3.7. `appimagetool`/`linuxdeploy` без FUSE в WSL

WSL по умолчанию не включает FUSE. `appimagetool` традиционно требует FUSE для монтирования squashfs. Обход: переменная окружения `APPIMAGE_EXTRACT_AND_RUN=1` — позволяет `appimagetool` работать без FUSE (извлекает и запускает из временной директории). Нужно выставлять в `wsl_bootstrap.sh` или `build.py linux` при вызове из WSL.

### 3.8. macOS `.app` — непроверяемый задел

Без реальной машины:
- `BUNDLE()` в PyInstaller spec (замена `COLLECT()` для .app).
- Иконка `.icns` вместо `.ico` (нужно сгенерировать из имеющегося `.png`).
- `pyobjc-framework-Cocoa`, `pyobjc-framework-WebKit` в `dasmixer-gui/pyproject.toml` с маркером `sys_platform == 'darwin'`.
- Codesigning/notarization не входят в скоуп (требуют Apple Developer ID).
- `webview.platforms.cocoa` и `objc` сейчас **безусловно исключены** в Excludes — нужно сделать условными.

Все правки помечаются в коде комментарием `# UNTESTED: macOS build — not verified without Apple hardware`.

---

## 4. WSL bootstrap

`build_tools/wsl_bootstrap.sh` — запускается внутри целевого WSL-дистрибутива (`wsl.exe -d Ubuntu-22.04 bash build_tools/wsl_bootstrap.sh`). Устанавливает:

```bash
# Системные зависимости
sudo apt-get update && sudo apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    libgtk-3-dev libwebkit2gtk-4.1-dev \
    libfuse2 squashfs-tools \
    pipx

# Poetry через pipx
pipx install poetry
pipx ensurepath

# AppImage toolchain
wget -c "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage" \
    -O /usr/local/bin/linuxdeploy && chmod +x /usr/local/bin/linuxdeploy
wget -c "https://github.com/linuxdeploy/linuxdeploy-plugin-gtk/releases/download/continuous/linuxdeploy-plugin-gtk-x86_64.AppImage" \
    -O /usr/local/bin/linuxdeploy-plugin-gtk && chmod +x /usr/local/bin/linuxdeploy-plugin-gtk

# Snapcraft (через snap, требует systemd в WSL — возможна альтернатива через snapcraft в Docker)
# Если snapd не работает в WSL → использование Docker-образа snapcore/snapcraft

# Poetry install проекта
cd /mnt/c/Users/.../dasmixer  # путь к репозиторию (передаётся параметром)
poetry install -E all

# APPIMAGE_EXTRACT_AND_RUN для без-FUSE режима (в ~/.bashrc или export при сборке)
echo 'export APPIMAGE_EXTRACT_AND_RUN=1' >> ~/.bashrc
```

**Snapcraft в WSL: особый случай.** `snapd` и `snapcraft` исторически зависят от systemd, которого нет в WSL1 и ограниченно доступен в WSL2. Альтернативы:
- Сборка snap через Docker (`snapcore/snapcraft` образ) — надёжнее, но требует Docker в WSL.
- Использование `snapcraft --destructive-mode` (без LXD/Multipass, прямо на хосте) — подходит для WSL, но повышает риск загрязнения окружения.
- Реальное решение уточняется в ходе spike.

---

## 5. План работ

### Фаза 1: Ручной spike (без правки `build.py`) — текущая Linux-машина или WSL

1. Создать Linux-ветку `dasmixer.spec` (минимальный вариант: platform-conditional datas + hiddenimports + excludes, см. раздел 2.3).
2. `poetry install -E all` в проекте.
3. `pyinstaller dasmixer.spec --clean -y` — проверить, что `dist/dasmixer/dasmixer` запускается вне venv (GUI стартует, нет ImportError/gi-introspection-паники).
4. Установить linuxdeploy + linuxdeploy-plugin-gtk (см. bootstrap).
5. Собрать AppImage: `linuxdeploy --appdir AppDir --plugin gtk ...` → проверить переносимость (запустить в Docker-контейнере Ubuntu 22.04 или чистом окружении без dev-пакетов).
6. Установить snapcraft, собрать snap (strict, core24, gnome extension):
   1. Проверить запуск GUI внутри snap.
   2. Проверить file dialogs.
   3. Проверить генерацию Plotly-отчётов (headless Chrome/kaleido) — критично для strict confinement.

### Фаза 2: Фиксация решений по итогам spike

- Выбрать профиль сборки для AppImage/Snap (единый или раздельные).
- Подтвердить/скорректировать список hiddenimports/datas для Linux.
- Подтвердить/скорректировать стратегию headless Chrome внутри strict snap.
- Зафиксировать версию Ubuntu для WSL (22.04), подтвердить glibc-совместимость AppImage.

### Фаза 3: Реализация (код)

1. **`dasmixer.spec`** — platform-conditional datas/binaries/hiddenimports/excludes (win/linux/darwin-untested).
2. **`packaging/appimage/`** — `dasmixer.desktop`, `AppRun`, `.appdata.xml`.
3. **`packaging/snap/snapcraft.yaml`** — strict confinement, plugs: `network`, `browser-support`, `opengl`, `home`, `desktop`, `desktop-legacy`.
4. **`packaging/conda/meta.yaml`** + `build.sh` + `bld.bat` — pip install локальных .whl через `requirements: host: pip`, версия с PEP440-нормализацией.
5. **`build_tools/set_version.py`** — добавить синхронизацию `snapcraft.yaml` (`version:`), `conda/meta.yaml` (`{% set version = "..." %}`).
6. **`build_tools/wsl_bootstrap.sh`** — инициализация WSL-окружения (apt, poetry, linuxdeploy/appimagetool).
7. **`build.py` команды:**
   - `linux` — `--appimage`/`--snap` флаги.
   - `conda` — `--label dev|main`.
   - `release` — оркестрация WSL-вызова + флаг `--add`.
   - Параметр `--wsl-dist` (default `Ubuntu-22.04`).
8. **macOS-задел (untested):**
   - `BUNDLE()` в spec для `darwin`.
   - `.icns` иконка.
   - `pyobjc` маркеры в `dasmixer-gui/pyproject.toml`.
   - Комментарии `# UNTESTED` во всех соответствующих местах.
9. **AGENTS.md / docs** — описание новой команды сборки, предупреждения о непроверенных путях.

---

## 6. Зафиксированные решения (по итогам обсуждения с разработчиком)

| Параметр | Решение |
|---|---|
| Snap confinement | **Strict** (полная автоматизация, без ручного review Canonical) |
| Conda канал | **Личный канал на anaconda.org** (`anaconda upload`) — не conda-forge |
| Conda зависимости | `pip install` внутри build-скрипта для PyPI-only пакетов, conda-forge для остальных |
| Среда сборки Linux | **Ubuntu-22.04** через WSL (параметризуется `--wsl-dist`) |
| Docker для сборки | **Не используется** — WSL напрямую, без дополнительного контейнера |
| macOS охват | **Спроектировать, пометить untested** — без реальной проверки |
| GTK/WebKit в PyInstaller | **Решить после spike** (единый или раздельный профиль для AppImage/Snap) |
| Порядок работ | **Сначала ручной spike** (Фаза 1), затем код |

---

## 7. Открытые вопросы (требуют уточнения в ходе реализации)

1. Точный список GI hiddenimports после spike (версия webkit2gtk влияет на имена: `WebKit2` vs `WebKit-4.1` vs `WebKit-6.0`).
2. Конвертер PEP440→conda-версии: какой именно формат использовать для pre-release суффиксов (точка перед dev — допустима ли в конкретной версии conda-build?).
3. Формат `meta.yaml` для `pip:` зависимостей — корректный синтаксис с учётом platform-селекторов `# [win]`/`# [linux]`.
4. Работоспособность `snapcraft` в WSL без systemd — понадобится ли `--destructive-mode` или Docker fallback.
5. `.desktop` MimeType-ассоциация `.dasmix` — точная процедура регистрации custom MIME в Linux (shared-mime-info XML vs просто `.desktop`). Включать ли в автоматизацию.
