"""Переиспользуемый выбор цвета (preview + SlidePicker/ColorPicker + text field).

Компонент на базе ``flet_color_pickers``, интегрированный в стили DASMixer.

Форматы:
- Внешний API оперирует форматом ``#RRGGBB`` (как хранится в БД DASMixer).
- Внутри (для ``flet_color_pickers``) используется ``#AARRGGBB`` — alpha
  всегда ``FF``.

Режимы:
- ``compact=False`` (full) — preview + ``SlidePicker`` + text field в одну
  строку. Используется в диалогах Group/Tool.
- ``compact=True`` — компактная строка: кликабельный preview + text field
  (+ опциональная кнопка удаления). Пикер (``ColorPicker`` с палитрой)
  открывается в ``AlertDialog`` по клику на preview. Используется на
  странице Settings.
"""

import re

import flet as ft
from flet_color_pickers import ColorPicker, SlidePicker

from dasmixer.utils import logger

__all__ = [
    "HEX_COLOR_RE",
    "ColorPickerField",
    "is_valid_hex_color",
    "normalize_hex_color",
]

# '#RRGGBB'
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_RGB6_RE = re.compile(r"^[0-9a-fA-F]{6}$")


def normalize_hex_color(value: str | None) -> str:
    """
    Привести любое значение к '#RRGGBB' (uppercase).

    Понимает: '#RRGGBB', 'RRGGBB', '#AARRGGBB', 'AARRGGBB',
    '' / None -> '#888888' (серый по умолчанию).
    """
    if not value:
        return "#888888"
    h = value.strip().lstrip("#")
    if len(h) == 8:  # AARRGGBB -> RRGGBB
        h = h[-6:]
    if _RGB6_RE.match(h):
        return f"#{h.upper()}"
    return "#888888"


def is_valid_hex_color(value: str | None) -> bool:
    """True, если строка — валидный цвет '#RRGGBB' (или 'RRGGBB')."""
    if not value:
        return False
    return bool(_RGB6_RE.match(value.strip().lstrip("#")))


def _to_argb(rrggbb: str) -> str:
    """'#RRGGBB' -> '#FFRRGGBB' (нижний регистр — как у flet_color_pickers)."""
    return f"#ff{rrggbb[1:].lower()}"


def _from_argb(value: str) -> str:
    """'#AARRGGBB' или '#RRGGBB' -> '#RRGGBB' (uppercase)."""
    h = value.strip().lstrip("#")
    if len(h) >= 6:
        h = h[-6:]
    return f"#{h.upper()}"


def _try_update(control: ft.Control | None) -> None:
    """Безопасный update — игнорирует ошибки (контрол может быть не на странице)."""
    if control is None:
        return
    try:
        control.update()
    except Exception as ex:  # noqa: BLE001
        # Контрол может быть не смонтирован (page отсутствует) — это нормально.
        logger.debug("ColorPickerField update skipped: %s", ex)


