"""
Configuration facade for backward compatibility.
Provides the same interface as the old ConfigManager while delegating to new components.
"""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher

from me3_manager.core.me3_info import ME3InfoManager
from me3_manager.core.mod_manager import ImprovedModManager
from me3_manager.core.paths import FileWatcher, PathManager
from me3_manager.core.profiles.profile_manager import ProfileManager
from me3_manager.core.settings import GameRegistry, SettingsManager, UISettings
from me3_manager.domain.models import GameConfig, Profile

log = logging.getLogger(__name__)


class ConfigFacade:
    """
    Facade that maintains backward compatibility with the old ConfigManager interface.
    Delegates to the new modular components.
    """

    def __init__(self):
        """Initialize the facade with all necessary components."""
        # Initialize ME3 info manager
        self.me3_info_manager = ME3InfoManager()
        self.me3_info = self.me3_info_manager
        # Determine settings file path
        settings_file = self._get_initial_settings_path()
        # Initialize core components
        self.settings_manager = SettingsManager(settings_file)
        self.ui_settings = UISettings(self.settings_manager)
        self.game_registry = GameRegistry(self.settings_manager)
        self.path_manager = PathManager(
            self.settings_manager, self.game_registry, self.me3_info_manager
        )
        self.file_watcher_handler = FileWatcher()
        # New mod manager for enable/disable and queries
        self.mod_manager = ImprovedModManager(self)
        # Legacy compatibility attributes
        self.config_root = self.path_manager.config_root
        self.settings_file = settings_file
        self.file_watcher = QFileSystemWatcher()
        self._sync_legacy_attributes()
        self.path_manager.ensure_directories()
        self.setup_file_watcher()

    def _get_initial_settings_path(self) -> Path:
        """Get the initial settings file path."""
        # Try to get from ME3 info
        if self.me3_info_manager and self.me3_info_manager.is_me3_installed():
            profile_dir = self.me3_info_manager.get_profile_directory()
            if profile_dir:
                return Path(profile_dir).parent / "manager_settings.json"
        if sys.platform == "win32":
            localappdata = os.environ.get("LOCALAPPDATA")
            if localappdata:
                config_root = (
                    Path(localappdata) / "garyttierney" / "me3" / "config" / "profiles"
                )
            else:
                config_root = (
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
                config_root = Path(xdg_config) / "me3" / "profiles"
            else:
                config_root = Path.home() / ".config" / "me3" / "profiles"
        return config_root.parent / "manager_settings.json"

    def _sync_legacy_attributes(self):
        """Sync legacy attributes for backward compatibility."""
        # Keep legacy fields for code that still reads attributes directly
        self.games = self.game_registry.get_all_games()
        self.game_order = self.game_registry.get_game_order()
        self.game_exe_paths = self.settings_manager.get("game_exe_paths", {})
        self.tracked_external_mods = self.settings_manager.get(
            "tracked_external_mods", {}
        )
        self.ui_settings_dict = self.ui_settings.get_all_ui_settings()
        self.custom_config_paths = self.settings_manager.get("custom_config_paths", {})
        self.me3_config_paths = self.settings_manager.get("me3_config_paths", {})
        self.profiles = self.settings_manager.get("profiles", {})
        self.active_profiles = self.settings_manager.get("active_profiles", {})
        # Legacy custom path attributes (these are now handled differently)
        self.custom_profile_paths = {}
        self.custom_mods_paths = {}
        self.stored_custom_profile_paths = {}
        self.stored_custom_mods_paths = {}

    # Clean accessors (preferred over legacy attributes)

    def get_all_games(self) -> dict[str, dict[str, str]]:
        """Get all registered games (live view from registry)."""
        return self.game_registry.get_all_games()

    def has_game(self, game_name: str) -> bool:
        """Check if a game exists in the registry."""
        return self.game_registry.get_game(game_name) is not None

    def get_game_info(self, game_name: str) -> dict[str, str] | None:
        """Get a single game's configuration."""
        return self.game_registry.get_game(game_name)

    def get_game_mods_dir_name(self, game_name: str) -> str | None:
        """Get the mods directory name for a game (e.g., 'eldenring-mods')."""
        return self.game_registry.get_game_mods_dir(game_name)

    # Typed convenience methods (non-breaking additions)

    def get_game_configs(self) -> list[GameConfig]:
        games = self.game_registry.get_all_games()
        return [
            GameConfig(
                name=name,
                mods_dir=cfg.get("mods_dir", ""),
                profile=cfg.get("profile", ""),
                cli_id=cfg.get("cli_id", ""),
                executable=cfg.get("executable", ""),
            )
            for name, cfg in games.items()
        ]

    def get_profiles_for_game_typed(self, game_name: str) -> list[Profile]:
        profiles = self.settings_manager.get("profiles", {}).get(game_name, [])
        result: list[Profile] = []
        for p in profiles:
            pid = p.get("id", "")
            name = p.get("name", "")
            profile_path = p.get("profile_path", "")
            mods_path = p.get("mods_path", "")
            result.append(
                Profile(
                    id=pid, name=name, profile_path=profile_path, mods_path=mods_path
                )
            )
        return result

    # Settings Management (delegated)

    def _load_settings(self) -> dict:
        """Legacy method for loading settings."""
        return self.settings_manager.load_settings()

    def _save_settings(self):
        """Legacy method for saving settings."""
        # Only persist fields that are intended to be user-editable and not derived
        payload = {
            "games": self.game_registry.get_all_games(),
            "game_order": self.game_registry.get_game_order(),
            "game_exe_paths": self.game_exe_paths,
            "tracked_external_mods": self.tracked_external_mods,
            "profiles": self.profiles,
            "active_profiles": self.active_profiles,
            "custom_config_paths": self.custom_config_paths,
            "me3_config_paths": self.me3_config_paths,
        }
        self.settings_manager.update(payload)
        # update() auto-saves; explicit save ensures durability in legacy paths
        self.settings_manager.save_settings()

    def add_game(
        self, name: str, mods_dir: str, profile: str, cli_id: str, executable: str
    ):
        """Add a new game configuration."""
        success = self.game_registry.add_game(
            name, mods_dir, profile, cli_id, executable
        )
        if success:
            self._sync_legacy_attributes()
            self.path_manager.ensure_directories(name)
            self.setup_file_watcher()
            self._save_settings()
        return success

    def remove_game(self, name: str):
        """Remove a game configuration."""
        success = self.game_registry.remove_game(name)
        if success:
            self._sync_legacy_attributes()
            self.setup_file_watcher()
            self._save_settings()
        return success

    def update_game(self, name: str, **kwargs):
        """Update game configuration."""
        success = self.game_registry.update_game(name, **kwargs)
        if success:
            self._sync_legacy_attributes()
            self.path_manager.ensure_directories(name)
            self._save_settings()
        return success

    def get_game_cli_id(self, game_name: str) -> str | None:
        """Get CLI ID for a game."""
        return self.game_registry.get_game_cli_id(game_name)

    def get_game_executable_name(self, game_name: str) -> str | None:
        """Get executable name for a game."""
        return self.game_registry.get_game_executable_name(game_name)

    def get_game_exe_path(self, game_name: str) -> str | None:
        """Get custom executable path for a game."""
        return self.game_registry.get_game_exe_path(game_name)

    def set_game_exe_path(self, game_name: str, path: str | None):
        """Set custom executable path for a game."""
        self.game_registry.set_game_exe_path(game_name, path)
        self._sync_legacy_attributes()
        self._save_settings()

    def get_game_order(self) -> list[str]:
        """Get game order."""
        return self.game_registry.get_game_order()

    def set_game_order(self, new_order: list[str]):
        """Set game order."""
        success = self.game_registry.set_game_order(new_order)
        if success:
            self._sync_legacy_attributes()
            self._save_settings()
        return success

    def get_mods_per_page(self) -> int:
        """Get mods per page setting."""
        return self.ui_settings.get_mods_per_page()

    def set_mods_per_page(self, value: int):
        """Set mods per page setting."""
        self.ui_settings.set_mods_per_page(value)

    def get_check_for_updates(self) -> bool:
        """Get check for updates setting."""
        return self.ui_settings.get_check_for_updates()

    def set_check_for_updates(self, enabled: bool):
        """Set check for updates setting."""
        self.ui_settings.set_check_for_updates(enabled)

    def get_auto_launch_steam(self) -> bool:
        """Get auto launch Steam setting."""
        return self.ui_settings.get_auto_launch_steam()

    def set_auto_launch_steam(self, enabled: bool):
        """Set auto launch Steam setting."""
        self.ui_settings.set_auto_launch_steam(enabled)

    # Path Management (delegated to PathManager)
    def get_mods_dir(self, game_name: str) -> Path:
        """Get mods directory for a game."""
        return self.path_manager.get_mods_dir(game_name)

    def get_profile_path(self, game_name: str) -> Path:
        """Get profile path for a game."""
        return self.path_manager.get_profile_path(game_name)

    def get_mod_config_path(self, game_name: str, mod_path_str: str) -> Path:
        """Get config path for a mod."""
        return self.path_manager.get_mod_config_path(game_name, mod_path_str)

    def set_mod_config_path(self, game_name: str, mod_path_str: str, config_path: str):
        """Set custom config path for a mod."""
        self.path_manager.set_mod_config_path(game_name, mod_path_str, config_path)
        self._sync_legacy_attributes()

    def get_me3_config_path(self, game_name: str) -> str | None:
        """Get ME3 config path for a game."""
        path = self.path_manager.get_me3_config_path(game_name)
        return str(path) if path else None

    def set_me3_config_path(self, game_name: str, config_path: str):
        """Set ME3 config path for a game."""
        self.path_manager.set_me3_config_path(game_name, config_path)
        self._sync_legacy_attributes()

    def ensure_directories(self):
        """Ensure all necessary directories exist."""
        self.path_manager.ensure_directories()

    # File Watcher (delegated to FileWatcher)
    def setup_file_watcher(self):
        """Setup file watcher for all games."""
        self.file_watcher_handler.setup_global(
            self.path_manager, self.settings_manager, self.game_registry
        )
        current_dirs = self.file_watcher.directories()
        if current_dirs:
            self.file_watcher.removePaths(current_dirs)
        new_dirs = self.file_watcher_handler.get_watched_directories()
        if new_dirs:
            self.file_watcher.addPaths(new_dirs)

    # Profile Management
    def get_profiles_for_game(self, game_name: str) -> list[dict]:
        """Get all profiles for a game."""
        profiles = self.settings_manager.get("profiles", {})
        return profiles.get(game_name, [])

    def get_active_profile(self, game_name: str) -> dict | None:
        """Get active profile for a game."""
        profiles = self.get_profiles_for_game(game_name)
        if not profiles:
            default_mods_path = self.path_manager.get_mods_dir(game_name)
            default_profile_file_path = self.path_manager.get_profile_path(game_name)
            new_profile = {
                "id": "default",
                "name": "Default",
                "profile_path": str(default_profile_file_path),
                "mods_path": str(default_mods_path),
            }
            default_mods_path.mkdir(parents=True, exist_ok=True)
            if game_name not in self.profiles:
                self.profiles[game_name] = []
            self.profiles[game_name].append(new_profile)
            self.active_profiles[game_name] = "default"
            self._save_settings()
            return new_profile

        active_id = self.active_profiles.get(game_name, "default")
        for profile in profiles:
            if profile.get("id") == active_id:
                return profile
        if profiles:
            return profiles[0]
        return None

    def set_active_profile(self, game_name: str, profile_id: str):
        """Set active profile for a game."""
        self.active_profiles[game_name] = profile_id
        self._save_settings()
        self.setup_file_watcher()

    def add_profile(
        self, game_name: str, name: str, mods_path: str, make_active: bool = False
    ) -> str | None:
        """Add a new profile for a game."""
        import uuid

        profile_id = str(uuid.uuid4())
        mods_dir = Path(mods_path)
        mods_dir.mkdir(parents=True, exist_ok=True)
        # Create profile file
        safe_filename = "".join(
            c for c in name if c.isalnum() or c in (" ", "_")
        ).rstrip()
        profile_file_path = mods_dir / f"{safe_filename.replace(' ', '_')}.me3"
        profile_file_path.touch()
        # Add to profiles
        if game_name not in self.profiles:
            self.profiles[game_name] = []
        new_profile = {
            "id": profile_id,
            "name": name,
            "profile_path": str(profile_file_path),
            "mods_path": str(mods_dir),
        }
        self.profiles[game_name].append(new_profile)
        if make_active:
            self.set_active_profile(game_name, profile_id)
        else:
            self._save_settings()
        return profile_id

    def delete_profile(self, game_name: str, profile_id: str):
        """Delete a profile."""
        if profile_id == "default":
            return
        # Remove from profiles
        if game_name in self.profiles:
            self.profiles[game_name] = [
                p for p in self.profiles[game_name] if p.get("id") != profile_id
            ]
            # Reset active if needed
        if self.active_profiles.get(game_name) == profile_id:
            self.active_profiles[game_name] = "default"
        self._save_settings()

    def update_profile(self, game_name: str, profile_id: str, new_name: str):
        """Update a profile's name."""
        if game_name in self.profiles:
            for profile in self.profiles[game_name]:
                if profile.get("id") == profile_id:
                    profile["name"] = new_name
                    self._save_settings()
                    return True
        return False

    def _get_default_games(self) -> dict:
        """Get default game configurations."""
        return self.game_registry.DEFAULT_GAMES

    def track_external_mod(self, game_name: str, mod_path: str):
        """Track an external mod."""
        normalized_path = mod_path.replace("\\", "/")
        active_profile_id = self.active_profiles.get(game_name, "default")

        if game_name not in self.tracked_external_mods:
            self.tracked_external_mods[game_name] = {}

        if not isinstance(self.tracked_external_mods[game_name], dict):
            self.tracked_external_mods[game_name] = {}

        if active_profile_id not in self.tracked_external_mods[game_name]:
            self.tracked_external_mods[game_name][active_profile_id] = []

        if (
            normalized_path
            not in self.tracked_external_mods[game_name][active_profile_id]
        ):
            self.tracked_external_mods[game_name][active_profile_id].append(
                normalized_path
            )
            self._save_settings()

    def untrack_external_mod(self, game_name: str, mod_path: str):
        """Untrack an external mod."""
        normalized_path = mod_path.replace("\\", "/")
        active_profile_id = self.active_profiles.get(game_name, "default")

        if game_name in self.tracked_external_mods and isinstance(
            self.tracked_external_mods[game_name], dict
        ):
            profile_mods = self.tracked_external_mods[game_name].get(
                active_profile_id, []
            )
            if normalized_path in profile_mods:
                profile_mods.remove(normalized_path)
                if not profile_mods:
                    del self.tracked_external_mods[game_name][active_profile_id]
                self._save_settings()

    def is_me3_installed(self) -> bool:
        """Check if ME3 is installed."""
        return self.me3_info_manager.is_me3_installed()

    def get_me3_installation_status(self) -> int:
        """Get ME3 installation status as a Status code."""
        return self.me3_info_manager.get_me3_installation_status()

    def get_me3_version(self) -> str | None:
        """Get ME3 version."""
        return self.me3_info_manager.get_version()

    def get_steam_path(self) -> Path | None:
        """Get Steam path."""
        return self.me3_info_manager.get_steam_path()

    def get_logs_directory(self) -> Path | None:
        """Get ME3 logs directory."""
        return self.me3_info_manager.get_logs_directory()

    def refresh_me3_info(self):
        """Refresh ME3 info."""
        self.me3_info_manager.refresh_info()
        self.path_manager.refresh_config_root()
        self.config_root = self.path_manager.config_root

    def _parse_toml_config(self, config_path):
        """Parse TOML config file (needed by mod_manager)."""
        return ProfileManager.read_profile(Path(config_path))

    def _write_toml_config(self, config_path, config_data):
        """Write TOML config file using tomlkit for proper formatting."""
        ProfileManager.write_profile(Path(config_path), config_data)

    def validate_and_prune_profiles(self):
        """Validate and prune profiles (needed by main_window)."""
        # This would be handled by ProfileManager in full refactor
        # For now, just pass through
        pass

    def check_and_reformat_profile(self, profile_path):
        """Check and reformat profile to use new array of tables syntax."""
        ProfileManager.ensure_format(Path(profile_path))

    def sync_profile_with_filesystem(self, game_name):
        """Sync profile with filesystem (needed by main_window)."""
        # This would be handled by ProfileManager in full refactor
        # For now, just pass through
        pass

    def launch_steam_silently(self):
        """Launch Steam silently (needed by main_window)."""
        # This would be handled by a separate launcher module
        # For now, return False
        return False

    def get_mods_info(self, game_name, skip_sync=False):
        """Get mods info for a game (needed by various UI components)."""
        # This would be handled by ModManager in full refactor
        # For now, return empty dict
        # The skip_sync parameter is accepted for compatibility but not used
        return {}

    def set_mod_enabled(self, game_name, mod_path, enabled):
        """Set mod enabled status (needed by UI components)."""
        try:
            success, _ = self.mod_manager.set_mod_enabled(game_name, mod_path, enabled)
            return success
        except Exception:
            return False

    def delete_mod(self, game_name, mod_path):
        """Delete a mod (needed by UI components)."""
        # This would be handled by ModManager in full refactor
        pass

    def set_regulation_active(self, game_name, mod_name):
        """Set regulation active (needed by UI components)."""
        # This would be handled by ModManager in full refactor
        pass

    def add_folder_mod(self, game_name: str, mod_name: str, mod_path: str):
        """
        Add a folder mod to the configuration.
        This is called when creating new folder/package mods.

        Args:
            game_name: Name of the game
            mod_name: Name of the mod
            mod_path: Path to the mod folder
        """
        # For now, this is a no-op since the mod_manager handles this
        # when set_mod_enabled is called. The folder mod is automatically
        # detected and added to the profile when enabled.
        pass

    def get_profile_content(self, game_name: str) -> str:
        """Get the raw content of a game's profile file (needed by profile editor)."""
        profile_path = self.get_profile_path(game_name)
        if not profile_path.exists():
            # Create default profile if it doesn't exist
            config_data = {
                "profileVersion": "v1",
                "natives": [],
                "packages": [],
                "supports": [],
            }
            self._write_toml_config(profile_path, config_data)

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            log.error("Error reading profile %s: %s", profile_path, e)
            return ""

    def save_profile_content(self, game_name: str, content: str):
        """Save raw content to a game's profile file (needed by profile editor)."""
        profile_path = self.get_profile_path(game_name)
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            log.error("Error writing to profile %s: %s", profile_path, e)
            raise

    def get_me3_game_settings(self, game_name: str) -> dict:
        """Get ME3 game-specific settings from the ME3 config file."""
        try:
            config_path = self.get_me3_config_path(game_name)
            if not config_path:
                return {}

            config_path_obj = Path(config_path)
            if not config_path_obj.exists():
                return {}

            import tomllib

            with open(config_path_obj, "rb") as f:
                config_data = tomllib.load(f)

            # Determine slug key used in TOML
            slug = self._get_game_slug(game_name)

            game_table = config_data.get("game", {})

            # Prefer slug key (e.g., eldenring) then fall back to display name
            if isinstance(game_table, dict):
                if slug in game_table:
                    return game_table.get(slug, {}) or {}
                if game_name in game_table:
                    return game_table.get(game_name, {}) or {}

            return {}

        except Exception as e:
            log.error("Error reading ME3 game settings for %s: %s", game_name, e)
            return {}

    def set_me3_game_settings(self, game_name: str, settings: dict) -> bool:
        """Set ME3 game-specific settings in the ME3 config file."""
        try:
            config_path = self.get_me3_config_path(game_name)
            if not config_path:
                log.debug("No ME3 config path available for %s", game_name)
                return False

            config_path_obj = Path(config_path)

            # Load existing config or create empty one
            config_data = {}
            if config_path_obj.exists():
                try:
                    import tomllib

                    with open(config_path_obj, "rb") as f:
                        config_data = tomllib.load(f)
                except Exception as e:
                    log.warning("Could not parse existing ME3 config: %s", e)
                    config_data = {}

            # Ensure game section exists
            game_table = config_data.get("game")
            if not isinstance(game_table, dict):
                game_table = {}
                config_data["game"] = game_table

            slug = self._get_game_slug(game_name)

            # Migrate legacy key if present (e.g., "Elden Ring" -> "eldenring")
            if game_name in game_table and slug not in game_table:
                game_table[slug] = game_table.pop(game_name) or {}

            if slug not in game_table:
                game_table[slug] = {}

            # Update game-specific settings on slug key
            for key, value in settings.items():
                if value is None:
                    game_table[slug].pop(key, None)
                else:
                    game_table[slug][key] = value

            # Also remove any lingering legacy key section if empty
            if game_name in game_table and not game_table.get(game_name):
                game_table.pop(game_name, None)

            # Clean up empty sections
            if not game_table.get(slug):
                game_table.pop(slug, None)
            if not game_table:
                config_data.pop("game", None)

            # Save back to file
            import tomli_w

            with open(config_path_obj, "wb") as f:
                tomli_w.dump(config_data, f)

            return True

        except Exception as e:
            log.error("Error saving ME3 game settings for %s: %s", game_name, e)
            return False

    def _get_game_slug(self, game_name: str) -> str:
        """Derive canonical game slug used in TOML sections.

        Prefer deriving from mods_dir (e.g., eldenring-mods -> eldenring). If not
        available, use the game's cli_id. As a final fallback, lowercase and
        strip spaces from the display name.
        """
        try:
            game_info = self.game_registry.get_game(game_name) or {}
            mods_dir = game_info.get("mods_dir")
            if isinstance(mods_dir, str) and mods_dir.endswith("-mods"):
                return mods_dir[:-5].lower()

            cli_id = game_info.get("cli_id")
            if isinstance(cli_id, str) and cli_id:
                # Some existing cli_id values may contain dashes like "elden-ring".
                # Normalize to remove non-alphanumerics for TOML section key.
                return "".join(ch for ch in cli_id.lower() if ch.isalnum())

            # Fallback: remove non-alphanumerics and lowercase from display name
            return "".join(ch for ch in game_name.lower() if ch.isalnum())
        except Exception:
            return "".join(ch for ch in game_name.lower() if ch.isalnum())
