"""
Settings manager for handling persistent application settings.
Manages JSON-based configuration storage.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


class SettingsManager:
    """Manages loading and saving of application settings to JSON file."""

    def __init__(self, settings_file: Path):
        """
        Initialize the settings manager.

        Args:
            settings_file: Path to the JSON settings file
        """
        self.settings_file = settings_file
        self._settings_cache: Dict[str, Any] = {}
        self._ensure_settings_directory()
        self.load_settings()

    def _ensure_settings_directory(self):
        """Ensure the settings directory exists."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> Dict[str, Any]:
        """
        Load settings from the JSON file.

        Returns:
            Dictionary containing all settings
        """
        if not self.settings_file.exists():
            self._settings_cache = self._get_default_settings()
            return self._settings_cache

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                self._settings_cache = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.error("Error loading settings from %s: %s", self.settings_file, e)
            self._settings_cache = self._get_default_settings()

        return self._settings_cache

    def save_settings(self) -> bool:
        """
        Save current settings to the JSON file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._settings_cache, f, indent=4)
            return True
        except IOError as e:
            log.error("Error saving settings to %s: %s", self.settings_file, e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if key doesn't exist

        Returns:
            Setting value or default
        """
        return self._settings_cache.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value
            auto_save: Whether to automatically save to file
        """
        self._settings_cache[key] = value
        if auto_save:
            self.save_settings()

    def update(self, settings: Dict[str, Any], auto_save: bool = True) -> None:
        """
        Update multiple settings at once.

        Args:
            settings: Dictionary of settings to update
            auto_save: Whether to automatically save to file
        """
        self._settings_cache.update(settings)
        if auto_save:
            self.save_settings()

    def remove(self, key: str, auto_save: bool = True) -> Any:
        """
        Remove a setting.

        Args:
            key: Setting key to remove
            auto_save: Whether to automatically save to file

        Returns:
            The removed value, or None if key didn't exist
        """
        value = self._settings_cache.pop(key, None)
        if auto_save and value is not None:
            self.save_settings()
        return value

    def clear(self, auto_save: bool = True) -> None:
        """
        Clear all settings and reset to defaults.

        Args:
            auto_save: Whether to automatically save to file
        """
        self._settings_cache = self._get_default_settings()
        if auto_save:
            self.save_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """
        Get default settings structure.

        Returns:
            Dictionary with default settings
        """
        return {
            "games": {},
            "game_exe_paths": {},
            "game_order": [],
            "ui_settings": {},
            "tracked_external_mods": {},
            "profiles": {},
            "active_profiles": {},
            "custom_config_paths": {},
            "me3_config_paths": {},
        }

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get a copy of all current settings.

        Returns:
            Dictionary containing all settings
        """
        return self._settings_cache.copy()

    def has_key(self, key: str) -> bool:
        """
        Check if a setting key exists.

        Args:
            key: Setting key to check

        Returns:
            True if key exists, False otherwise
        """
        return key in self._settings_cache
