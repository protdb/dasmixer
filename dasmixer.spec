# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for DASMixer (Windows x64)
#
# Notes:
#   - Flet runs flet.exe as a subprocess; its entire directory must be bundled
#     under flet_desktop/app/flet/ so that flet_desktop.__init__ can locate it.
#   - npysearch uses a custom Windows wheel (_npysearch.cp314-win_amd64.pyd).
#   - pythonnet/clr requires ClrLoader.dll from clr_loader/ffi/dlls/amd64/.
#   - webview (pywebview) ships .NET DLLs in webview/lib/ that must be bundled.
#   - multiprocessing.freeze_support() is called in the entry point wrapper below.

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ---------------------------------------------------------------------------
# Resolve paths relative to this spec file
# ---------------------------------------------------------------------------
# IMPORTANT: dasmixer is NOT installed as a package in the venv (no pip install -e .).
# Poetry adds the project root to sys.path at runtime, but PyInstaller does NOT.
# We must inject it here so that collect_submodules() can actually find and
# enumerate all submodules of the dasmixer package.
_project_root = str(Path(SPECPATH))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
SPEC_DIR = Path(SPECPATH)

# Locate the active poetry virtual environment's site-packages
import subprocess
_venv_python = subprocess.check_output(
    ["poetry", "run", "python", "-c", "import sys; print(sys.executable)"],
    cwd=str(SPEC_DIR),
    text=True,
).strip()
_site = subprocess.check_output(
    [_venv_python, "-c",
     "import site; pkgs = site.getsitepackages();"
     " sp = next(p for p in pkgs if 'site-packages' in p); print(sp)"],
    text=True,
).strip()
SITE = Path(_site)

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------
datas = [
    # Project assets (icons, logos)
    (str(SPEC_DIR / "assets"), "assets"),

    # peptacular ships data files (chem.txt, *.obo, resid.xml, unimod.obo, ...)
    # that are loaded at runtime via relative paths — must be bundled explicitly.
    *collect_data_files("peptacular"),

    # Flet desktop client binary + all its DLLs and Flutter assets
    # flet_desktop locates it at: get_package_bin_dir() / "flet" / "flet.exe"
    (str(SITE / "flet_desktop" / "app" / "flet"), "flet_desktop/app/flet"),

    # webview .NET DLLs needed by pythonnet/WebView2
    (str(SITE / "webview" / "lib"), "webview/lib"),

    # clr_loader native DLL (needed to bootstrap pythonnet)
    (str(SITE / "clr_loader" / "ffi" / "dlls" / "amd64"), "clr_loader/ffi/dlls/amd64"),

    # choreographer ships last_known_good_chrome.json which kaleido reads via
    # Path(__file__).resolve().parent.parent / "resources" / "last_known_good_chrome.json"
    # Must be bundled at the same relative path so the frozen lookup succeeds.
    (str(SITE / "choreographer" / "resources"), "choreographer/resources"),
]

# ---------------------------------------------------------------------------
# Binary extensions (native .pyd files not auto-detected)
# ---------------------------------------------------------------------------
# NOTE: _npysearch and _cffi_backend are .pyd extension modules that PyInstaller
# picks up automatically through import tracing of npysearch/cffi packages.
# Do NOT add them manually here — doing so causes numpy to be initialized twice
# in the frozen process (Python 3.14 raises ImportError on double-load).
binaries = []

# ---------------------------------------------------------------------------
# Hidden imports — modules loaded dynamically or via string at runtime
# ---------------------------------------------------------------------------
hiddenimports = [
    # dasmixer GUI tabs — loaded dynamically via importlib.import_module() in
    # project_view.py (_TAB_DEFS); PyInstaller cannot detect these automatically.
    *collect_submodules("dasmixer.gui"),

    # dasmixer internals loaded via plugin_loader
    "dasmixer.api.inputs",
    "dasmixer.api.reporting",

    # npysearch — native .pyd must be reachable via the package
    "npysearch",
    "_npysearch",

    # numpy._core submodules — numpy hook may miss some on Python 3.14 / numpy 2.x
    *collect_submodules("numpy"),
    *collect_submodules("numpy._core"),

    # flet internals
    "flet.messaging.flet_socket_server",
    "flet.controls.context",
    "flet.utils",
    "flet.utils.pip",
    "flet.utils.deprecated",
    "flet_desktop",
    "flet_web",

    # webview / pythonnet
    "webview",
    "webview.platforms",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.guilib",
    "clr",
    "clr_loader",
    "pythonnet",

    # numpy/pandas sub-modules often needed
    "numpy",
    "numpy._core",
    "pandas",
    "pandas.io.formats.style",

    # pyteomics uses lxml
    "lxml",
    "lxml.etree",
    "lxml._elementpath",

    # scipy / sklearn dynamic imports
    "sklearn",
    "sklearn.tree._utils",
    "scipy",
    "scipy.special._ufuncs",
    "scipy.linalg.cython_blas",
    "scipy.linalg.cython_lapack",

    # unittest — excluded by PyInstaller by default but required by scipy/numpy internals
    "unittest",
    "unittest.mock",

    # misc
    "cffi",
    "aiosqlite",
    "aiofiles",
    "aiocsv",
    "pydantic",
    "pydantic_settings",
    "typer",
    "typer.core",
    "rich",
    "openpyxl",
    "xlrd",
    "kaleido",
    "plotly",
    "tabulate",
    "docxtpl",
    "jinja2",
    "multiprocessing",
    "pickle",
    "gzip",
    "sqlite3",
]

# ---------------------------------------------------------------------------
# Additional hook search paths (numpy ships its own hooks)
# ---------------------------------------------------------------------------
additional_hooks_dirs = [
    str(SITE / "numpy" / "_pyinstaller"),
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(SPEC_DIR / "dasmixer" / "main.py")],
    pathex=[str(SPEC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=additional_hooks_dirs,
    hooksconfig={},
    runtime_hooks=["rthooks/rthook_logfile.py"],
    excludes=[
        # Exclude test frameworks from the bundle
        "pytest",
        # NOTE: unittest must NOT be excluded — scipy/numpy.testing depend on it
        # Linux-only gtk backend for pywebview
        "webview.platforms.gtk",
        "webview.platforms.cocoa",
        "gi",
        "objc",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Single-folder EXE (--onedir style) — easier to debug and faster startup
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="dasmixer",
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # skip UPX to avoid antivirus false-positives
    console=True,      # no console window in release build
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icons/icon_256.ico",  # add .ico when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="dasmixer",
)
