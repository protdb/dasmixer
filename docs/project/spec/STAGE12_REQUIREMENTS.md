# Создание формы для отчета

Требуется дать возможность сделать на UI упрощенный вариант интерфейса для отчетов.

Логика и базовые отчеты тут: `dasmixer/api/reporting`

GUI отчетов тут: `dasmixer/gui/views/tabs/reports/reports_tab.py`

Сейчас там в качестве "Костыля" используется TextArea. Нужно вместо неё сделать возможность задать базовый класс формы, приеобразующийся к ft.Container, который открывается по кнопке Parameters

Концепция: создаём базовый клаcc ReportForm, который может принять на вход несколько простых виджетов и сделать на выходе сбор данных.
Причем мы не используем виджеты flet напрямую,  мы используем специальные обёртки с отдельным классом ReportParamBase,
от которого наследуем ряд классов:
- ToolSelector: Dropdown выбора инструмента
- EnumSelector: Выбор одного значения из списка
- BoolSelector: Checkbox
- FloatSelector: Ввод числа с плавающей запятой
- IntSelector: Ввод целого
- SubsetSelector: Выбор одной из групп сравнения
- MultiSubsetSelector: По чекбоксу на каждую группу
- StringSelector: Выбор одной строки

Пример с т.з. пользвоателя:
```python
class MyReportForm(ReportForm):
    tool = ToolSelector()
    stats_type = EnumSelector(values=["Mann-Whitney U", "T-Student"])
    control_subset = SubsetSelector()
    do_false_discovery_correction = BoolSelector(default=True)
```

Для простых BoolSelector, FloatSelector и т.д. доступны значения по умолчанию через параметр default.

Для выпадающих списков по умолчанию выбирается первый вариант из списка (переданного пользователем или сохраненного в системе.

У класса ReportForm должны быть определены два основных метода:
- get_container() - возвращает ft.Container со всеми контролами
- get_values() - возвращает значения

В BaseReport заменить get_parameter_defaults() на свойство parameters: ReportForm | None = None

Соответственно, в вызов `_generate_impl` передается как сейчас словарь, но он добывается из get_values(). Значения настроек нужно сохранять так же, как это происходит сейчас, в проекте.

Сам класс должен быть в `dasmixer.gui.components.report_form`