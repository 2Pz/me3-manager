"""
Path management for ME3 Manager.
Handles all path resolution, custom paths, and directory management.
"""

import os
import sys
from pathlib import Path
from typing import Any

from me3_manager.utils.path_utils import PathUtils


class PathManager:
    """Manages all path resolution and directory operations."""

    def __init__(self, settings_manager, game_registry, me3_info=None):
        """
        Initialize path manager.

        Args:
            settings_manager: Reference to SettingsManager
            game_registry: Reference to GameRegistry
            me3_info: Optional ME3InfoManager instance
        """
        self.settings_manager = settings_manager
        self.game_registry = game_registry
        self.me3_info = me3_info
        self._config_root = None
        self._initialize_config_root()

    def _initialize_config_root(self):
        """Initialize the configuration root directory."""
        # Try to get dynamic config root from ME3
        if self.me3_info:
            dynamic_profile_dir = self.me3_info.get_profile_directory()
            if dynamic_profile_dir:
                self._config_root = Path(dynamic_profile_dir)
                return

        # Use platform-specific paths for ME3 config
        if sys.platform == "win32":
            localappdata = os.environ.get("LOCALAPPDATA")
            if localappdata:
                self._config_root = (
                    Path(localappdata) / "garyttierney" / "me3" / "config" / "profiles"
                )
            else:
                self._config_root = (
                    Path.home()
                    / "AppData"
                    / "Local"
                    / "garyttierney"
                    / "me3"
                    / "config"
                    / "profiles"
                )
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                self._config_root = Path(xdg_config) / "me3" / "profiles"
            else:
                self._config_root = Path.home() / ".config" / "me3" / "profiles"

    @property
    def config_root(self) -> Path:
        """
        Get the configuration root directory.

        Returns:
            Path to config root
        """
        return self._config_root

    def get_settings_file_path(self) -> Path:
        """
        Get the path to the settings file.

        Returns:
            Path to manager_settings.json
        """
        return self.config_root.parent / "manager_settings.json"

    def get_mods_dir(self, game_name: str) -> Path:
        """
        Get the mods directory for a game's active profile.

        Args:
            game_name: Name of the game

        Returns:
            Path to mods directory
        """
        # Check for custom mods path in active profile
        active_profile = self._get_active_profile(game_name)
        if active_profile and active_profile.get("mods_path"):
            return Path(active_profile["mods_path"])

        # Default to config_root/mods_dir
        mods_dir_name = self.game_registry.get_game_mods_dir(game_name)
        if mods_dir_name:
            return self.config_root / mods_dir_name

        # Fallback
        return self.config_root / f"{game_name.lower()}-mods"

    def get_profile_path(self, game_name: str) -> Path:
        """
        Get the profile file path for a game's active profile.

        Args:
            game_name: Name of the game

        Returns:
            Path to profile file
        """
        # Check for custom profile path in active profile
        active_profile = self._get_active_profile(game_name)
        if active_profile and active_profile.get("profile_path"):
            return Path(active_profile["profile_path"])

        # Default to config_root/profile
        profile_name = self.game_registry.get_game_profile_name(game_name)
        if profile_name:
            return self.config_root / profile_name

        # Fallback
        return self.config_root / f"{game_name.lower()}-default.me3"

    def get_mod_config_path(self, game_name: str, mod_path_str: str) -> Path:
        """
        Get the config path for a mod.

        Args:
            game_name: Name of the game
            mod_path_str: Path to the mod

        Returns:
            Path to mod config file
        """
        # Create a canonical key for lookups
        mod_key = mod_path_str.replace("\\", "/").lower()

        # Check for saved custom path
        custom_paths = self.settings_manager.get("custom_config_paths", {})
        game_custom_paths = custom_paths.get(game_name, {})
        custom_path = game_custom_paths.get(mod_key)

        if custom_path:
            return Path(custom_path)

        # Default convention: mod_folder/config.ini
        mod_path = Path(mod_path_str)
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def set_mod_config_path(
        self, game_name: str, mod_path_str: str, config_path: str
    ) -> None:
        """
        Set a custom config path for a mod.

        Args:
            game_name: Name of the game
            mod_path_str: Path to the mod
            config_path: Custom config path
        """
        # Use canonical key
        mod_key = mod_path_str.replace("\\", "/").lower()

        # Get or create custom paths structure
        custom_paths = self.settings_manager.get("custom_config_paths", {})
        if game_name not in custom_paths:
            custom_paths[game_name] = {}

        # Save the custom path
        custom_paths[game_name][mod_key] = config_path
        self.settings_manager.set("custom_config_paths", custom_paths)

    def get_me3_config_path(self, game_name: str) -> Path | None:
        """
        Get the ME3 config file path for a game.

        Args:
            game_name: Name of the game

        Returns:
            Path to ME3 config or None
        """
        # Check for custom path
        me3_paths = self.settings_manager.get("me3_config_paths", {})
        custom_path = me3_paths.get(game_name)

        if custom_path:
            custom_path_obj = Path(custom_path)
            if custom_path_obj.exists():
                return custom_path_obj
            else:
                # Remove invalid custom path
                del me3_paths[game_name]
                self.settings_manager.set("me3_config_paths", me3_paths)

        # Try to find config through ME3 info
        if self.me3_info:
            return self.me3_info.get_primary_config_path()

        return None

    def set_me3_config_path(self, game_name: str, config_path: str) -> None:
        """
        Set a custom ME3 config path for a game.

        Args:
            game_name: Name of the game
            config_path: Path to ME3 config
        """
        me3_paths = self.settings_manager.get("me3_config_paths", {})
        me3_paths[game_name] = config_path
        self.settings_manager.set("me3_config_paths", me3_paths)

    def get_me3_binary_path(self) -> Path:
        """
        Get the path where the ME3 binary/executable should be installed.
        This is typically a 'bin' directory alongside the 'config' directory.

        Returns:
            Path to the binary installation directory.
        """
        # self.config_root is .../me3/config/profiles
        # We want .../me3/bin
        me3_root = self.config_root.parent.parent
        return me3_root / "bin"

    def ensure_directories(self, game_name: str | None = None) -> None:
        """
        Ensure necessary directories exist.

        Args:
            game_name: Optional specific game to ensure directories for
        """
        # Ensure config root exists
        self.config_root.mkdir(parents=True, exist_ok=True)

        # Ensure game directories
        if game_name:
            games = {game_name: self.game_registry.get_game(game_name)}
        else:
            games = self.game_registry.get_all_games()

        for name, game_info in games.items():
            if game_info:
                # Ensure mods directory
                mods_dir = self.get_mods_dir(name)
                mods_dir.mkdir(parents=True, exist_ok=True)

                # Ensure profile exists
                profile_path = self.get_profile_path(name)
                if not profile_path.exists():
                    # Profile creation would be handled by ProfileManager
                    pass

    def normalize_path(self, path_str: str) -> str:
        """
        Normalize a path string to use forward slashes.

        Args:
            path_str: Path string to normalize

        Returns:
            Normalized path string
        """
        return PathUtils.normalize(path_str)

    def is_external_mod(self, game_name: str, mod_path: str) -> bool:
        """
        Check if a mod is external (not in the game's mods directory).

        Args:
            game_name: Name of the game
            mod_path: Path to the mod

        Returns:
            True if mod is external
        """
        mod_path_obj = Path(mod_path)
        mods_dir = self.get_mods_dir(game_name)

        try:
            mod_path_obj.relative_to(mods_dir)
            return False  # It's internal
        except ValueError:
            return True  # It's external

    def get_relative_mod_path(self, game_name: str, mod_path: str) -> str:
        """
        Get the relative path for a mod if it's internal.

        Args:
            game_name: Name of the game
            mod_path: Absolute path to the mod

        Returns:
            Relative path string or absolute if external
        """
        mod_path_obj = Path(mod_path)
        mods_dir = self.get_mods_dir(game_name)

        try:
            relative = mod_path_obj.relative_to(mods_dir)
            mods_dir_name = self.game_registry.get_game_mods_dir(game_name)
            return f"{mods_dir_name}/{relative}".replace("\\", "/")
        except ValueError:
            # External mod, return absolute path
            return self.normalize_path(str(mod_path_obj.resolve()))

    def resolve_mod_path(self, game_name: str, path_str: str) -> Path:
        """
        Resolve a mod path string to an absolute Path object.

        Args:
            game_name: Name of the game
            path_str: Path string (relative or absolute)

        Returns:
            Absolute Path object
        """
        path_obj = Path(path_str)

        if path_obj.is_absolute():
            return path_obj

        # Try relative to config root
        if "/" in path_str or "\\" in path_str:
            # It's a relative path with directory
            return self.config_root / path_str

        # Simple filename, assume in mods dir
        return self.get_mods_dir(game_name) / path_str

    def _get_active_profile(self, game_name: str) -> dict[str, Any] | None:
        """
        Get the active profile for a game.

        Args:
            game_name: Name of the game

        Returns:
            Active profile dictionary or None
        """
        profiles = self.settings_manager.get("profiles", {})
        active_profiles = self.settings_manager.get("active_profiles", {})

        active_id = active_profiles.get(game_name, "default")
        game_profiles = profiles.get(game_name, [])

        for profile in game_profiles:
            if profile.get("id") == active_id:
                return profile

        return None

    def refresh_config_root(self) -> None:
        """Refresh the config root from ME3 info if available."""
        if self.me3_info:
            self.me3_info.refresh_info()
            dynamic_profile_dir = self.me3_info.get_profile_directory()
            if dynamic_profile_dir:
                self._config_root = Path(dynamic_profile_dir)
