"""Dynamic plugin loading for identification parsers and report modules."""

import importlib.util
import sys
import traceback
import shutil
import zipfile
from pathlib import Path
import typer

from dasmixer.api.config import config


class PluginConflictError(Exception):
    """Raised when a plugin tries to register a name already occupied by a built-in."""


def get_plugins_dir() -> Path:
    """Return path to plugins root directory in app data folder."""
    return Path(typer.get_app_dir("dasmixer")) / "plugins"


def get_identification_plugins_dir() -> Path:
    return get_plugins_dir() / "inputs" / "identifications"


def get_reports_plugins_dir() -> Path:
    return get_plugins_dir() / "reports"


def _ensure_plugin_dirs():
    """Create plugin directories if they don't exist."""
    get_identification_plugins_dir().mkdir(parents=True, exist_ok=True)
    get_reports_plugins_dir().mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Internal loader
# --------------------------------------------------------------------------

def _load_plugin_file(path: Path, plugin_id: str) -> tuple[bool, str | None]:
    """
    Import a single .py plugin file.

    Args:
        path: Path to .py file
        plugin_id: Unique identifier (used as module name)

    Returns:
        (success, error_message)
    """
    try:
        spec = importlib.util.spec_from_file_location(f"dasmixer_plugin_{plugin_id}", path)
        if spec is None or spec.loader is None:
            return False, f"Cannot create module spec from {path}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"dasmixer_plugin_{plugin_id}"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return True, None
    except KeyError as e:
        # Registry raises KeyError on duplicate names
        msg = str(e).strip("'\"")
        if "already registered" in msg:
            raise PluginConflictError(
                f"Plugin name conflict: {msg}. "
                f"This name is already used by a built-in module."
            ) from e
        return False, traceback.format_exc()
    except PluginConflictError:
        raise
    except Exception:
        return False, traceback.format_exc()


def _load_module_from_dir(module_dir: Path, plugin_id: str) -> tuple[bool, str | None]:
    """
    Import a plugin that is a Python package (directory with __init__.py).

    Args:
        module_dir: Path to module directory containing __init__.py
        plugin_id: Unique identifier

    Returns:
        (success, error_message)
    """
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return False, f"No __init__.py found in {module_dir}"
    return _load_plugin_file(init_file, plugin_id)


def _collect_py_entries(directory: Path) -> list[Path]:
    """Return all .py files and package directories in a directory (non-recursive)."""
    entries = []
    for item in sorted(directory.iterdir()):
        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
            entries.append(item)
        elif item.is_dir() and (item / "__init__.py").exists():
            entries.append(item)
    return entries


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def load_identification_plugins() -> list[dict]:
    """
    Load identification parser plugins from plugins/inputs/identifications/.

    Each plugin file/package must call at module level:
        from dasmixer.api.inputs.registry import registry
        registry.add_identification_parser("PluginName", MyParserClass)

    Returns:
        list of dicts:
            id (str): plugin identifier (filename without extension)
            path (Path): path to plugin file/directory
            name (str): display name (same as id if not overridable)
            error (str | None): error message if loading failed
            builtin (bool): always False for external plugins
            plugin_type (str): "identification"
    """
    _ensure_plugin_dirs()
    results = []
    plugin_dir = get_identification_plugins_dir()

    for entry in _collect_py_entries(plugin_dir):
        plugin_id = entry.stem if entry.is_file() else entry.name
        enabled = config.plugin_states.get(plugin_id, True)

        if not enabled:
            results.append({
                "id": plugin_id,
                "path": entry,
                "name": plugin_id,
                "error": None,
                "builtin": False,
                "plugin_type": "identification",
                "enabled": False,
            })
            continue

        try:
            if entry.is_file():
                success, error = _load_plugin_file(entry, plugin_id)
            else:
                success, error = _load_module_from_dir(entry, plugin_id)
        except PluginConflictError as e:
            success, error = False, str(e)

        results.append({
            "id": plugin_id,
            "path": entry,
            "name": plugin_id,
            "error": error,
            "builtin": False,
            "plugin_type": "identification",
            "enabled": enabled,
        })

    return results


