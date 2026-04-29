"""Application configuration stored in system folder."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import typer
import json
from typing import Any

from dasmixer.utils.logger import logger


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

    model_config = SettingsConfigDict(
        env_prefix="DASMIXER_",
        env_file=".env",
        env_file_encoding="utf-8"
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


# Global config instance
# Loaded once on module import
config = AppConfig.load()
