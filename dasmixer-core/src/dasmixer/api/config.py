"""Application configuration stored in system folder."""

import json
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Literal

import typer
from dasmixer.utils.logger import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_tempdir() -> str:
    """Return the platform-appropriate default temporary directory.

    On Windows the system temp directory (``tempfile.gettempdir()``) is used.
    On Linux/macOS ``~/.cache/dasmixer`` is used.
    """
    if sys.platform == "win32":
        return str(Path(tempfile.gettempdir()))
    return str(Path.home() / ".cache" / "dasmixer")


_DEFAULT_TEMPDIR = default_tempdir()

_TEMP_DIR_POSTFIXES: dict[str, dict[str, str]] = {
    "HTML": {
        "win32": "",
        "default": "tmp/plots",
    },
    "MaxQuant": {
        "win32": "dasmixer/maxquant_import",
        "default": "tmp/maxquant_import",
    },
    "PXD": {
        "win32": "dasmixer/pride",
        "default": "pride",
    },
}

# Types that use large_file_tempdir as their base (large temporary files).
_LARGE_DIR_TYPES: frozenset[str] = frozenset({"PXD", "MaxQuant"})


class AppConfig(BaseSettings):
    """
    Application configuration stored in system folder.

    Stores user preferences and recent activity:
    - Last used paths for file operations
    - Recent projects list
    - UI settings
    - Batch operation limits
    - Default color palette
    - Plugin states and paths

    Configuration is automatically saved to system-specific folder:
    - Windows: %APPDATA%/dasmixer/config.json
    - Linux: ~/.config/dasmixer/config.json
    - macOS: ~/Library/Application Support/dasmixer/config.json
    """

    # Paths
    last_project_path: str | None = None
    last_import_folder: str | None = None
    last_export_folder: str | None = None

    # Recent projects (list of paths, max 10)
    recent_projects: list[str] = []

    # UI settings
    theme: str = "light"
    window_width: int = 1200
    window_height: int = 800
    plot_aspect_ratio: str = "16:9"  # Plot aspect ratio: "1:1" | "4:3" | "2:3" | "16:9"
    plot_view_mode: str = "Window"    # Interactive viewer mode: "Window" | "Browser"

    # Batch operation limits
    spectra_batch_size: int = 5000
    identification_batch_size: int = 5000
    identification_processing_batch_size: int = 5000
    protein_mapping_batch_size: int = 5000
    
    # CPU threads for multiprocessing (None = auto: cpu_count - 1)
    max_cpu_threads: int | None = None

    # Default color palette (shared pool for tools and subsets)
    default_colors: list[str] = [
        "#3B82F6",  # blue
        "#10B981",  # green
        "#F59E0B",  # amber
        "#EF4444",  # red
        "#8B5CF6",  # violet
        "#06B6D4",  # cyan
        "#F97316",  # orange
        "#EC4899",  # pink
    ]

    # Logging settings
    log_to_file: bool = False
    log_level: str = "INFO"           # DEBUG | INFO | WARNING | ERROR
    log_folder: str | None = None     # None = ~/.cache/dasmixer/logs/
    log_separate_workers: bool = False  # If True, workers write separate per-PID files

    # Plugin states: {plugin_id: enabled}
    plugin_states: dict[str, bool] = {}

    # Plugin file paths: {plugin_id: str path to file or directory}
    plugin_paths: dict[str, str] = {}

    # Temporary directories
    tempdir: str = _DEFAULT_TEMPDIR
    large_file_tempdir: str = _DEFAULT_TEMPDIR

    model_config = SettingsConfigDict(
        env_prefix="DASMIXER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def get_config_path(cls) -> Path:
        """
        Get path to config file in system folder.

        Returns:
            Path to config.json in application directory
        """
        app_dir = Path(typer.get_app_dir("dasmixer"))
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "config.json"

    @classmethod
    def load(cls) -> 'AppConfig':
        """
        Load config from file or create default.

        Returns:
            Loaded or default configuration
        """
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                logger.exception(f"Could not load config: {e}")
                return cls()
        return cls()

    def save(self) -> None:
        """Save config to file."""
        config_path = self.get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.model_dump(), f, indent=2)
        except Exception as e:
            logger.exception(f"Could not save config: {e}")

    def get_next_color(self, existing_colors: list[str]) -> str:
        """
        Get next color from the default palette not yet used.

        Returns the first color from default_colors not in existing_colors.
        If all colors are used, returns the first color in the palette.

        Args:
            existing_colors: List of already-used hex color strings

        Returns:
            Hex color string
        """
        existing_lower = {c.lower() for c in existing_colors}
        for color in self.default_colors:
            if color.lower() not in existing_lower:
                return color
        return self.default_colors[0] if self.default_colors else "#3B82F6"

    def add_recent_project(self, path: str) -> None:
        """
        Add project to recent list (max 10, most recent first).

        Args:
            path: Path to project file
        """
        abs_path = str(Path(path).absolute())

        if abs_path in self.recent_projects:
            self.recent_projects.remove(abs_path)

        self.recent_projects.insert(0, abs_path)
        self.recent_projects = self.recent_projects[:10]
        self.last_project_path = abs_path
        self.save()

    def remove_recent_project(self, path: str) -> None:
        """
        Remove project from recent list.

        Args:
            path: Path to project file
        """
        abs_path = str(Path(path).absolute())
        if abs_path in self.recent_projects:
            self.recent_projects.remove(abs_path)
            self.save()

    def update_last_import_folder(self, folder: str) -> None:
        """
        Update last used import folder.

        Args:
            folder: Path to folder
        """
        self.last_import_folder = str(Path(folder).absolute())
        self.save()

    def update_last_export_folder(self, folder: str) -> None:
        """
        Update last used export folder.

        Args:
            folder: Path to folder
        """
        self.last_export_folder = str(Path(folder).absolute())
        self.save()

    def set_plugin_state(self, plugin_id: str, enabled: bool) -> None:
        """
        Set plugin enabled/disabled state.

        Args:
            plugin_id: Plugin identifier (filename without extension)
            enabled: Whether plugin is enabled
        """
        self.plugin_states[plugin_id] = enabled
        self.save()

    def register_plugin_path(self, plugin_id: str, path: str) -> None:
        """
        Register file path for a plugin (for deletion support).

        Args:
            plugin_id: Plugin identifier
            path: Path to plugin file or directory
        """
        self.plugin_paths[plugin_id] = str(Path(path).absolute())
        self.save()

    def unregister_plugin(self, plugin_id: str) -> None:
        """
        Remove plugin from config records.

        Args:
            plugin_id: Plugin identifier
        """
        self.plugin_states.pop(plugin_id, None)
        self.plugin_paths.pop(plugin_id, None)
        self.save()

    def get_tempdir(
        self,
        dir_type: Literal['HTML', 'PXD', 'MaxQuant', 'root', 'large_root'] = 'root',
    ) -> Path:
        """
        Get a temporary directory path for the specified type.

        The base directory is taken from :attr:`tempdir` (or
        :attr:`large_file_tempdir` for ``large_root``). A platform-specific
        sub-path (postfix) is appended for typed directories.

        The returned directory is created (with parents) if it does not
        exist.

        Args:
            dir_type: Type of temporary directory:

                - ``'root'`` — base :attr:`tempdir`.
                - ``'large_root'`` — base :attr:`large_file_tempdir`.
                - ``'HTML'`` — directory for temporary HTML files (uses
                  :attr:`tempdir`).
                - ``'MaxQuant'`` — directory for MaxQuant import temp files
                  (uses :attr:`large_file_tempdir`; includes a timestamp
                  sub-directory).
                - ``'PXD'`` — directory for PRIDE PXD temp files (uses
                  :attr:`large_file_tempdir`).

        Returns:
            Path to an existing directory.
        """
        if dir_type == 'root':
            path = Path(self.tempdir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        if dir_type == 'large_root':
            path = Path(self.large_file_tempdir)
            path.mkdir(parents=True, exist_ok=True)
            return path

        platform_key = "win32" if sys.platform == "win32" else "default"
        postfix = _TEMP_DIR_POSTFIXES.get(dir_type, {}).get(platform_key, "")

        base = self.large_file_tempdir if dir_type in _LARGE_DIR_TYPES else self.tempdir
        path = Path(base)
        if postfix:
            path = path / postfix

        if dir_type == 'MaxQuant':
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = path / ts

        path.mkdir(parents=True, exist_ok=True)
        return path


# Global config instance
# Loaded once on module import
config = AppConfig.load()


def get_temp_html_dir() -> Path:
    """
    Get directory for temporary HTML files produced in Browser display mode.

    .. deprecated::
        Use :meth:`AppConfig.get_tempdir` with ``dir_type='HTML'`` instead.

    Returns:
        Path to an existing directory for temporary HTML files.
    """
    warnings.warn(
        "get_temp_html_dir() is deprecated; "
        "use config.get_tempdir('HTML') instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return config.get_tempdir('HTML')


def get_maxquant_import_temp_dir() -> Path:
    """
    Directory for temporary MGF/CSV files created during MaxQuant import.

    .. deprecated::
        Use :meth:`AppConfig.get_tempdir` with ``dir_type='MaxQuant'`` instead.

    Returns:
        Path to an existing directory for MaxQuant temporary files.
    """
    warnings.warn(
        "get_maxquant_import_temp_dir() is deprecated; "
        "use config.get_tempdir('MaxQuant') instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return config.get_tempdir('MaxQuant')


def get_pxd_temp_dir() -> Path:
    """
    Directory for temporary PRIDE PXD dataset files.

    .. deprecated::
        Use :meth:`AppConfig.get_tempdir` with ``dir_type='PXD'`` instead.

    Returns:
        Path to the PRIDE temporary directory.
    """
    warnings.warn(
        "get_pxd_temp_dir() is deprecated; "
        "use config.get_tempdir('PXD') instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return config.get_tempdir('PXD')