# Спецификация — Офлайн-база Unimod (устранение плавающей сетевой ошибки)

**Статус:** Схема согласована, реализация не начата
**Затронутые пакеты:** `dasmixer-core` (данные + резолвер), `dasmixer-gui`/`dasmixer-cli` (точки вызова), корневой `dasmixer.spec` (PyInstaller)

---

## 1. Проблема

`pyteomics` (в poetry-окружении установлена версия 4.7.5) при резолве именованных PTM в ProForma
**лениво скачивает** базу Unimod из интернета. При отсутствии сети возникает плавающая ошибка
доступа к базе (не воспроизводится при наличии интернета).

### 1.1. Механизм в pyteomics

- `pyteomics/proforma.py:378` → `UnimodResolver.load_database()` (строки 384-387):
  т.к. `psims` в окружении **не установлен** (`_has_psims=False`), вызывается
  `pyteomics.mass.Unimod()` — это **старый** класс `pyteomics/mass/mass.py:1063`,
  который выполняет `urlopen("http://www.unimod.org/xml/unimod.xml")` (строка 1134).
- Путь через `psims` (`obo_cache.resolve("http://www.unimod.org/obo/unimod.obo")`)
  не актуален — `psims` не входит в зависимости.

### 1.2. Точки срабатывания в DASMixer

- `dasmixer-core/src/dasmixer/utils/ppm.py:44` — `mass.calculate_mass(proforma=...)`
- `dasmixer-core/src/dasmixer/utils/seqfixer_utils.py:27` — `GenericModification(...).mass`
  (через `FixedPTM.__post_init__`)

Именованные PTM (`[Deamidated]`, `[Pyridylethyl]`, `[Amidated]` и т.п.) резолвятся через
`GenericResolver → UnimodResolver`; масс-шифты вида `[+15.99]` и plain-последовательности
Unimod **не** требуют.

---

## 2. Решение (без патчинга pyteomics)

`pyteomics.proforma.set_unimod_path(path)` (строки 1081-1102) — публичная функция,
подменяющая БД резолвера (`UnimodModification.resolver.database`) и полностью отключающая
скачивание.

> **Нюанс передачи пути:** `path` передаётся в `Unimod(source)`, где строка идёт в
> `urlopen()`. Поэтому для локального файла нужно передавать **открытый файловый объект**
> (`with open(..., "rb") as f: set_unimod_path(f)`) — тогда сработает `etree.parse(file)`.
> Альтернатива — `path.as_uri()` (строка вида `file:///...`).

---

## 3. Схема реализации

### 3.1. Файл БД (единый источник для wheel и PyInstaller)

```
dasmixer-core/src/dasmixer/utils/data/unimod.xml
```

- Скачивается один раз с `http://www.unimod.org/xml/unimod.xml` (~2.5 МБ).
- Размещается в `dasmixer.utils` (обычный пакет с `__init__.py`), чтобы:
  - попадал в wheel `dasmixer-core` и был доступен и GUI, и CLI;
  - служил источником для `datas` в `dasmixer.spec`.

### 3.2. Резолвер `dasmixer-core/src/dasmixer/utils/unimod.py`

`ensure_unimod_available()` — идемпотентна (флаг-гард). Поиск файла — «пояс с подтяжками»,
проверка кандидатов по порядку:

```python
candidates = []
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    candidates += [
        # = <bundle>/_internal/... — совпадает с dest в dasmixer.spec
        Path(sys._MEIPASS) / "dasmixer" / "utils" / "data" / "unimod.xml",
        # страховка на случай рассинхрона раскладки
        Path(sys._MEIPASS) / "utils" / "data" / "unimod.xml",
    ]
# dev (из исходников) / wheel (site-packages)
candidates.append(Path(__file__).resolve().parent / "data" / "unimod.xml")
```

Логика:

- Файл найден → `with path.open("rb") as f: pyteomics.proforma.set_unimod_path(f)`.
- Файл не найден / любая ошибка → `logger.warning(...)` и откат к штатному онлайн-поведению
  pyteomics (ничего не ломаем, сеть остаётся fallback'ом).

### 3.3. Точки вызова (лениво, только когда реально нужны PTM)

- `dasmixer-core/src/dasmixer/utils/ppm.py` — в начале `calculate_theor_mass()`.
- `dasmixer-core/src/dasmixer/utils/seqfixer_utils.py` — в `FixedPTM.__post_init__`.
- (опционально) прогрев при старте GUI в `dasmixer-gui/src/dasmixer/gui/main.py` перед
  `run_gui()` — убирает разовый hitch при первой обработке.

Покрытие: главный процесс + multiprocessing-воркеры (при `spawn` на Windows `_MEIPASS`
резолвится заново в каждом воркере). Оба вызова дешёвы после первого (проверка флага).

### 3.4. PyInstaller — захват файла

В корневой `dasmixer.spec`, в список `datas` (рядом с существующими core-шаблонами):

```python
(
    str(SPEC_DIR / "dasmixer-core" / "src" / "dasmixer" / "utils" / "data"),
    "dasmixer/utils/data",
),
```

**Ключевое требование:** dest `"dasmixer/utils/data"` обязан совпадать с первым
frozen-кандидатом резолвера. В onedir-сборке (`COLLECT`) файл попадает в
`dist/dasmixer/_internal/dasmixer/utils/data/unimod.xml`, а `sys._MEIPASS` указывает на
`_internal` — резолвер его найдёт.

### 3.5. Wheel (Poetry/PyPI)

- Проверить после сборки, что `unimod.xml` попал в `dasmixer_core-*.whl` по пути
  `dasmixer/utils/data/unimod.xml` (poetry-core обычно кладёт всё содержимое пакетной
  директории).
- Если файл не попал — явно добавить в `[tool.poetry]` (в `dasmixer-core/pyproject.toml`):

```toml
include = ["src/dasmixer/utils/data/**/*.xml"]
```

---

## 4. Проверка

1. `poetry build` в `dasmixer-core` → `unimod.xml` присутствует в wheel по пути
   `dasmixer/utils/data/unimod.xml`.
2. PyInstaller-сборка (`pyinstaller dasmixer.spec`) → файл присутствует в
   `dist/dasmixer/_internal/dasmixer/utils/data/`.
3. Офлайн-смоук (без сети):
   - `parse("PEP[Deamidated]TIDE")` — не падает;
   - `FixedPTM("Deamidated").mass` — не падает;
   - `dasmixer-cli calculate` на тестовых данных — отрабатывает.

---

## 5. Замечание вне задачи (обнаружено при исследовании)

В `dasmixer.spec` dest ассетов GUI — `"dasmixer/gui/assets"`, а
`dasmixer-gui/src/dasmixer/gui/utils.py:get_asset_path` в frozen-ветке ищет
`_MEIPASS/assets/...`. Похоже на рассинхрон (возможная незаметная поломка логотипа/иконки
во frozen-сборке). В рамках данной задачи не правится, но при желании выравнивается по тому
же принципу, что в п.3.4.

---

## 6. Открытые вопросы

1. Коммитить ли `unimod.xml` в репозиторий (рекомендуется — воспроизводимо, не зависит от
   сети при сборке) с опциональной командой обновления `build.py fetch-unimod`, или качать
   файл в CI на этапе сборки без коммита?
2. Нужна ли аналогичная офлайн-подпитка для PSI-MOD / XLMOD / GNO? Сейчас DASMixer использует
   только generic-имена и масс-шифты, поэтому префиксы `MOD:`/`XL:`/`GNO:` не встречаются —
   в объём задачи не входят.
