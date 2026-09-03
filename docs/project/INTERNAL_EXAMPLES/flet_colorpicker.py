import re
import flet as ft
from flet_color_pickers import SlidePicker, ColorPicker, PaletteType

check_rgb = re.compile(r"^([a-fA-F0-9]{6})$")

default_color="#ffff0000"

## NOTE: #AARRGGBB format used by flet, RRGGBB stored in DASMixer DB!!! (Alpha is always FF)

def main(page: ft.Page):
    page.title = "ColorPicker"
    page.padding = 20

    def on_color_change(e: ft.ControlEvent):
        print(e.data)
        color_preview.bgcolor=e.data
        color_field.value = e.data[3:]

    def on_text_change(e: ft.ControlEvent):
        print(e.control.value)
        text = e.control.value
        if len(text) == 6:
            if check_rgb.match(text) is not None:
                color = f'#ff{e.control.value}'
                picker.color = color
                color_preview.bgcolor = color
                picker.update()

    color_field = ft.TextField(
        label="Color (hex)",
        value=default_color[3:],
        on_change=on_text_change,
        max_length=6,
        width=100,
        height=60,
        hint_text="e.g., FF0000 for red",
    )
    color_preview = ft.Container(
        width=80, height=80, border_radius=5, bgcolor=default_color
    )



    picker = SlidePicker(
        color=default_color,
        show_indicator=False,
        enable_alpha=False,
        on_color_change=on_color_change,
        display_thumb_color=True,
        slider_size=ft.Size(width=200, height=20),
    )
    content = ft.Row([
        color_preview,
        picker,
        ft.Container(content=color_field, padding=ft.padding.symmetric(vertical=10)),

    ], height=80, vertical_alignment = ft.CrossAxisAlignment.CENTER)
    page.add(ft.SafeArea(content))
    page.update()


if __name__ == "__main__":
    ft.run(main)
