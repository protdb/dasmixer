"""Копирование PNG-изображений в clipboard (flet-first + native fallback).

Стратегия:
1. Сначала ``await ft.Clipboard().set_image(png_bytes)`` — работает на
   web/mobile. На desktop flet 0.81 выбрасывает
   ``FletUnsupportedPlatformException``.
2. При недоступности flet-пути — платформенный fallback:
   - Windows: pythonnet (System.Windows.Forms.Clipboard), форматы PNG + Bitmap;
   - Linux:   ``wl-copy`` (Wayland) или ``xclip`` (X11);
   - macOS:   ``osascript`` + временный PNG-файл.

Все блокирующие вызовы выполняются в executor'е, чтобы не блокировать UI.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile

import flet as ft

from dasmixer.utils import logger

# Регистрируемый Windows-формат PNG для вставки с прозрачностью.
_PNG_FORMAT = "PNG"


async def copy_png_to_clipboard(page: ft.Page, png_bytes: bytes) -> None:
    """
    Скопировать PNG-байты в системный clipboard.

    Args:
        page: Flet page. Может быть None при вызове вне GUI.
        png_bytes: PNG-изображение в байтах.

    Raises:
        RuntimeError: если изображение не удалось скопировать ни одним способом.
    """
    # 1) Flet path (web/mobile/future desktop)
    try:
        await ft.Clipboard().set_image(png_bytes)
        return
    except Exception as ex:  # noqa: BLE001 - на desktop это FletUnsupportedPlatformException
        logger.debug("ft.Clipboard().set_image() unavailable (%s); using native fallback", ex)

    # 2) Native fallback — блокирующие вызовы в executor'е
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _copy_native, png_bytes)
    except Exception as ex:
        logger.exception(ex)
        raise RuntimeError(str(ex)) from ex


def _copy_native(png_bytes: bytes) -> None:
    if sys.platform == "win32":
        _win_copy(png_bytes)
    elif sys.platform == "darwin":
        _mac_copy(png_bytes)
    else:  # linux и пр.
        _linux_copy(png_bytes)


# ---------------------------------------------------------------------------
# Windows (pythonnet / .NET)
# ---------------------------------------------------------------------------

def _win_copy(png_bytes: bytes) -> None:
    import clr

    clr.AddReference("System.Windows.Forms")
    clr.AddReference("System.Drawing")

    from System import Array, Byte
    from System.Drawing import Image as DImage
    from System.IO import MemoryStream
    from System.Threading import ApartmentState, ThreadStart
    from System.Threading import Thread as NetThread
    from System.Windows.Forms import Clipboard, DataObject

    errors: list[Exception] = []

    def worker():
        try:
            data_object = DataObject()
            # PNG с прозрачностью (Word, PowerPoint, LibreOffice понимают)
            data_object.SetData(
                _PNG_FORMAT, False, MemoryStream(Array[Byte](png_bytes))
            )
            # Bitmap для приложений, понимающих только DIB (mspaint и т.п.)
            img = DImage.FromStream(MemoryStream(Array[Byte](png_bytes)))
            data_object.SetImage(img)
            Clipboard.SetDataObject(data_object, True)
        except Exception as ex:  # noqa: BLE001
            errors.append(ex)

    # System.Windows.Forms.Clipboard требует STA-поток
    t = NetThread(ThreadStart(worker))
    t.SetApartmentState(ApartmentState.STA)
    t.Start()
    t.Join()

    if errors:
        raise errors[0]


# ---------------------------------------------------------------------------
# Linux (wl-copy / xclip)
# ---------------------------------------------------------------------------

def _linux_copy(png_bytes: bytes) -> None:
    wl = shutil.which("wl-copy")
    if wl:
        subprocess.run(
            [wl, "--type", "image/png"],
            input=png_bytes,
            check=True,
        )
        return

    xclip = shutil.which("xclip")
    if xclip:
        subprocess.run(
            [xclip, "-selection", "clipboard", "-t", "image/png"],
            input=png_bytes,
            check=True,
        )
        return

    raise RuntimeError(
        "Neither 'wl-copy' nor 'xclip' is installed. "
        "Install 'wl-clipboard' (Wayland) or 'xclip' (X11)."
    )


# ---------------------------------------------------------------------------
# macOS (osascript + temp PNG)
# ---------------------------------------------------------------------------

def _mac_copy(png_bytes: bytes) -> None:
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(png_bytes)
        # «class PNGf» — литералы в AppleScript: « » = \xab / \xbb
        script = (
            'set the clipboard to '
            f'(read (POSIX file "{path}") as \xabclass PNGf\xbb)'
        )
        subprocess.run(["osascript", "-e", script], check=True)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