class ColorPickerField(ft.Container):
    """
    Поле выбора цвета.

    Args:
        value: Начальное значение '#RRGGBB'.
        label: Подпись текстового поля.
        compact: Компактный режим для Settings (пикер в диалоге).
        show_delete: Показывать кнопку удаления (compact).
        on_delete: Callback без аргументов (клик по корзине).
        on_change: Callback с одним аргументом '#RRGGBB' при изменении.
        preview_size: Размер квадрата-превью в px.
        slider_width: Ширина слайдеров пикера в px.

    Внешний интерфейс:
        - ``.value`` — '#RRGGBB' (получить/установить)
        - ``.is_valid`` — корректный ли цвет в поле
        - ``.set_error(message|None)`` — показать/скрыть ошибку
    """

    def __init__(
        self,
        value: str = "#888888",
        *,
        label: str = "Color (hex)",
        compact: bool = False,
        show_delete: bool = False,
        on_delete=None,
        on_change=None,
        preview_size: int = 50,
        slider_width: int = 180,
    ):
        super().__init__()
        self._compact = compact
        self._show_delete = show_delete
        self._on_delete_cb = on_delete
        self._on_change_cb = on_change
        self._preview_size = preview_size
        self._slider_width = slider_width
        self._picker: SlidePicker | None = None
        self._dialog_picker: ColorPicker | None = None
        self._syncing = False

        normalized = normalize_hex_color(value)
        self._value: str = normalized

        # --- preview ---
        self._preview = ft.Container(
            width=preview_size,
            height=preview_size,
            border_radius=5,
            bgcolor=normalized,
            border=ft.border.all(1, ft.Colors.GREY_400),
        )
        if compact:
            self._preview.on_click = self._on_preview_click
            self._preview.tooltip = "Pick color"

        # --- text field ---
        self._field = ft.TextField(
            label=label if label else None,
            value=normalized[1:],  # без '#'
            max_length=6,
            width=100,
            height=60,
            hint_text="e.g., FF0000",
            on_change=self._on_text_change,
            on_blur=self._on_text_blur,
        )

        # --- компоновка ---
        row_controls: list[ft.Control] = [self._preview]

        if not compact:
            self._picker = SlidePicker(
                color=_to_argb(normalized),
                show_indicator=False,
                enable_alpha=False,
                display_thumb_color=True,
                on_color_change=self._on_picker_change,
                slider_size=ft.Size(width=slider_width, height=20),
            )
            row_controls.append(self._picker)

        row_controls.append(self._field)

        if show_delete:
            row_controls.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Remove color",
                    on_click=lambda _e: (self._on_delete_cb() if self._on_delete_cb else None),
                )
            )

        self.content = ft.Row(
            row_controls,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.padding = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def value(self) -> str:
        """Текущий цвет в формате '#RRGGBB'."""
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        """Программно установить цвет (без вызова on_change)."""
        nv = normalize_hex_color(new_value)
        self._value = nv
        self._field.value = nv[1:]
        self._preview.bgcolor = nv
        if self._picker is not None:
            self._syncing = True
            try:
                self._picker.color = _to_argb(nv)
            finally:
                self._syncing = False
        self._refresh()

    @property
    def is_valid(self) -> bool:
        """Валиден ли введённый в текстовое поле цвет."""
        return is_valid_hex_color(self._field.value)

    def set_error(self, message: str | None = None) -> None:
        """Показать ошибку под полем (или убрать, если message is None)."""
        if message:
            self._field.error_text = message
            self._field.border_color = ft.Colors.RED
        else:
            self._field.error_text = None
            self._field.border_color = None
        _try_update(self._field)

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------

    def _on_picker_change(self, e: ft.ControlEvent) -> None:
        """Изменение цвета в SlidePicker (full-режим)."""
        if self._syncing:
            return
        rgb = _from_argb(e.data or "")
        self._apply_color(rgb, notify=True)

    def _on_text_change(self, e: ft.ControlEvent) -> None:
        """Пользователь печатает hex-код вручную."""
        raw = (e.control.value or "").strip()
        if is_valid_hex_color(raw):
            rgb = f"#{raw.upper()}"
            self._value = rgb
            self._preview.bgcolor = rgb
            e.control.border_color = None
            if self._picker is not None:
                self._syncing = True
                try:
                    self._picker.color = _to_argb(rgb)
                finally:
                    self._syncing = False
            self._notify_change()
        else:
            # Пока пользователь не допечатал — серый, без сброса значения
            self._preview.bgcolor = "#888888"
        _try_update(self._preview)
        _try_update(e.control)

    def _on_text_blur(self, e: ft.ControlEvent) -> None:
        """Валидация на потерю фокуса."""
        raw = (e.control.value or "").strip()
        if not is_valid_hex_color(raw):
            e.control.border_color = ft.Colors.RED
            _try_update(e.control)

    # --- compact: диалог с ColorPicker ---

    def _on_preview_click(self, e: ft.ControlEvent) -> None:
        """Открыть ColorPicker в AlertDialog (только compact-режим)."""
        page = self._safe_page()
        if page is None:
            return
        self._dialog_picker = ColorPicker(
            color=_to_argb(self._value),
            enable_alpha=False,
            hex_input_bar=True,
            color_picker_width=self._slider_width + 40,
            on_color_change=self._on_dialog_picker_change,
        )
        dlg = ft.AlertDialog(
            title=ft.Text("Pick color"),
            content=ft.Container(
                content=self._dialog_picker,
                padding=10,
            ),
            actions=[
                ft.TextButton(
                    "Done",
                    on_click=lambda _ev: self._close_picker_dialog(dlg),
                ),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _on_dialog_picker_change(self, e: ft.ControlEvent) -> None:
        """Изменение цвета в диалоговом ColorPicker (compact)."""
        rgb = _from_argb(e.data or "")
        self._apply_color(rgb, notify=True)
        if self._dialog_picker is not None:
            # возвращаем синхронизацию слайдера, если hex вводился вручную
            self._syncing = True
            try:
                self._dialog_picker.color = _to_argb(rgb)
            finally:
                self._syncing = False

    def _close_picker_dialog(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        page = self._safe_page()
        if page is not None:
            page.update()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_color(self, rgb: str, *, notify: bool) -> None:
        """Применить цвет '#RRGGBB' ко всем элементам."""
        self._value = rgb
        self._field.value = rgb[1:]
        self._preview.bgcolor = rgb
        self._field.border_color = None
        self._refresh()
        if notify:
            self._notify_change()

    def _notify_change(self) -> None:
        if self._on_change_cb is not None:
            self._on_change_cb(self._value)

    def _refresh(self) -> None:
        _try_update(self._preview)
        _try_update(self._field)
        _try_update(self._picker)
        if self._dialog_picker is not None:
            _try_update(self._dialog_picker)

    def _safe_page(self) -> ft.Page | None:
        """Вернуть page, если контрол уже добавлен в дерево, иначе None."""
        try:
            return self.page
        except RuntimeError:
            return None
