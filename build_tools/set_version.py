#!/usr/bin/env python3
"""
set_version.py — синхронизация версии во всех файлах проекта DASMixer.

Использование:
    python build_tools/set_version.py <new_version>

Пример:
    python build_tools/set_version.py 0.6.0

Меняет версию в:
  - dasmixer-core/pyproject.toml              [project].version
  - dasmixer-gui/pyproject.toml              [project].version + зависимость на dasmixer-core
  - dasmixer-cli/pyproject.toml              [project].version + зависимость на dasmixer-core
  - metapackage/pyproject.toml               [project].version + зависимости на все три пакета
  - pyproject.toml                           [project].version (workspace root)
  - dasmixer-core/src/dasmixer/versions.py   APP_VERSION (НЕ трогает PROJECT_VERSION и MIN_SUPPORTED_PROJECT_VERSION)
  - metapackage/dasmixer/__init__.py         __version__
  - dasmixer.iss                             #define MyAppVersion
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def replace_exact(path: Path, old: str, new: str) -> bool:
    """Заменяет первое вхождение old на new в файле. Возвращает True если замена произошла."""
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def replace_regex(path: Path, pattern: str, replacement: str) -> bool:
    """Заменяет первое совпадение regex в файле. Возвращает True если замена произошла."""
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1)
    if count == 0:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def set_version(new_version: str) -> None:
    changes: list[tuple[str, str]] = []  # (file, description)
    errors: list[str] = []

    def apply(path: Path, old: str, new: str, description: str) -> None:
        rel = path.relative_to(REPO_ROOT)
        if replace_exact(path, old, new):
            changes.append((str(rel), description))
        else:
            errors.append(f"  NOT FOUND in {rel}: {repr(old)}")

    # ------------------------------------------------------------------
    # 1. dasmixer-core/pyproject.toml — [project].version
    # ------------------------------------------------------------------
    core_toml = REPO_ROOT / "dasmixer-core" / "pyproject.toml"
    text = core_toml.read_text(encoding="utf-8")
    old_core_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if old_core_ver:
        old_v = old_core_ver.group(1)
        apply(core_toml, f'version = "{old_v}"', f'version = "{new_version}"',
              f"[project].version: {old_v} -> {new_version}")
    else:
        errors.append(f"  version not found in dasmixer-core/pyproject.toml")

    # ------------------------------------------------------------------
    # 2. dasmixer-gui/pyproject.toml — [project].version + dep on dasmixer-core
    # ------------------------------------------------------------------
    gui_toml = REPO_ROOT / "dasmixer-gui" / "pyproject.toml"
    text = gui_toml.read_text(encoding="utf-8")

    old_gui_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if old_gui_ver:
        old_v = old_gui_ver.group(1)
        apply(gui_toml, f'version = "{old_v}"', f'version = "{new_version}"',
              f"[project].version: {old_v} -> {new_version}")

    # Зависимость на dasmixer-core — может быть любая версия (включая устаревшую)
    dep_match = re.search(r'"dasmixer-core\[all\]\s*==([^"]+)"', text)
    if dep_match:
        old_dep = dep_match.group(1).strip()
        apply(gui_toml,
              f'"dasmixer-core[all] =={old_dep}"',
              f'"dasmixer-core[all] =={new_version}"',
              f"dep dasmixer-core[all]: {old_dep} -> {new_version}")
    else:
        errors.append(f"  dasmixer-core[all] dependency not found in dasmixer-gui/pyproject.toml")

    # ------------------------------------------------------------------
    # 3. dasmixer-cli/pyproject.toml — [project].version + dep on dasmixer-core
    # ------------------------------------------------------------------
    cli_toml = REPO_ROOT / "dasmixer-cli" / "pyproject.toml"
    text = cli_toml.read_text(encoding="utf-8")

    old_cli_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if old_cli_ver:
        old_v = old_cli_ver.group(1)
        apply(cli_toml, f'version = "{old_v}"', f'version = "{new_version}"',
              f"[project].version: {old_v} -> {new_version}")

    dep_match = re.search(r'"dasmixer-core\s*==([^"]+)"', text)
    if dep_match:
        old_dep = dep_match.group(1).strip()
        apply(cli_toml,
              f'"dasmixer-core =={old_dep}"',
              f'"dasmixer-core =={new_version}"',
              f"dep dasmixer-core: {old_dep} -> {new_version}")
    else:
        errors.append(f"  dasmixer-core dependency not found in dasmixer-cli/pyproject.toml")

    # ------------------------------------------------------------------
    # 4. metapackage/pyproject.toml — [project].version + deps на все три пакета
    #    Metapackage использовал формат "0.6.0.a2" (с точкой перед a).
    #    Теперь приводим его к тому же формату, что и остальные.
    # ------------------------------------------------------------------
    meta_toml = REPO_ROOT / "metapackage" / "pyproject.toml"
    text = meta_toml.read_text(encoding="utf-8")

    old_meta_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if old_meta_ver:
        old_v = old_meta_ver.group(1).strip()
        apply(meta_toml, f'version = "{old_v}"', f'version = "{new_version}"',
              f"[project].version: {old_v} -> {new_version}")

    for pkg in ("dasmixer-core", "dasmixer-gui", "dasmixer-cli"):
        dep_match = re.search(rf'"{re.escape(pkg)}\s*==([^"]+)"', text)
        if dep_match:
            old_dep = dep_match.group(1).strip()
            apply(meta_toml,
                  f'"{pkg} =={old_dep}"',
                  f'"{pkg} =={new_version}"',
                  f"dep {pkg}: {old_dep} -> {new_version}")
        else:
            errors.append(f"  {pkg} dependency not found in metapackage/pyproject.toml")

    # ------------------------------------------------------------------
    # 5. pyproject.toml (workspace root) — [project].version
    # ------------------------------------------------------------------
    root_toml = REPO_ROOT / "pyproject.toml"
    text = root_toml.read_text(encoding="utf-8")
    old_root_ver = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if old_root_ver:
        old_v = old_root_ver.group(1)
        apply(root_toml, f'version = "{old_v}"', f'version = "{new_version}"',
              f"[project].version: {old_v} -> {new_version}")
    else:
        errors.append(f"  version not found in root pyproject.toml")

    # ------------------------------------------------------------------
    # 6. dasmixer-core/src/dasmixer/versions.py — только APP_VERSION
    #    PROJECT_VERSION и MIN_SUPPORTED_PROJECT_VERSION не трогаем.
    # ------------------------------------------------------------------
    versions_py = REPO_ROOT / "dasmixer-core" / "src" / "dasmixer" / "versions.py"
    text = versions_py.read_text(encoding="utf-8")
    app_ver_match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if app_ver_match:
        old_v = app_ver_match.group(1)
        apply(versions_py,
              f'APP_VERSION = "{old_v}"',
              f'APP_VERSION = "{new_version}"',
              f"APP_VERSION: {old_v} -> {new_version}")
    else:
        errors.append(f"  APP_VERSION not found in versions.py")

    # ------------------------------------------------------------------
    # 7. metapackage/dasmixer/__init__.py — __version__
    # ------------------------------------------------------------------
    meta_init = REPO_ROOT / "metapackage" / "dasmixer" / "__init__.py"
    text = meta_init.read_text(encoding="utf-8")
    init_ver_match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if init_ver_match:
        old_v = init_ver_match.group(1)
        apply(meta_init,
              f'__version__ = "{old_v}"',
              f'__version__ = "{new_version}"',
              f"__version__: {old_v} -> {new_version}")
    else:
        errors.append(f"  __version__ not found in metapackage/dasmixer/__init__.py")

    # ------------------------------------------------------------------
    # 8. dasmixer.iss — #define MyAppVersion
    # ------------------------------------------------------------------
    iss_file = REPO_ROOT / "dasmixer.iss"
    text = iss_file.read_text(encoding="utf-8")
    iss_ver_match = re.search(r'#define MyAppVersion\s+"([^"]+)"', text)
    if iss_ver_match:
        old_v = iss_ver_match.group(1)
        apply(iss_file,
              f'#define MyAppVersion "{old_v}"',
              f'#define MyAppVersion "{new_version}"',
              f"#define MyAppVersion: {old_v} -> {new_version}")
    else:
        errors.append(f"  MyAppVersion not found in dasmixer.iss")

    # ------------------------------------------------------------------
    # Итоговый отчёт
    # ------------------------------------------------------------------
    print(f"Version set to: {new_version}\n")

    if changes:
        print(f"Updated ({len(changes)} changes):")
        for filepath, desc in changes:
            print(f"  {filepath}: {desc}")

    if errors:
        print(f"\nWarnings ({len(errors)}):")
        for err in errors:
            print(err)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <new_version>")
        print(f"Example: python {sys.argv[0]} 0.6.0")
        sys.exit(1)

    new_version = sys.argv[1].strip()
    if not re.match(r'^\d+\.\d+\.\d+', new_version):
        print(f"Error: version must start with X.Y.Z (got: {new_version!r})")
        sys.exit(1)

    set_version(new_version)


if __name__ == "__main__":
    main()
