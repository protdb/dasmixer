# Offline-исследование: сетевые обращения зависимостей DASMixer в рантайме

**Тип документа:** исследование (не постановка задачи)
**Дата:** 2026-08-18
**Область:** анализ прямых и транзитивных зависимостей на предмет неожиданных сетевых обращений за пределами первого запуска

---

## 1. Задача и метод

Требовалось понять, какие внешние библиотеки могут обращаться в сеть **в рантайме** — то есть
после установки и первой инициализации. Известные ранее источники: Flet (загрузка Flutter),
kaleido (Chrome), uniprot_meta_tool (UniProt при обогащении), pyteomics (Unimod, разобран отдельно).

Метод: проверены все прямые зависимости (по `pyproject.toml` четырёх пакетов) и 83
транзитивных пакета в poetry venv
(`/home/kirill/.cache/pypoetry/virtualenvs/dasmixer-workspace-djOIbfrl-py3.14`), плюс исходники
DASMixer. Поиск вёлся по паттернам `urlopen`, `urlretrieve`, `requests.get/post`,
`requests.Session`, `httpx`, `aiohttp`, `download`, `fetch`, `wget`, `telemetry`, `analytics`,
`update_check`, `check_for_update`, `version_check`, `phone home`, `sentry`, `mixpanel`,
`posthog`, `google_analytics`, `amplitude`.

Проверенные версии: flet 0.80.5, kaleido/choreographer 1.3.0, plotly 6.9.0,
scikit-learn 1.9.0, peptacular 2.5.1, pyteomics 4.7.5, uniprot_meta_tool 0.2.1,
pywebview 6.2.1.

---

## 2. Сводная картина

### 2.1. Реальные источники сети в рантайме

| Библиотека | Что качает | Когда | Оценка |
|---|---|---|---|
| uniprot_meta_tool | `https://rest.uniprot.org/uniprotkb/{id}` | Только «Enrich from UniProt». **N запросов** — по одному на белок, последовательно, без троттлинга. Кэш в `/tmp/uniprot_meta/` без TTL | HIGH |
| pyteomics | `unimod.xml`, `unimod_tables.xml`, XSD-схемы, PROXI (USI) | Только по запросу (резолв PTM `[Deamidated]` и т.п.) | LOW (lazy) |
| kaleido/choreographer | Chrome for Testing (~200 МБ) | Только явный `get_chrome_sync()` — не автоматически | см. §5 |
| peptacular | 6 OBO-файлов | Только явный `reload_from_online()`, никогда не вызывается автоматически | LOW |
| scikit-learn | датасеты `fetch_*` (15 функций) | Только явный вызов | LOW |
| flet (OAuth) | GitHub и пр. | Только если настроен OAuth (DASMixer не использует) | LOW |

### 2.2. Что НЕ качает (проверено, можно закрыть)

- **plotly** — телеметрии/аналитики **нет**, сети нет. `plotly.min.js` (4.8 МБ) бандлится;
  CDN-ссылки (`cdn.plot.ly`, MathJax) только встраиваются в HTML-вывод — Python их не тянет
  (подтянет браузер, но не приложение). Единственный сетевой код — устаревший Orca-движок
  (`requests.post` на `localhost`) и явный `plotly_get_chrome()`.
- **flet** — с `flet[all]` Flutter-клиент **бандлится**
  (`flet_desktop/app/flet-linux-amd64.tar.gz`, ~20 МБ); при первом запуске лишь распаковывается
  локально в `~/.flet/client/{dist}-{version}/`. Сетевых обращений в `flet`/`flet_desktop`/`flet_cli`
  в рантайме нет.
- **pywebview** — обёртка системного webview, сети нет.
- **pythonnet / npysearch / mztabwriter / smart-round / docxtpl / jinja2 / openpyxl / xlrd /
  aiofiles / aiocsv / parse / tabulate / pydantic / typer / certifi** — сети нет.
- **Телеметрии, автоапдейт-чекеров, crash-репортеров** — ноль ни в DASMixer, ни в зависимостях.

---

## 3. uniprot_meta_tool — детально

Единственный HTTP-вызов во всей библиотеке — `requests.get()` в
`uniprot_meta_tool/data_parser.py:109` (конструктор `UniprotData.__init__`).

Логика конструктора:

- передан `raw_meta` → сеть **не** используется;
- кэш-файл `{meta_cache_dir}/{id}.meta.json` существует → читается с диска, сети нет;
- кэша нет → HTTP GET `https://rest.uniprot.org/uniprotkb/{id}` + запись кэша.

Кэш по умолчанию в `/tmp/uniprot_meta/`, **без TTL** (живёт бессрочно, пока файл не удалён).
`use_cache` влияет только на чтение; если файла нет — запрос происходит всегда.

Точки срабатывания в DASMixer:

- `dasmixer-core/src/dasmixer/api/calculations/proteins/enrich.py` — `enrich_proteins()` вызывает
  `UniprotData(protein_id)` для каждого идентифицированного белка (клик «Enrich proteins from
  UniProt»). Для 2000 белков это 2000 последовательных HTTP-запросов.
- `sempai/protein.py:186-189` — потенциальный вызов при `sequence is None and is_uniprot=True`,
  но DASMixer всегда передаёт `sequence`, поэтому ветка мёртвая.
- `fasta.py:enrich_with_uniprot()` — заглушка `"not yet implemented"`, безопасна.

Отображение статистики белков (`get_protein_statistics`) сети **не** делает: `uniprot_data`
читается из БД (pickle BLOB), `get_pathways_from_uniprot()` и т.п. работают с уже
десериализованным объектом.

---

## 4. plotly / scikit-learn — детально

### plotly