def load_report_plugins() -> list[dict]:
    """
    Load report module plugins from plugins/reports/.

    Each plugin file/package must call at module level:
        from dasmixer.api.reporting.registry import registry
        registry.register(MyReportClass)

    Returns:
        list of dicts — same structure as load_identification_plugins,
        plugin_type = "report"
    """
    _ensure_plugin_dirs()
    results = []
    plugin_dir = get_reports_plugins_dir()

    for entry in _collect_py_entries(plugin_dir):
        plugin_id = entry.stem if entry.is_file() else entry.name
        enabled = config.plugin_states.get(plugin_id, True)

        if not enabled:
            results.append({
                "id": plugin_id,
                "path": entry,
                "name": plugin_id,
                "error": None,
                "builtin": False,
                "plugin_type": "report",
                "enabled": False,
            })
            continue

        try:
            if entry.is_file():
                success, error = _load_plugin_file(entry, plugin_id)
            else:
                success, error = _load_module_from_dir(entry, plugin_id)
        except PluginConflictError as e:
            success, error = False, str(e)

        results.append({
            "id": plugin_id,
            "path": entry,
            "name": plugin_id,
            "error": error,
            "builtin": False,
            "plugin_type": "report",
            "enabled": enabled,
        })

    return results


def install_plugin_file(src_path: Path, plugin_type: str) -> tuple[bool, str, str | None]:
    """
    Copy or extract a plugin file into the plugins directory.

    .py  → copied directly
    .zip → extracted as a package:
        - If __init__.py is in the zip root: extract contents into
          a new folder named after the zip (without extension)
        - If __init__.py is in the single top-level subdirectory:
          extract the archive as-is (folder name preserved)

    Args:
        src_path: Path to source .py or .zip file
        plugin_type: "identification" or "report"

    Returns:
        (success, plugin_id, error_message)
    """
    if plugin_type == "identification":
        dest_dir = get_identification_plugins_dir()
    elif plugin_type == "report":
        dest_dir = get_reports_plugins_dir()
    else:
        return False, "", f"Unknown plugin_type: {plugin_type}"

    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        if src_path.suffix == ".py":
            dest = dest_dir / src_path.name
            shutil.copy2(src_path, dest)
            plugin_id = src_path.stem
            config.register_plugin_path(plugin_id, str(dest))
            return True, plugin_id, None

        elif src_path.suffix == ".zip":
            return _install_zip_plugin(src_path, dest_dir)
        else:
            return False, "", f"Unsupported file type: {src_path.suffix}"

    except Exception:
        return False, "", traceback.format_exc()


def _install_zip_plugin(src_path: Path, dest_dir: Path) -> tuple[bool, str, str | None]:
    """
    Extract a .zip plugin archive.

    Rules:
    1. If __init__.py is in the zip root → extract all into a new folder
       named after the zip (without .zip extension).
    2. If __init__.py is in the single top-level subfolder → extract the
       archive as-is (the subfolder becomes the package).
    3. Otherwise → error (no valid Python package found in archive).
    """
    try:
        with zipfile.ZipFile(src_path, "r") as zf:
            names = zf.namelist()

            # Check for __init__.py in root
            if "__init__.py" in names:
                # Case 1: extract into new folder named after zip
                module_name = src_path.stem
                dest_module_dir = dest_dir / module_name
                dest_module_dir.mkdir(parents=True, exist_ok=True)
                zf.extractall(dest_module_dir)
                config.register_plugin_path(module_name, str(dest_module_dir))
                return True, module_name, None

            # Check for single top-level folder containing __init__.py
            top_level_dirs = {
                n.split("/")[0]
                for n in names
                if "/" in n and not n.endswith("/")
            }
            top_level_dirs = {d for d in top_level_dirs if d}

            if len(top_level_dirs) == 1:
                folder_name = next(iter(top_level_dirs))
                init_path = f"{folder_name}/__init__.py"
                if init_path in names:
                    # Case 2: extract as-is
                    zf.extractall(dest_dir)
                    dest_module_dir = dest_dir / folder_name
                    config.register_plugin_path(folder_name, str(dest_module_dir))
                    return True, folder_name, None

            return False, "", (
                "Archive does not contain a valid Python package. "
                "Expected __init__.py in the archive root or in a single subfolder."
            )
    except zipfile.BadZipFile as e:
        return False, "", f"Invalid zip archive: {e}"


def delete_plugin(plugin_id: str) -> tuple[bool, str | None]:
    """
    Physically delete a plugin file or directory.

    Uses path stored in config.plugin_paths. If not found there,
    tries to locate by id in both plugin directories.

    Args:
        plugin_id: Plugin identifier

    Returns:
        (success, error_message)
    """
    path_str = config.plugin_paths.get(plugin_id)

    if path_str:
        target = Path(path_str)
    else:
        # Fallback: search both dirs
        for d in [get_identification_plugins_dir(), get_reports_plugins_dir()]:
            for candidate in [d / f"{plugin_id}.py", d / plugin_id]:
                if candidate.exists():
                    target = candidate
                    break
            else:
                continue
            break
        else:
            return False, f"Plugin '{plugin_id}' not found on disk"

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        config.unregister_plugin(plugin_id)
        return True, None
    except Exception:
        return False, traceback.format_exc()
