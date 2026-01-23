"""
Path management for ME3 Manager.
Handles all path resolution, custom paths, and directory management.
"""

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
        from me3_manager.core.paths.profile_paths import get_me3_profiles_root

        # Try to get dynamic config root from ME3
        if self.me3_info:
            dynamic_profile_dir = self.me3_info.get_profile_directory()
            if dynamic_profile_dir:
                self._config_root = Path(dynamic_profile_dir)
                return

        # Use shared platform-specific path resolution
        self._config_root = get_me3_profiles_root()

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

    def _find_native_entry(
        self, natives: list[dict], search_path: str, mods_root: Path
    ) -> dict | None:
        """Helper to find a native entry by path with robust matching."""
        search_path_lower = search_path.lower()
        search_path_obj_str = str(Path(search_path).resolve()).lower()

        for native in natives:
            if not isinstance(native, dict) or not native.get("path"):
                continue

            native_path = self.normalize_path(native["path"])

            # 1. Direct match
            if native_path.lower() == search_path_lower:
                return native

            # 2. Resolved match
            try:
                p_native = Path(native_path)
                if p_native.is_absolute():
                    res_native = p_native.resolve()
                    if str(res_native).lower() == search_path_obj_str:
                        return native
                else:
                    # Try relative to mods_root
                    res_native = (mods_root / native_path).resolve()
                    if str(res_native).lower() == search_path_obj_str:
                        return native

                    # Try relative to mods_root.parent (standard for default profiles)
                    # This handles paths like "game-mods/mod.dll" where mods_root ends in "game-mods"
                    try:
                        res_native_parent = (mods_root.parent / native_path).resolve()
                        if str(res_native_parent).lower() == search_path_obj_str:
                            return native
                    except Exception:
                        pass
            except Exception:
                continue
        return None

    def get_mod_config_paths(self, game_name: str, mod_path_str: str) -> list[Path]:
        """Get all config paths for a mod."""
        mod_key = mod_path_str.replace("\\", "/").lower()

        # Check legacy custom paths
        custom_paths = self.settings_manager.get("custom_config_paths", {}).get(
            game_name, {}
        )
        if custom_path := custom_paths.get(mod_key):
            return [Path(custom_path)]

        # Default convention
        mod_path = Path(mod_path_str)
        default_path = mod_path.parent / mod_path.stem / "config.ini"
        mods_dir = self.get_mods_dir(game_name)
        search_path = self.normalize_path(mod_path_str)

        # Check active profile override
        try:
            profile_path = self.get_profile_path(game_name)
            if profile_path.exists():
                from me3_manager.core.profiles.profile_manager import ProfileManager

                profile_data = ProfileManager.read_profile(profile_path)

                if native := self._find_native_entry(
                    profile_data.get("natives", []), search_path, mods_dir
                ):
                    if cfg_val := native.get("config"):
                        paths = self._resolve_config_paths(cfg_val, mods_dir)
                        if paths:
                            return paths
        except Exception:
            pass

        # Fallback: Search for .me3 files in mods directory and config_root that contain this mod
        try:
            from me3_manager.core.profiles.profile_manager import ProfileManager

            search_dirs = [mods_dir, self.config_root]
            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue
                for me3_file in search_dir.rglob("*.me3"):
                    try:
                        profile_data = ProfileManager.read_profile(me3_file)
                        if native := self._find_native_entry(
                            profile_data.get("natives", []), search_path, mods_dir
                        ):
                            if cfg_val := native.get("config"):
                                paths = self._resolve_config_paths(cfg_val, mods_dir)
                                if paths:
                                    return paths
                    except Exception:
                        continue
        except Exception:
            pass

        return [default_path]

    def _resolve_config_paths(self, cfg_val, mods_dir: Path) -> list[Path]:
        """Resolve config value (str or list) to absolute paths."""
        paths = []
        raw_list = cfg_val if isinstance(cfg_val, list) else [cfg_val]
        for r in raw_list:
            if not r:
                continue
            p = Path(r)
            final_p = p if p.is_absolute() else mods_dir / p
            paths.append(final_p)
        return paths

    def get_mod_config_path(self, game_name: str, mod_path_str: str) -> Path:
        """Get the primary config path for a mod (compatibility wrapper)."""
        paths = self.get_mod_config_paths(game_name, mod_path_str)
        return paths[0]

    def set_mod_config_path(
        self, game_name: str, mod_path_str: str, config_path: str
    ) -> None:
        """Set a custom config path for a mod."""
        from me3_manager.core.profiles.profile_manager import ProfileManager

        try:
            profile_path = self.get_profile_path(game_name)
            # Ensure profile directory exists
            if not profile_path.parent.exists():
                profile_path.parent.mkdir(parents=True, exist_ok=True)

            # Read or initialize profile
            if profile_path.exists():
                profile_data = ProfileManager.read_profile(profile_path)
            else:
                profile_data = {"profileVersion": "v1", "natives": []}

            natives = profile_data.setdefault("natives", [])
            mods_dir = self.get_mods_dir(game_name)
            search_path = self.normalize_path(mod_path_str)

            # Relativize config path if possible
            norm_config = self.normalize_path(config_path)
            try:
                mods_dir_resolved = mods_dir.resolve()
                config_obj = Path(config_path).resolve()
                if config_obj.is_relative_to(mods_dir_resolved):
                    norm_config = self.normalize_path(
                        str(config_obj.relative_to(mods_dir_resolved))
                    )
            except Exception:
                pass

            # Find and update or append
            native = self._find_native_entry(natives, search_path, mods_dir)
            if native:
                current_config = native.get("config")
                if isinstance(current_config, list):
                    # It's a list, we must preserve it and append if new
                    # Normalize existing list to check
                    # We don't want to change existing entries unless necessary, so just check existence
                    existing_normalized = [
                        self.normalize_path(str(c)) for c in current_config if c
                    ]
                    if norm_config not in existing_normalized:
                        current_config.append(norm_config)
                        # We modifed the list in place, but ensure it's set back just in case
                        native["config"] = current_config
                    # If it IS in the list, do nothing - we just "selected" it effectively
                else:
                    # Not a list, simple overwrite
                    native["config"] = norm_config
            else:
                natives.append({"path": search_path, "config": norm_config})

            ProfileManager.write_profile(profile_path, profile_data, game_name)

        except Exception:
            # Fallback to legacy settings only if profile write fails completely
            try:
                mod_key = mod_path_str.replace("\\", "/").lower()
                custom_paths = self.settings_manager.get("custom_config_paths", {})
                custom_paths.setdefault(game_name, {})[mod_key] = config_path
                self.settings_manager.set("custom_config_paths", custom_paths)
            except Exception:
                pass

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