- Телеметрии и телефона домой нет (нулевые совпадения по `telemetry`/`analytics`/`sentry` и т.п.).
- `pio.to_html(fig, include_plotlyjs=True)` — бандлит локальный `plotly.min.js`.
- `pio.to_image` — через kaleido (локальный Chrome), сети нет.
- `pio.show` — локальный HTML или локальный HTTP-сервер на `127.0.0.1`.
- CDN-URL (`plotlyServerURL`, MathJax `cdn`) — только строки для встраивания в HTML.
- Исключения: `plotly_get_chrome()` (скачивает Chrome, только по явному вызову с подтверждением)
  и Orca (`requests.post` на `localhost`).

### scikit-learn

- Телеметрии нет.
- `load_*` (iris, digits, wine и т.д.) — данные бандлятся через `importlib.resources`.
- `fetch_*` (openml, california_housing, lfw и т.д.) — качают через `urllib.request.urlretrieve`,
  но **только по явному вызову**; при импорте `sklearn.datasets` ничего не скачивается.
  Кэш в `~/scikit_learn_data/` с проверкой SHA256.

---

## 5. kaleido / choreographer и Chrome — аномалия

- Chrome for Testing (~200 МБ) скачивается только явным `get_chrome_sync()` (URL
  `googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json`).
- `fig.to_image()` при отсутствии Chrome **не скачивает** его, а бросает `ChromeNotFoundError`
  с инструкцией.
- Kaleido-генератор страниц имеет CDN-фолбэки (`cdn.plot.ly/plotly-2.35.2.js`, MathJax), но они
  используются только если plotly не установлен. У DASMixer plotly установлен → используется
  локальный `plotly.min.js`.
- Chrome запускается с флагами, отключающими `component-update`, `sync`, `first-run`,
  `metrics`, `breakpad`, `default-browser-check`. Остаются фоновые активности самого бинарника
  (DNS, OCSP, safe browsing) — вне контроля Python.

**Аномалия в DASMixer (обратное направление — сеть НЕ вызывается, хотя должна):**

`_ensure_chrome()` (`dasmixer-gui/src/dasmixer/gui/main.py:103`) вызывает
`kaleido.get_chrome_sync()` и скачивает Chrome в `{app_dir}/chrome/`, но вызывается **только**
в блоке `if __name__ == "__main__"` (строка 150). Через нормальные точки входа
(`dasmixer` → `dasmixer.gui.main:app` и `python -m dasmixer` → `dasmixer/__main__.py`) функция
не выполняется.

В PyInstaller-сборке (`dasmixer.spec`) Chrome не бандлится — бандлится только
`choreographer/resources/last_known_good_chrome.json`. Следствие: при первом экспорте PNG
(`base.py:432`, `base_plot_view.py:362`, `peptides_tab.py:1022`) kaleido не найдёт Chrome и упадёт
с `ChromeNotFoundError`.

---

## 6. pyteomics / peptacular — детально

### pyteomics

Сетевой код: `mass.Unimod` (`mass/mass.py:1134`, `urlopen` на `unimod.org/xml/unimod.xml`),
`mass/unimod.py` (`unimod_tables.xml`), `xml.py` (XSD-схемы), `usi.py` (PROXI). Ни один из них
не срабатывает при импорте — только по запросу. `nist_mass` — жёстко зашитый словарь
(`_nist_mass`), не скачивается. Отдельно разобран случай резолва PTM (Unimod) — см.
`docs/project/spec/features/unimod.md`.

### peptacular

На импорте БД модификаций грузятся из бандленных файлов `peptacular/data/*.obo`
(локально). Сетевой код один — `EntryDb.reload_from_online()` в `mods/mod_db_setup.py:1109`,
скачивающий OBO во временный файл; вызывается **только явно** (как и
`reload_all_databases_from_online()`). `requests` подгружается лениво и не является объявленной
зависимостью — при отсутствии `requests` метод бросает `ImportError`.

Бандленные данные (~100 МБ): `unimod.obo`, `psi-mod.obo`, `xlmod.obo`, `monosaccharides_updated.obo`,
`gno.obo` (не грузится), `resid.xml` (не грузится), `chem.txt`.

---

## 7. DASMixer (собственный код)

Поиск по исходникам DASMixer: сетевые паттерны найдены только в `build.py` (CI/dev-скрипт,
PyPI/TestPyPI + `urlopen` проверки доступности — не рантайм). `webbrowser.open` — только локальные
HTML-отчёты. Телеметрии, автоапдейта, raw-сокетов, `curl`/`wget` через subprocess — нет.

Единственные сетевые обращения, которые может вызвать код DASMixer в рантайме:

1. uniprot_meta_tool → `rest.uniprot.org` (обогащение белков);
2. kaleido/choreographer → CDN Chrome (только при явном `get_chrome_sync`);
3. сам Chrome-бинарник (фоновые DNS/OCSP/safe browsing);
4. pyteomics → PROXI/Unimod/XSD (по запросу).

---

## 8. Выводы

1. **uniprot_meta_tool** — главный и единственный «массовый» источник сети: N последовательных
   запросов при обогащении; кэш в `/tmp` без TTL (не переживает перезагрузку). Риск для
   оффлайн-сценария — высокий.
2. **kaleido/Chrome** — не качает Chrome автоматически в рантайме; более того, в текущем коде
   `_ensure_chrome()` фактически мёртв для нормального запуска. Требует решения: бандлить Chrome
   либо подключить `_ensure_chrome()` к старту.
3. **plotly, scikit-learn, peptacular, pywebview, pythonnet, flet (с `[all]`)** — оффлайн-безопасны,
   сетевой код либо отсутствует, либо требует явного вызова.
4. **Телеметрии и автоапдейта** нет нигде — ни в DASMixer, ни в зависимостях.
