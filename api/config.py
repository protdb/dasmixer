"""Application configuration stored in system folder."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import typer
import json
from typing import Any


class AppConfig(BaseSettings):
    """
    Application configuration stored in system folder.
    
    Stores user preferences and recent activity:
    - Last used paths for file operations
    - Recent projects list
    - UI settings (future)
    
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
    
    # UI settings (future use)
    theme: str = "light"
    window_width: int = 1200
    window_height: int = 800
    
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
                print(f"Warning: Could not load config: {e}")
                return cls()
        return cls()
    
    def save(self) -> None:
        """Save config to file."""
        config_path = self.get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.model_dump(), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
    
    def add_recent_project(self, path: str) -> None:
        """
        Add project to recent list (max 10, most recent first).
        
        Args:
            path: Path to project file
        """
        # Convert to absolute path string
        abs_path = str(Path(path).absolute())
        
        # Remove if already exists
        if abs_path in self.recent_projects:
            self.recent_projects.remove(abs_path)
        
        # Add to beginning
        self.recent_projects.insert(0, abs_path)
        
        # Keep only last 10
        self.recent_projects = self.recent_projects[:10]
        
        # Update last project path
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


# Global config instance
# Loaded once on module import
config = AppConfig.load()
