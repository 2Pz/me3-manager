import subprocess
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
from PyQt6.QtCore import QFileSystemWatcher
from utils.resource_path import resource_path
import tomllib
from core.me3_info import ME3InfoManager

class ConfigManager:
    """Manages ME3 configuration files and mod directories"""
    
    def __init__(self):
        # Initialize ME3 info manager
        self.me3_info = ME3InfoManager()
        
        # Try to get dynamic config root from ME3, fallback to hardcoded path
        dynamic_profile_dir = self.me3_info.get_profile_directory()
        if dynamic_profile_dir:
            self.config_root = dynamic_profile_dir
        else:
            # Fallback to hardcoded path if ME3 is not installed or info command fails
            if sys.platform == "win32":
                self.config_root = Path(os.path.expandvars(r"%LocalAppData%\garyttierney\me3\config\profiles"))
            else:
                self.config_root = Path.home() / ".config" / "garyttierney" / "me3" / "profiles"
        
        self.settings_file = self.config_root.parent / "manager_settings.json"
        
        self.file_watcher = QFileSystemWatcher()
        
        # Load games from JSON configuration
        self.games = self._load_games_config()
        
        settings = self._load_settings()
        self.game_exe_paths = settings.get('game_exe_paths', {})
        self.tracked_external_mods = settings.get('tracked_external_mods', {})
        self.ui_settings = settings.get('ui_settings', {})
        self.custom_config_paths = settings.get('custom_config_paths', {})

        # PROFILE MANAGEMENT SYSTEM
        self.profiles = settings.get('profiles', {})
        self.active_profiles = settings.get('active_profiles', {})

        self.validate_and_prune_profiles()
        self._migrate_old_custom_paths()
        self._ensure_default_profiles()

        self._migrate_external_mods_to_profile_system()
        
        # Custom profile and mods folder paths
        self.custom_profile_paths = settings.get('custom_profile_paths', {})
        self.custom_mods_paths = settings.get('custom_mods_paths', {})
        
        # Stored custom paths (preserved when switching to default)
        self.stored_custom_profile_paths = settings.get('stored_custom_profile_paths', {})
        self.stored_custom_mods_paths = settings.get('stored_custom_mods_paths', {})
        
        # Use default order from games config if not set in settings
        default_order = self._get_default_game_order()
        saved_order = settings.get('game_order', default_order)
        
        # Merge saved order with new games from JSON config
        self.game_order = self._merge_game_order(saved_order, list(self.games.keys()))
        
        # Save the updated order if it was changed during merge
        if self.game_order != saved_order:
            self._save_settings()
        
        self.ensure_directories()
        self.file_watcher = QFileSystemWatcher()
        self.setup_file_watcher()

    def get_check_for_updates(self) -> bool:
        """Get whether to check for updates on startup"""
        return self.ui_settings.get('check_for_updates', True)  # Default to True

    def set_check_for_updates(self, enabled: bool):
        """Set whether to check for updates on startup"""
        self.ui_settings['check_for_updates'] = enabled
        self._save_settings()

    def _migrate_external_mods_to_profile_system(self):
        """
        One-time migration to associate existing global external mods with the 'default' profile.
        """
        settings = self._load_settings()
        current_tracked_mods = settings.get('tracked_external_mods', {})
        
        if not current_tracked_mods:
            return # Nothing to migrate

        # Check if the first value is a list (old format) instead of a dict (new format)
        first_value = next(iter(current_tracked_mods.values()), None)
        if isinstance(first_value, dict):
            return # Already in the new format

        print("Migrating tracked external mods to the new profile-based system...")
        new_tracked_mods = {}
        for game_name, mods_list in current_tracked_mods.items():
            if isinstance(mods_list, list):
                new_tracked_mods[game_name] = {
                    'default': mods_list
                }
        
        self.tracked_external_mods = new_tracked_mods
        self._save_settings()
        print("External mod migration successful.")

    def _migrate_old_custom_paths(self):
        """Migrates old custom_profile_paths and custom_mods_paths to the new profiles system."""
        settings = self._load_settings()
        # We only need to check for the old mods path, as it's the key piece of info.
        old_custom_mods = settings.get('custom_mods_paths', {})

        if not old_custom_mods:
            return # No old settings to migrate

        print("Migrating old custom path settings to new profile system...")
        migrated = False
        
        for game_name, mods_path in old_custom_mods.items():
            if not mods_path:
                continue
                
            if game_name not in self.profiles:
                self.profiles[game_name] = []
            
            # This call now perfectly matches the function definition from Step 1.
            self.add_profile(
                game_name=game_name,
                name="Custom (Legacy)",
                mods_path=mods_path,
                make_active=True
            )
            migrated = True

        if migrated:
            # Clean up old keys after migration
            all_settings = self._load_settings()
            all_settings.pop('custom_profile_paths', None)
            all_settings.pop('custom_mods_paths', None)
            all_settings.pop('stored_custom_profile_paths', None)
            all_settings.pop('stored_custom_mods_paths', None)
            all_settings['profiles'] = self.profiles
            all_settings['active_profiles'] = self.active_profiles
            
            try:
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(all_settings, f, indent=4)
                print("Migration successful.")
            except IOError as e:
                print(f"Error saving migrated settings: {e}")

    def _ensure_default_profiles(self):
        """Ensures every game has a default profile entry and an active profile set."""
        for game_name in self.games.keys():
            if game_name not in self.profiles:
                self.profiles[game_name] = []
            
            # Check if default profile exists
            if not any(p['id'] == 'default' for p in self.profiles[game_name]):
                self.profiles[game_name].insert(0, {
                    "id": "default",
                    "name": "Default",
                    "profile_path": None,
                    "mods_path": None
                })
            
            # Ensure an active profile is set
            if game_name not in self.active_profiles:
                self.active_profiles[game_name] = 'default'

    def _load_settings(self) -> dict:
        """Loads custom settings from the JSON file."""
        if not self.settings_file.exists():
            return {}
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {} # Return empty dict on error

    def _save_settings(self):
        """Saves all settings to the JSON file."""
        try:
            all_settings = {
                'game_exe_paths': self.game_exe_paths,
                'game_order': getattr(self, 'game_order', list(self.games.keys())),
                'ui_settings': self.ui_settings,
                'tracked_external_mods': self.tracked_external_mods,
                'profiles': self.profiles,
                'active_profiles': self.active_profiles,
                'custom_config_paths': self.custom_config_paths, # Add this line
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(all_settings, f, indent=4)
        except IOError as e:
            print(f"Error saving settings: {e}")

    def validate_and_prune_profiles(self):
        """
        Removes profiles from settings if their associated 'mods_path' directory OR
        'profile_path' file no longer exists.
        """
        settings_changed = False
        # Iterate over a copy of the items to allow safe modification
        for game_name, profile_list in list(self.profiles.items()):
            original_count = len(profile_list)
            
            valid_profiles = []
            for p in profile_list:
                if p.get('id') == 'default':
                    valid_profiles.append(p)
                    continue

                # For custom profiles, both the mods directory and the profile file must exist.
                mods_path_ok = p.get('mods_path') and Path(p.get('mods_path')).is_dir()
                profile_file_ok = p.get('profile_path') and Path(p.get('profile_path')).is_file()
                
                if mods_path_ok and profile_file_ok:
                    valid_profiles.append(p)
            
            if len(valid_profiles) < original_count:
                removed_ids = set(p['id'] for p in profile_list) - set(p['id'] for p in valid_profiles)
                print(f"Pruning invalid profiles for {game_name}: {removed_ids}")
                
                self.profiles[game_name] = valid_profiles
                settings_changed = True
                
                active_profile_id = self.active_profiles.get(game_name)
                if active_profile_id in removed_ids:
                    self.active_profiles[game_name] = 'default'
                    print(f"Active profile for {game_name} was pruned. Resetting to 'default'.")

        if settings_changed:
            self._save_settings()

    def _load_games_config(self) -> dict:
        """Load games configuration from JSON file."""
        games_config_path = Path(resource_path("resources/games_config.json"))
        
        # Fallback to hardcoded games if JSON file doesn't exist
        fallback_games = {
            "Elden Ring": {
                "mods_dir": "eldenring-mods",
                "profile": "eldenring-default.me3",
                "cli_id": "elden-ring",
                "executable": "eldenring.exe"
            },
            "Nightreign": {
                "mods_dir": "nightreign-mods",
                "profile": "nightreign-default.me3",
                "cli_id": "nightreign",
                "executable": "nightreign.exe"
            },
            "Sekiro": {
                "mods_dir": "sekiro-mods",
                "profile": "sekiro-default.me3",
                "cli_id": "sekiro",
                "executable": "sekiro.exe"
            },
            "Armoredcore6": {
                "mods_dir": "armoredcore6-mods",
                "profile": "armoredcore6-default.me3",
                "cli_id": "armoredcore6",
                "executable": "armoredcore6.exe"
            }
        }
        
        try:
            if games_config_path.exists():
                with open(games_config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    return config_data.get('games', fallback_games)
            else:
                print(f"Games config file not found at {games_config_path}, using fallback")
                return fallback_games
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading games config: {e}, using fallback")
            return fallback_games

    def _get_default_game_order(self) -> list:
        """Get default game order from JSON config."""
        games_config_path = Path(resource_path("resources/games_config.json"))
        
        try:
            if games_config_path.exists():
                with open(games_config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    return config_data.get('default_order', list(self.games.keys()))
            else:
                return list(self.games.keys())
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading default game order: {e}")
            return list(self.games.keys())

    def _merge_game_order(self, saved_order: list, available_games: list) -> list:
        """Merge saved game order with new games from JSON config."""
        # Start with saved order, keeping only games that still exist
        merged_order = [game for game in saved_order if game in available_games]
        
        # Add any new games that aren't in the saved order
        for game in available_games:
            if game not in merged_order:
                merged_order.append(game)
        
        # Save the updated order if it changed
        if merged_order != saved_order:
            self.game_order = merged_order
            # We'll save this after initialization is complete
            
        return merged_order

    def get_game_exe_path(self, game_name: str) -> Optional[str]:
        """Gets the custom game executable path for a game."""
        return self.game_exe_paths.get(game_name)

    def set_game_exe_path(self, game_name: str, path: Optional[str]):
        """Sets or clears the custom game executable path and saves settings."""
        if path:
            self.game_exe_paths[game_name] = path
        else:
            # If path is None or empty, remove the key
            self.game_exe_paths.pop(game_name, None)
        self._save_settings()

    def get_game_cli_id(self, game_name: str) -> Optional[str]:
        """Gets the command-line ID for the game (e.g., 'elden-ring')."""
        return self.games.get(game_name, {}).get("cli_id")

    def get_game_executable_name(self, game_name: str) -> Optional[str]:
        """Gets the expected executable filename for the game (e.g., 'eldenring.exe')."""
        return self.games.get(game_name, {}).get("executable")

    def get_mods_per_page(self) -> int:
        """Gets the saved number of mods to display per page."""
        return self.ui_settings.get('mods_per_page', 5)

    def set_mods_per_page(self, value: int):
        """Sets the number of mods per page and saves the settings."""
        self.ui_settings['mods_per_page'] = value
        self._save_settings()

    def get_mod_config_path(self, game_name: str, mod_path_str: str) -> Path:
        """
        Gets the config path for a mod.
        Checks for a custom path first, then falls back to the default.
        Uses a standardized, case-insensitive key for reliability on all platforms.
        """
        # Create a canonical key: normalize slashes AND convert to lowercase.
        mod_key = mod_path_str.replace('\\', '/').lower()
        
        # Check for a saved custom path using the reliable key.
        custom_path = self.custom_config_paths.get(game_name, {}).get(mod_key)
        if custom_path:
            return Path(custom_path)
            
        # Fallback to default path convention if no custom path is found.
        mod_path = Path(mod_path_str)
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def set_mod_config_path(self, game_name: str, mod_path_str: str, config_path: str):
        """Saves a custom config path for a mod using the same standardized key."""
        # Use the EXACT same key generation logic as the getter for a perfect match.
        mod_key = mod_path_str.replace('\\', '/').lower()
        
        # Ensure the game's dictionary exists.
        self.custom_config_paths.setdefault(game_name, {})
        
        # Save the custom path using the canonical key.
        self.custom_config_paths[game_name][mod_key] = config_path
        self._save_settings()

    def track_external_mod(self, game_name: str, mod_path: str):
        """Adds an external mod to the tracking list for the ACTIVE profile."""
        normalized_path = mod_path.replace('\\', '/')
        active_profile_id = self.active_profiles.get(game_name, 'default')
        
        # Defensively ensure the structure is correct before trying to modify it.
        if game_name not in self.tracked_external_mods or not isinstance(self.tracked_external_mods[game_name], dict):
            # If the entry for this game is missing or is not a dictionary (i.e., it's the old list format),
            # we must overwrite it with the correct dictionary structure.
            self.tracked_external_mods[game_name] = {}

        game_profiles_mods = self.tracked_external_mods[game_name]
        profile_specific_mods = game_profiles_mods.setdefault(active_profile_id, [])
        
        if normalized_path not in profile_specific_mods:
            profile_specific_mods.append(normalized_path)
            self._save_settings()

    def untrack_external_mod(self, game_name: str, mod_path: str):
        """Removes an external mod from the tracking list for the ACTIVE profile."""
        normalized_path = mod_path.replace('\\', '/')
        active_profile_id = self.active_profiles.get(game_name, 'default')

        # Defensively check the structure before trying to modify it.
        if game_name in self.tracked_external_mods and isinstance(self.tracked_external_mods[game_name], dict):
            profile_specific_mods = self.tracked_external_mods[game_name].get(active_profile_id)
            if profile_specific_mods and normalized_path in profile_specific_mods:
                profile_specific_mods.remove(normalized_path)
                if not profile_specific_mods:
                    # Clean up empty list for this profile
                    del self.tracked_external_mods[game_name][active_profile_id]
                self._save_settings()

    def find_me3_executable(self) -> Optional[Path]:
        possible_locations = [
            self.config_root / "me3.exe",
            self.config_root.parent / "me3.exe",
            Path.cwd() / "me3.exe",
        ]
        for location in possible_locations:
            if location.exists():
                return location
        return None

    
    def ensure_directories(self):
        """Create necessary directories and validate profile formats on startup."""
        self.config_root.mkdir(parents=True, exist_ok=True)
        
        for game_info in self.games.values():
            mods_dir = self.config_root / game_info["mods_dir"]
            mods_dir.mkdir(exist_ok=True)
            
            profile_path = self.config_root / game_info["profile"]
            if not profile_path.exists():
                self.create_default_profile(profile_path)
            else:
                # On startup, check for old format and reformat if needed.
                self.check_and_reformat_profile(profile_path)

    def check_and_reformat_profile(self, profile_path: Path):
        """
        Checks if a profile uses the old [[section]] format and rewrites it
        to the new inline array format if necessary.
        """
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # A simple, reliable check for the old format. If found, re-writing is triggered.
            if '[[natives]]' in content or '[[packages]]' in content or '[[supports]]' in content:
                print(f"Old profile format detected in {profile_path.name}. Reformatting.")
                # This function already reads data (from old or new format)
                # and writes it back using the new standard format.
                self.validate_and_fix_profile(profile_path)

        except IOError as e:
            print(f"Error checking profile format for {profile_path.name}: {e}")

    def create_default_profile(self, profile_path: Path):
        """Create a default ME3 profile with proper structure"""
        # Determine game name and mods directory from profile filename
        profile_name = profile_path.name.lower()
        game_name = "eldenring"  # default
        game_key = "Elden Ring"  # default
        
        # Map profile names to game info
        if "nightreign" in profile_name:
            game_name = "nightreign"
            game_key = "Nightreign"
        elif "sekiro" in profile_name:
            game_name = "sekiro"
            game_key = "Sekiro"
        elif "eldenring" in profile_name:
            game_name = "eldenring"
            game_key = "Elden Ring"
        elif "armoredcore6" in profile_name:
            game_name = "armoredcore6"
            game_key = "Armoredcore6"
        
        mods_dir = self.games.get(game_key, {}).get("mods_dir", "")
        
        # Create proper TOML structure
        config_data = {
            "profileVersion": "v1",
            "natives": [],
            "packages": [
                {
                    "id": mods_dir,
                    "source": str(self.config_root / mods_dir), 
                    "load_after": [],
                    "load_before": []
                }
            ],
            "supports": [
                {
                    "game": game_name
                }
            ]
        }
        
        self._write_toml_config(profile_path, config_data)
    
    def _parse_toml_config(self, config_path: Path) -> Dict[str, Any]:
        """Parse TOML config file, with fallback to regex parsing"""
        if not config_path.exists():
            return {"profileVersion": "v1", "natives": [], "packages": [], "supports": []}
        
        try:
            # Try using TOML library first
            if tomllib:
                with open(config_path, 'rb') as f:
                    return tomllib.load(f)
        except Exception as e:
            print(f"TOML parsing failed, trying fallback: {e}")
        
        # Fallback to regex parsing for malformed files
        return self._parse_config_fallback(config_path)
    
    def _parse_config_fallback(self, config_path: Path) -> Dict[str, Any]:
        """Fallback parser for malformed TOML files"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            config_data = {
                "profileVersion": "v1",
                "natives": [],
                "packages": [],
                "supports": []
            }
            
            # Extract profileVersion
            version_match = re.search(r'profileVersion\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            if version_match:
                config_data["profileVersion"] = version_match.group(1)
            
            # Extract natives paths - handle both single and multiple [[natives]] blocks
            # More flexible pattern to handle various whitespace and formatting
            native_pattern = r'\[\[natives\]\]\s*\r?\n\s*path\s*=\s*[\'"]([^\'"]+)[\'"]'
            native_matches = re.findall(native_pattern, content, re.MULTILINE | re.IGNORECASE)
            config_data["natives"] = [{"path": path} for path in native_matches]
            
            # Debug: Print what we found and the content being parsed
            print(f"Parsing profile content (first 500 chars): {content[:500]}")
            print(f"Found {len(native_matches)} native paths in profile: {native_matches}")
            
            # Extract supports
            supports_pattern = r'\[\[supports\]\]\s*\n\s*(?:name\s*=\s*[\'"]([^\'"]+)[\'"]|game\s*=\s*[\'"]([^\'"]+)[\'"]|id\s*=\s*[\'"]([^\'"]+)[\'"])'
            supports_matches = re.findall(supports_pattern, content, re.MULTILINE | re.IGNORECASE)
            
            for match in supports_matches:
                game_name = match[0] or match[1] or match[2]
                if game_name:
                    if game_name.upper() == "ELDEN RING" or game_name.upper() == "ER":
                        game_name = "eldenring"
                    elif game_name.upper() == "NIGHTREIGN" or game_name.upper() == "NR":
                        game_name = "nightreign"
                    config_data["supports"].append({"game": game_name.lower()})
            
            # Extract packages
            packages_pattern = r'\[\[packages\]\]\s*\n(?:.*\n)*?(?=\[\[|$)'
            packages_matches = re.findall(packages_pattern, content, re.MULTILINE | re.DOTALL)
            
            for package_block in packages_matches:
                package_data = {"load_after": [], "load_before": []}
                
                id_match = re.search(r'id\s*=\s*[\'"]([^\'"]+)[\'"]', package_block)
                if id_match:
                    package_data["id"] = id_match.group(1)
                
                path_match = re.search(r'path\s*=\s*[\'"]([^\'"]+)[\'"]', package_block)
                if path_match:
                    package_data["path"] = path_match.group(1)
                
                source_match = re.search(r'source\s*=\s*[\'"]([^\'"]+)[\'"]', package_block)
                if source_match:
                    package_data["source"] = source_match.group(1)
                
                config_data["packages"].append(package_data)
            
            return config_data
            
        except Exception as e:
            print(f"Error in fallback parsing: {e}")
            return {"profileVersion": "v1", "natives": [], "packages": [], "supports": []}
    
    def _write_toml_config(self, config_path: Path, config_data: Dict[str, Any]):
        """Write TOML config file with proper formatting"""
        # Always use manual formatting for ME3 compatibility
        self._write_config_manual(config_path, config_data)

    def _write_config_manual(self, config_path: Path, config_data: Dict[str, Any]):
        """Manual TOML formatting for ME3 compatibility using inline array format."""
        lines = []

        # Check if this is a custom profile (outside config_root)
        is_custom_profile = not str(config_path).startswith(str(self.config_root))

        # Profile version
        lines.append(f'profileVersion = "{config_data.get("profileVersion", "v1")}"')
        lines.append('')

        # Natives
        natives = config_data.get("natives", [])
        if natives:
            lines.append("natives = [")
            native_items = []
            for native in natives:
                path = native['path'] if isinstance(native, dict) else native
                
                # For custom profiles, ensure paths are absolute if they're relative
                if is_custom_profile and not Path(path).is_absolute():
                    # Try to resolve relative path from the profile's directory
                    profile_dir = config_path.parent
                    potential_absolute = profile_dir / path
                    if potential_absolute.exists():
                        path = str(potential_absolute.resolve())
                
                native_items.append(f"    {{path = '{path}'}}")
            lines.append(",\n".join(native_items))
            lines.append("]")
        else:
            lines.append("natives = []")
        lines.append('')

        # Supports
        supports = config_data.get("supports", [])
        if supports:
            lines.append("supports = [")
            support_items = []
            for support in supports:
                game = support['game'] if isinstance(support, dict) else support
                support_items.append(f'    {{game = "{game}"}}')
            lines.append(",\n".join(support_items))
            lines.append("]")
        else:
            lines.append("supports = []")
        lines.append('')

        # Packages
        all_packages = config_data.get("packages", [])
        # Filter out the main mods directory package from the output list
        main_mods_dirs = {game_info["mods_dir"] for game_info in self.games.values()}
        packages_to_write = [p for p in all_packages if p.get("id") not in main_mods_dirs]

        if packages_to_write:
            lines.append("packages = [")
            package_items = []
            for package in packages_to_write:
                package_parts = []
                if "id" in package:
                    package_parts.append(f'id = "{package["id"]}"')

                source_path = ""
                if "source" in package:
                    source_path = package["source"]
                elif "path" in package:
                    source_path = package["path"]
                
                if source_path:
                    # For custom profiles, always use absolute paths with forward slashes
                    if is_custom_profile:
                        if not Path(source_path).is_absolute():
                            # Try to resolve relative path from the profile's directory
                            profile_dir = config_path.parent
                            potential_absolute = profile_dir / source_path
                            if potential_absolute.exists():
                                source_path = str(potential_absolute.resolve()).replace('\\', '/')
                        else:
                            # Convert backslashes to forward slashes for Windows compatibility
                            source_path = source_path.replace('\\', '/')
                        # Use single quotes to avoid TOML escaping issues
                        package_parts.append(f"source = '{source_path}'")
                    else:
                        # For default profiles, convert to relative path if it's within the config root
                        if Path(source_path).is_absolute() and source_path.startswith(str(self.config_root)):
                            # Make it relative to config_root and use forward slashes
                            relative_path = Path(source_path).relative_to(self.config_root)
                            source_path = str(relative_path).replace('\\', '/')
                        package_parts.append(f"source = '{source_path}'")
                
                package_str = "{ " + ", ".join(package_parts) + " }"
                package_items.append(f"    {package_str}")
            
            lines.append(",\n".join(package_items))
            lines.append("]")
        else:
            lines.append("packages = []")

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    
    def setup_file_watcher(self):
        """
        Sets up the file watcher to monitor ALL profile directories for changes AND
        all specific .me3 profile files for deletion/modification.
        """
        target_dirs = set()
        target_files = set()

        for game_name, profile_list in self.profiles.items():
            # Add the default mods directory for this game
            default_mods_dir = self.config_root / self.games[game_name]["mods_dir"]
            if default_mods_dir.is_dir():
                target_dirs.add(str(default_mods_dir))

            # Add all custom profile directories and their corresponding .me3 files
            for profile in profile_list:
                if profile['id'] != 'default':
                    mods_path_str = profile.get('mods_path')
                    if mods_path_str and Path(mods_path_str).is_dir():
                        target_dirs.add(mods_path_str)

                    profile_path_str = profile.get('profile_path')
                    if profile_path_str and Path(profile_path_str).is_file():
                        target_files.add(profile_path_str)
        
        # Get the paths currently being watched
        current_dirs = self.file_watcher.directories()
        current_files = self.file_watcher.files()
        
        # Convert sets to lists for the API calls
        target_dirs_list = list(target_dirs)
        target_files_list = list(target_files)

        # Update directory watcher
        if set(current_dirs) != target_dirs:
            if current_dirs: self.file_watcher.removePaths(current_dirs)
            if target_dirs_list: self.file_watcher.addPaths(target_dirs_list)
            print(f"Updated watched directories to: {target_dirs_list}")

        # Update file watcher
        if set(current_files) != target_files:
            # Note: removePaths and addPaths work for both files and dirs
            if current_files: self.file_watcher.removePaths(current_files)
            if target_files_list: self.file_watcher.addPaths(target_files_list)
            print(f"Updated watched files to: {target_files_list}")
        
    def get_mods_dir(self, game_name: str) -> Path:
        """Get the mods directory for the active profile of a game."""
        active_profile = self.get_active_profile(game_name)
        if active_profile and active_profile.get('mods_path'):
            return Path(active_profile['mods_path'])
        return self.config_root / self.games[game_name]["mods_dir"]
    
    def get_profile_path(self, game_name: str) -> Path:
        """Get the profile file path for the active profile of a game."""
        active_profile = self.get_active_profile(game_name)
        if active_profile and active_profile.get('profile_path'):
            return Path(active_profile['profile_path'])
        return self.config_root / self.games[game_name]["profile"]
    
    def get_profiles_for_game(self, game_name: str) -> List[Dict]:
        """Get all saved profiles for a specific game."""
        return self.profiles.get(game_name, [])
    
    def set_active_profile(self, game_name: str, profile_id: str):
        """Sets the active profile for a game."""
        self.active_profiles[game_name] = profile_id
        self._save_settings()
        self.setup_file_watcher()

    def add_profile(self, game_name: str, name: str, mods_path: str, make_active: bool = False) -> Optional[str]:
        """Adds a new profile for a game. The .me3 file is created inside the mods folder."""
        import uuid
        profile_id = str(uuid.uuid4())
        mods_dir = Path(mods_path)
        mods_dir.mkdir(parents=True, exist_ok=True)
        
        # Profile file is now always stored inside the mods directory for simplicity
        # Sanitize the profile name for the filename
        safe_filename = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
        profile_file_path = mods_dir / f"{safe_filename.replace(' ', '_')}.me3"
        
        # Create the profile content
        game_cli_id = self.get_game_cli_id(game_name)
        config_data = {
            "profileVersion": "v1", "natives": [], "packages": [],
            "supports": [{"game": game_cli_id or "eldenring"}]
        }
        self._write_toml_config(profile_file_path, config_data)

        new_profile = {
            "id": profile_id,
            "name": name,
            "profile_path": str(profile_file_path),
            "mods_path": str(mods_dir)
        }
        self.profiles.setdefault(game_name, []).append(new_profile)
        
        if make_active:
            self.set_active_profile(game_name, profile_id)
        else:
            self._save_settings()
            
        return profile_id

    def update_profile(self, game_name: str, profile_id: str, new_name: str):
        """Renames a profile."""
        for profile in self.get_profiles_for_game(game_name):
            if profile['id'] == profile_id:
                profile['name'] = new_name
                self._save_settings()
                return
            
    def delete_profile(self, game_name: str, profile_id: str):
        """Deletes a custom profile and its associated tracked external mods."""
        if profile_id == 'default':
            return 

        # Delete from profiles list
        game_profiles = self.get_profiles_for_game(game_name)
        self.profiles[game_name] = [p for p in game_profiles if p['id'] != profile_id]
        
        if game_name in self.tracked_external_mods:
            # Safely remove the entry for the deleted profile
            self.tracked_external_mods[game_name].pop(profile_id, None)

        if self.active_profiles.get(game_name) == profile_id:
            self.set_active_profile(game_name, 'default')
        else:
            self._save_settings()
    
    def get_active_profile(self, game_name: str) -> Optional[Dict]:
        """Get the active profile object for a game."""
        active_id = self.active_profiles.get(game_name, 'default')
        for profile in self.get_profiles_for_game(game_name):
            if profile['id'] == active_id:
                return profile
        return None
    
    def set_custom_profile_path(self, game_name: str, path: Optional[str]):
        """Set or clear custom profile path for a game"""
        if path:
            self.custom_profile_paths[game_name] = path
        else:
            self.custom_profile_paths.pop(game_name, None)
        self._save_settings()
    
    def set_custom_mods_path(self, game_name: str, path: Optional[str]):
        """Set or clear custom mods directory path for a game."""
        if path:
            self.custom_mods_paths[game_name] = path
        else:
            # Store the current custom path before clearing it
            current_path = self.custom_mods_paths.get(game_name)
            if current_path:
                self.stored_custom_mods_paths[game_name] = current_path
            self.custom_mods_paths.pop(game_name, None)
            
        self._save_settings()
        self.setup_file_watcher()
    
    def get_custom_profile_path(self, game_name: str) -> Optional[str]:
        """Get custom profile path for a game"""
        return self.custom_profile_paths.get(game_name)
    
    def get_custom_mods_path(self, game_name: str) -> Optional[str]:
        """Get custom mods directory path for a game"""
        return self.custom_mods_paths.get(game_name)
    
    def get_stored_custom_mods_path(self, game_name: str) -> Optional[str]:
        """Get stored custom mods directory path for a game"""
        return self.stored_custom_mods_paths.get(game_name)
    
    def restore_custom_mods_path(self, game_name: str):
        """Restore previously stored custom mods path"""
        stored_path = self.stored_custom_mods_paths.get(game_name)
        if stored_path:
            self.custom_mods_paths[game_name] = stored_path
            self._save_settings()
            return True
        return False
    
    def parse_me3_config(self, config_path: Path) -> List[str]:
        """Parse ME3 configuration file and extract native DLL paths"""
        config_data = self._parse_toml_config(config_path)
        native_paths = []
        
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                native_paths.append(native["path"])
            elif isinstance(native, str):
                native_paths.append(native)
        
        return native_paths
    
    def write_me3_config(self, config_path: Path, native_paths: List[str]):
        """Write ME3 configuration file with native DLL paths in proper format"""
        # Read existing config or create default
        config_data = self._parse_toml_config(config_path)
        
        # Ensure proper structure
        if "profileVersion" not in config_data:
            config_data["profileVersion"] = "v1"
        
        # Update natives
        config_data["natives"] = [{"path": path} for path in native_paths]
        
        # Ensure supports section exists
        if not config_data.get("supports"):
            game_name = "nightreign" if "nightreign" in config_path.name else "eldenring"
            config_data["supports"] = [{"game": game_name}]
        
        # Ensure packages section exists with default package
        if not config_data.get("packages"):
            mods_dir = self.games.get("Nightreign" if "nightreign" in config_path.name else "Elden Ring", {}).get("mods_dir", "")
            if mods_dir:
                config_data["packages"] = [
                    {
                        "id": mods_dir,
                        "path": str(self.config_root / mods_dir),
                        "load_after": [],
                        "load_before": []
                    }
                ]
        
        # Write the corrected config
        self._write_toml_config(config_path, config_data)
    
    def get_mods_info(self, game_name: str) -> Dict[str, Dict]:
        """
        Get information about all mods for a game, discovering new mods from the
        filesystem and syncing the status of tracked mods from the config file.
        """
        #self.sync_profile_with_filesystem(game_name)

        mods_info = {}
        profile_path = self.get_profile_path(game_name)
        
        enabled_dll_paths = set(self.parse_me3_config(profile_path))
        config_data = self._parse_toml_config(profile_path)
        enabled_folder_mods = {
            pkg.get("id", "") for pkg in config_data.get("packages", [])
            if pkg.get("id") != self.games[game_name]['mods_dir']
        }
        
        active_regulation_mod = self._get_active_regulation_mod(game_name)
        mods_dir = self.get_mods_dir(game_name)

        # Step 1: Scan the filesystem for all mods in the active mods folder.
        if mods_dir.exists(): # Add a check to prevent errors if the dir was deleted
            for dll_file in mods_dir.glob("*.dll"):
                # Determine the correct path format for the config file
                active_mods_dir = self.get_mods_dir(game_name)
                default_mods_dir_path = self.config_root / self.games[game_name]["mods_dir"]
                
                config_path = ""
                if active_mods_dir == default_mods_dir_path:
                    # Standard internal mod: use the relative path format
                    config_path = f"{self.games[game_name]['mods_dir']}\\{dll_file.name}"
                else:
                    # Mod in a custom folder: use its absolute path
                    config_path = str(dll_file).replace('\\', '/')
                    
                mods_info[str(dll_file)] = {
                    'name': dll_file.stem,
                    'enabled': config_path in enabled_dll_paths,
                    'external': False,
                    'is_folder_mod': False
                }

            acceptable_folders = ['_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
                                'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
                                'parts', 'script', 'sd', 'sfx', 'shader', 'sound']
            
            for folder in mods_dir.iterdir():
                if folder.is_dir() and folder.name != self.games[game_name]['mods_dir']:
                    is_valid = False
                    has_regulation = (folder / "regulation.bin").exists() or (folder / "regulation.bin.disabled").exists()
                    
                    if folder.name in acceptable_folders:
                        is_valid = True
                    else:
                        # Check for subfolders that are valid mod content folders
                        if any(sub.is_dir() and sub.name in acceptable_folders for sub in folder.iterdir()):
                            is_valid = True
                    
                    if not is_valid and has_regulation:
                        is_valid = True
                    
                    if is_valid:
                        mod_info = {
                            'name': folder.name,
                            'enabled': folder.name in enabled_folder_mods,
                            'external': False,
                            'is_folder_mod': True
                        }
                        if has_regulation:
                            mod_info['has_regulation'] = True
                            mod_info['regulation_active'] = has_regulation and folder.name == active_regulation_mod
                        
                        mods_info[str(folder)] = mod_info
        
        # Step 2: Discover and sync all EXTERNAL mods for the ACTIVE profile.
        active_profile_id = self.active_profiles.get(game_name, 'default')
        
        enabled_external_paths = {
            p.replace('\\', '/') for p in enabled_dll_paths 
            if not Path(p).is_relative_to(self.config_root) and not p.startswith(self.games[game_name]['mods_dir'])
        }
        
        tracked_paths_list = []
        game_specific_mods = self.tracked_external_mods.get(game_name, {})
        if isinstance(game_specific_mods, dict):
            tracked_paths_list = game_specific_mods.get(active_profile_id, [])
        
        tracked_paths = {p.replace('\\', '/') for p in tracked_paths_list}
        all_known_external_paths = enabled_external_paths.union(tracked_paths)

        for path_str in all_known_external_paths:
            if path_str in mods_info:
                continue

            if not Path(path_str).exists():
                continue

            if path_str not in tracked_paths:
                self.track_external_mod(game_name, path_str)

            mods_info[path_str] = {
                'name': Path(path_str).stem,
                'enabled': path_str in enabled_external_paths,
                'external': True,
                'is_folder_mod': False
            }
        
        return mods_info
    
    def _get_active_regulation_mod(self, game_name: str) -> Optional[str]:
        """Find which mod currently has the active regulation.bin file"""
        mods_dir = self.get_mods_dir(game_name)
        
        for folder in mods_dir.iterdir():
            if folder.is_dir() and (folder / "regulation.bin").exists():
                return folder.name
        return None

    def set_regulation_active(self, game_name: str, mod_name: str):
        """Set which mod should have the active regulation.bin file"""
        mods_dir = self.get_mods_dir(game_name)
        
        # First, disable all regulation files
        for folder in mods_dir.iterdir():
            if folder.is_dir():
                regulation_file = folder / "regulation.bin"
                disabled_file = folder / "regulation.bin.disabled"
                
                if regulation_file.exists():
                    regulation_file.rename(disabled_file)
        
        # Then enable the selected mod's regulation file
        target_folder = mods_dir / mod_name
        if target_folder.exists():
            disabled_file = target_folder / "regulation.bin.disabled"
            regulation_file = target_folder / "regulation.bin"
            
            if disabled_file.exists():
                disabled_file.rename(regulation_file)
    
    def set_mod_enabled(self, game_name: str, mod_path: str, enabled: bool):
        """Enable or disable a mod"""
        mod_path_obj = Path(mod_path)
        
        if mod_path_obj.is_dir():
            # Handle folder mod (This logic is mostly fine)
            if Path(mod_path).is_absolute() and mod_path.startswith(str(self.config_root)):
                relative_path = Path(mod_path).relative_to(self.config_root)
                config_mod_path = str(relative_path).replace('\\', '/')
            else:
                config_mod_path = mod_path.replace('\\', '/')
            
            if enabled:
                self.add_folder_mod(game_name, mod_path_obj.name, config_mod_path)
            else:
                self.remove_folder_mod(game_name, mod_path_obj.name)
        else:
            # Handle DLL mod
            profile_path = self.get_profile_path(game_name)
            current_paths = self.parse_me3_config(profile_path)
            

            # Determine default and active mods directories
            active_mods_dir = self.get_mods_dir(game_name)
            default_mods_dir_path = self.config_root / self.games[game_name]["mods_dir"]

            config_path = ""
            # A mod is only "internal" (with a relative path) if it's in the DEFAULT mods folder.
            if mod_path_obj.parent == default_mods_dir_path:
                # Standard internal mod: use the relative path format
                config_path = f"{self.games[game_name]['mods_dir']}\\{mod_path_obj.name}"
            else:
                # Any other mod (in a custom mods folder or truly external) gets an absolute path.
                # Use forward slashes for cross-platform compatibility in the config.
                config_path = mod_path.replace('\\', '/')
            
            
            # Normalize all paths before comparison to avoid slash issues.
            normalized_config_path = config_path.replace('\\', '/')
            current_paths = [p for p in current_paths if p.replace('\\', '/') != normalized_config_path]
            
            if enabled:
                current_paths.append(config_path)
            
            self.write_me3_config(profile_path, current_paths)

    def _disable_other_regulation_mods(self, game_name: str, current_mod_path: str):
        """Disable all other mods that contain regulation.bin"""
        mods_info = self.get_mods_info(game_name)
        
        for mod_path, info in mods_info.items():
            if mod_path == current_mod_path or not info['enabled']:
                continue
                
            has_regulation = False
            
            if info.get('is_folder_mod', False):
                folder_path = Path(mod_path)
                if (folder_path / "regulation.bin").exists():
                    has_regulation = True
            
            if has_regulation:
                if info.get('is_folder_mod', False):
                    self.remove_folder_mod(game_name, Path(mod_path).name)

    
    def delete_mod(self, game_name: str, mod_path: str):
            """
            Delete a mod.
            If it's a DLL mod, also delete its associated config folder (if it exists).
            """
            mod_path_obj = Path(mod_path)
            
            if mod_path_obj.is_dir():
                # Handle folder mod
                self.remove_folder_mod(game_name, mod_path_obj.name)
                if mod_path_obj.parent == self.get_mods_dir(game_name):
                    shutil.rmtree(mod_path_obj)
            else:
                # Disable the mod first.
                self.set_mod_enabled(game_name, mod_path, False)
                
                # Check if it's an internal or external mod.
                if mod_path_obj.parent == self.get_mods_dir(game_name):
                    # Internal: Delete the files
                    if mod_path_obj.exists():
                        mod_path_obj.unlink()

                    config_folder_path = mod_path_obj.parent / mod_path_obj.stem
                    if config_folder_path.is_dir():
                        try:
                            shutil.rmtree(config_folder_path)
                        except OSError as e:
                            print(f"Error removing config folder {config_folder_path}: {e}")
                else:
                    # External: Just untrack it from our settings
                    self.untrack_external_mod(game_name, mod_path)

    def add_folder_mod(self, game_name: str, mod_name: str, mod_path: str):
        """Add a folder mod to the packages section"""
        profile_path = self.get_profile_path(game_name)
        config_data = self._parse_toml_config(profile_path)
        
        if "packages" not in config_data:
            config_data["packages"] = []
        
        existing_ids = [pkg.get("id", "") for pkg in config_data.get("packages")]
        if mod_name not in existing_ids:
            config_data["packages"].append({
                "id": mod_name,
                "source": mod_path,
                "load_after": [],
                "load_before": []
            })
            
            self._write_toml_config(profile_path, config_data)

    def remove_folder_mod(self, game_name: str, mod_name: str):
        """Remove a folder mod from the packages section"""
        profile_path = self.get_profile_path(game_name)
        config_data = self._parse_toml_config(profile_path)
        
        if "packages" in config_data:
            config_data["packages"] = [
                pkg for pkg in config_data["packages"] 
                if pkg.get("id", "") != mod_name
            ]
            
            self._write_toml_config(profile_path, config_data)
    
    def validate_and_fix_profile(self, profile_path: Path):
        """Validate and fix profile format to ensure it matches the correct structure"""
        try:
            config_data = self._parse_toml_config(profile_path)
            
            needs_fixing = False
            
            if "profileVersion" not in config_data:
                config_data["profileVersion"] = "v1"
                needs_fixing = True
            
            if "natives" in config_data:
                fixed_natives = []
                for native in config_data["natives"]:
                    if isinstance(native, str):
                        fixed_natives.append({"path": native})
                        needs_fixing = True
                    elif isinstance(native, dict) and "path" in native:
                        fixed_natives.append(native)
                config_data["natives"] = fixed_natives
            
            if "supports" in config_data:
                fixed_supports = []
                for support in config_data["supports"]:
                    if isinstance(support, dict):
                        if "name" in support or "id" in support:
                            game_name = support.get("name", support.get("id", ""))
                            if game_name.upper() == "ELDEN RING" or game_name.upper() == "ER":
                                game_name = "eldenring"
                            elif game_name.upper() == "NIGHTREIGN" or game_name.upper() == "NR":
                                game_name = "nightreign"
                            fixed_supports.append({"game": game_name.lower()})
                            needs_fixing = True
                        elif "game" in support:
                            fixed_supports.append(support)
                config_data["supports"] = fixed_supports
            
            if "packages" not in config_data or not config_data["packages"]:
                game_name = "nightreign" if "nightreign" in profile_path.name else "eldenring"
                game_key = "Nightreign" if "nightreign" in profile_path.name else "Elden Ring"
                mods_dir = self.games.get(game_key, {}).get("mods_dir", "")
                
                if mods_dir:
                    config_data["packages"] = [
                        {
                            "id": mods_dir,
                            "path": str(self.config_root / mods_dir),
                            "load_after": [],
                            "load_before": []
                        }
                    ]
                    needs_fixing = True
            else:
                for package in config_data["packages"]:
                    if "path" not in package and "source" not in package:
                        if "id" in package:
                            package["path"] = str(self.config_root / package["id"])
                            needs_fixing = True
            
            print(f"Validating and writing profile: {profile_path}")
            self._write_toml_config(profile_path, config_data)
            
            return config_data
            
        except Exception as e:
            print(f"Error validating/fixing profile {profile_path}: {e}")
            self.create_default_profile(profile_path)
            return self._parse_toml_config(profile_path)
        
    def sync_profile_with_filesystem(self, game_name: str):
        """
        Removes entries from the profile file that point to non-existent files or folders.
        This cleans up the config if a user manually deletes mod files.
        """
        profile_path = self.get_profile_path(game_name)
        if not profile_path.exists():
            return

        config_data = self._parse_toml_config(profile_path)
        modified = False

        # Sync Natives (DLLs) ---
        if "natives" in config_data:
            original_natives = config_data.get("natives", [])
            valid_natives = []
            for native_entry in original_natives:
                path_str = native_entry.get("path", "")
                if not path_str:
                    continue

              
                path_obj = Path(path_str)
                full_path = path_obj
                
                # If path is not absolute, it's assumed to be relative to the default config root.
                # This is the format for mods in the default mods folder.
                if not path_obj.is_absolute():
                    full_path = self.config_root / path_str.replace('\\', '/')
        
                
                if full_path.exists():
                    valid_natives.append(native_entry)
            
            if len(valid_natives) != len(original_natives):
                config_data["natives"] = valid_natives
                modified = True

        # Sync Tracked External Mods
        if game_name in self.tracked_external_mods:
            original_tracked = self.tracked_external_mods[game_name]
            # Normalize all paths before checking for existence
            valid_tracked = [p for p in original_tracked if Path(p.replace('\\', '/')).exists()]
            if len(valid_tracked) != len(original_tracked):
                self.tracked_external_mods[game_name] = valid_tracked
                self._save_settings()

        # Sync Packages (Folder Mods) ---
        if "packages" in config_data:
            original_packages = config_data.get("packages", [])
            valid_packages = []
            main_mods_dir_id = self.games[game_name]["mods_dir"]
            
            for package_entry in original_packages:
                if package_entry.get("id") == main_mods_dir_id:
                    valid_packages.append(package_entry)
                    continue

                source_str = package_entry.get("source") or package_entry.get("path")
                if not source_str:
                    modified = True
                    continue
                
        
                path_obj = Path(source_str)
                full_path = path_obj
                
                # If path is not absolute, it's assumed to be relative to the default config root.
                if not path_obj.is_absolute():
                    full_path = self.config_root / source_str
         

                if full_path.exists() and full_path.is_dir():
                    valid_packages.append(package_entry)
                else:
                    modified = True
            
            if len(valid_packages) != len(original_packages):
                 config_data["packages"] = valid_packages

        if modified:
            print(f"Saving updated profile for '{game_name}' after syncing with filesystem.")
            self._write_toml_config(profile_path, config_data)

    def get_game_order(self) -> List[str]:
        """Get the current game order"""
        return self.game_order.copy()

    def set_game_order(self, new_order: List[str]):
        """Set a new game order and save it"""
        valid_games = set(self.games.keys())
        if set(new_order) == valid_games:
            self.game_order = new_order.copy()
            self._save_settings()

    def get_profile_content(self, game_name: str) -> str:
        """Reads the raw content of a game's .me3 profile file."""
        profile_path = self.get_profile_path(game_name)
        if not profile_path.exists():
            self.create_default_profile(profile_path)
        
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            print(f"Error reading profile file {profile_path}: {e}")
            raise

    def save_profile_content(self, game_name: str, content: str):
        """
        Saves raw content to a game's .me3 profile file and validates it.
        """
        profile_path = self.get_profile_path(game_name)
        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.check_and_reformat_profile(profile_path)
        except IOError as e:
            print(f"Error writing to profile file {profile_path}: {e}")
            raise

    def is_me3_installed(self) -> bool:
        """Check if ME3 is installed and accessible"""
        return self.me3_info.is_me3_installed()

    def get_me3_version(self) -> Optional[str]:
        """Get ME3 version"""
        return self.me3_info.get_version()

    def get_steam_path(self) -> Optional[Path]:
        """Get Steam installation path"""
        return self.me3_info.get_steam_path()

    def get_logs_directory(self) -> Optional[Path]:
        """Get ME3 logs directory"""
        return self.me3_info.get_logs_directory()

    def get_installation_prefix(self) -> Optional[Path]:
        """Get ME3 installation prefix"""
        return self.me3_info.get_installation_prefix()

    def refresh_me3_info(self):
        """Refresh ME3 info cache (useful after installation)"""
        self.me3_info.refresh_info()
        dynamic_profile_dir = self.me3_info.get_profile_directory()
        if dynamic_profile_dir:
            self.config_root = dynamic_profile_dir
            self.settings_file = self.config_root.parent / "manager_settings.json"

    def get_auto_launch_steam(self) -> bool:
        """Get the auto-launch Steam setting"""
        return self.ui_settings.get('auto_launch_steam', False)

    def set_auto_launch_steam(self, enabled: bool):
        """Set the auto-launch Steam setting"""
        self.ui_settings['auto_launch_steam'] = enabled
        self._save_settings()

    def launch_steam_silently(self) -> bool:
        """Launch Steam silently in the background if not already running"""
        
        steam_path = self.get_steam_path()

        if self._is_steam_running():
            print("Steam is already running, skipping launch")
            return True

        try:
            if sys.platform == "win32":
                steam_exe = steam_path / "steam.exe"
                if not steam_exe.exists():
                    print(f"Steam executable not found at {steam_exe}")
                    return False

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                subprocess.Popen(
                    [str(steam_exe), "-silent"],
                    startupinfo=startupinfo,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("Steam launched silently in background (Windows)")
                return True

            else:
                steam_sh = steam_path / "steam.sh"
                if not steam_sh.exists():
                    print(f"Steam script not found at {steam_sh}")
                    return False

                if "FLATPAK_ID" in os.environ:
                    if shutil.which("flatpak-spawn"):
                        subprocess.Popen([
                            "flatpak-spawn", "--host", str(steam_sh), "-silent"
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        print("Steam launched via flatpak-spawn")
                        return True
                    else:
                        print("flatpak-spawn not found")
                        return False
                else:
                    subprocess.Popen(
                        [str(steam_sh), "-silent"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    print("Steam launched silently in background (Linux)")
                    return True

                return False

        except Exception as e:
            print(f"Error launching Steam: {e}")
            return False
    
    def simple_import_from_folder(self, game_name: str, import_folder: str, profile_file: str, merge: bool = True, custom_mod_name: str = None) -> Dict[str, Any]:
        """
        Simplified import from a folder containing both profile and mods.
        """
        results = {
            'success': False,
            'profile_imported': False,
            'package_mods_imported': 0,
            'dll_mods_imported': 0,
            'mods_skipped': 0,
            'skipped_details': [], # NEW: To store details about skipped mods
            'errors': []
        }
        
        try:
            import_path = Path(import_folder)
            profile_path = Path(profile_file)
            
            if not import_path.exists():
                results['errors'].append(f"Import folder not found: {import_folder}")
                return results
            if not profile_path.exists():
                results['errors'].append(f"Profile file not found: {profile_file}")
                return results
            
            source_config = self._parse_toml_config(profile_path)
            current_profile_path = self.get_profile_path(game_name)
            
            if merge:
                current_config = self._parse_toml_config(current_profile_path)
            else:
                current_config = {"profileVersion": "v1", "natives": [], "packages": [], "supports": []}

            # --- 1. Process Natives (DLLs) ---
            processed_dll_paths = {p.get('path', '').replace('\\', '/') for p in current_config.get('natives', [])}
            
            for native in source_config.get('natives', []):
                original_path_str = native.get('path', '') if isinstance(native, dict) else native
                if not original_path_str:
                    continue

                full_path = import_path / original_path_str if not Path(original_path_str).is_absolute() else Path(original_path_str)
                normalized_full_path = str(full_path).replace('\\', '/')
                normalized_original_path = original_path_str.replace('\\', '/')

                if normalized_full_path in processed_dll_paths or normalized_original_path in processed_dll_paths:
                    # NEW: Add detailed reason for skipping
                    if merge:
                        results['mods_skipped'] += 1
                        results['skipped_details'].append(f"DLL '{Path(original_path_str).name}' already exists in the active profile.")
                    continue

                if full_path.exists() and full_path.suffix.lower() == '.dll':
                    processed_dll_paths.add(normalized_original_path)
                    processed_dll_paths.add(normalized_full_path)
                    self.track_external_mod(game_name, str(full_path))
                    results['dll_mods_imported'] += 1
                else:
                    if merge:
                        results['mods_skipped'] += 1
                        # NEW: Add detailed reason for skipping
                        results['skipped_details'].append(f"DLL '{Path(original_path_str).name}' not found at expected path.")
                    else:
                        results['errors'].append(f"DLL mod from profile not found at expected path: {full_path}")

            # --- 2. Process Packages (Folder Mods) ---
            if custom_mod_name:
                final_mod_name = custom_mod_name.strip()
                target_mods_dir = self.get_mods_dir(game_name)
                new_mod_folder = target_mods_dir / final_mod_name
                
                if new_mod_folder.exists() and merge:
                    # NEW: Add detailed reason for skipping
                    results['mods_skipped'] += 1
                    results['skipped_details'].append(f"Package '{final_mod_name}' already exists in the mods folder.")
                else:
                    if new_mod_folder.exists():
                        shutil.rmtree(new_mod_folder)

                    folders_to_copy = []
                    source_dirs_map = {p.name.lower(): p for p in import_path.iterdir() if p.is_dir()}
                    
                    for package in source_config.get('packages', []):
                        package_key = package.get('source') or package.get('id')
                        if not package_key: continue
                        lookup_key = Path(package_key).name.lower()
                        if lookup_key in source_dirs_map:
                            folders_to_copy.append(source_dirs_map[lookup_key])
                    
                    if folders_to_copy:
                        try:
                            new_mod_folder.mkdir(parents=True, exist_ok=True)
                            for src_folder in folders_to_copy:
                                shutil.copytree(src_folder, new_mod_folder, dirs_exist_ok=True)
                            
                            mod_source_path = str(new_mod_folder).replace('\\', '/')
                            if final_mod_name not in {p.get('id') for p in current_config.get('packages', [])}:
                                current_config.setdefault('packages', []).append({
                                    "id": final_mod_name, "source": mod_source_path,
                                    "load_after": [], "load_before": []
                                })
                            results['package_mods_imported'] = 1
                        except Exception as e:
                            results['errors'].append(f"Failed to create bundled mod '{final_mod_name}': {str(e)}")
                            if new_mod_folder.exists(): shutil.rmtree(new_mod_folder)

            # --- 3. Finalize Profile ---
            current_config['natives'] = [{'path': p} for p in processed_dll_paths]
            current_config['supports'] = source_config.get('supports', [])
            current_config['profileVersion'] = source_config.get('profileVersion', 'v1')
            
            self._write_toml_config(current_profile_path, current_config)
            results['profile_imported'] = True
            results['success'] = True
            
        except Exception as e:
            results['errors'].append(f"An unexpected error occurred during import: {str(e)}")
        
        return results
        
    def create_custom_profile(self, game_name: str, profile_name: str, profile_dir: Optional[str] = None, mods_dir: Optional[str] = None) -> bool:
        """
        Create a new custom profile for a game with optional custom directories.
        
        Args:
            game_name: The game to create profile for
            profile_name: Name for the new profile (without .me3 extension)
            profile_dir: Optional custom directory for the profile file
            mods_dir: Optional custom directory for mods
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine profile path
            if profile_dir:
                profile_path = Path(profile_dir) / f"{profile_name}.me3"
                profile_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                profile_path = self.config_root / f"{profile_name}.me3"
            
            # Determine mods directory path
            if mods_dir:
                mods_path = Path(mods_dir)
                mods_path.mkdir(parents=True, exist_ok=True)
            else:
                mods_path = self.config_root / f"{profile_name}-mods"
                mods_path.mkdir(parents=True, exist_ok=True)
            
            # Create the profile
            game_cli_id = self.get_game_cli_id(game_name)
            config_data = {
                "profileVersion": "v1",
                "natives": [],
                "packages": [],  # A new profile should start with an empty package list
                "supports": [
                    {
                        "game": game_cli_id or "eldenring"
                    }
                ]
            }
            
            self._write_toml_config(profile_path, config_data)
            
            # Set as custom paths for this game
            self.set_custom_profile_path(game_name, str(profile_path))
            self.set_custom_mods_path(game_name, str(mods_path))
            
            return True
            
        except Exception as e:
            print(f"Error creating custom profile: {e}")
            return False

    def _is_steam_running(self) -> bool:
        """Check if Steam is already running"""
        try:
            import subprocess
            import sys
            
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
                    capture_output=True,
                    text=True,
                    startupinfo=startupinfo,
                    timeout=5
                )
                
                return "steam.exe" in result.stdout.lower()
            else:
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", "steam.sh|steam$"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                        
                    result = subprocess.run(
                        ["pgrep", "steam"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                        
                except FileNotFoundError:
                    result = subprocess.run(
                        ["ps", "aux"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    lines = result.stdout.lower().split('\n')
                    for line in lines:
                        if ('steam' in line and 
                            ('steam.sh' in line or 
                            line.strip().endswith('steam') or
                            'steam -' in line)):
                            return True
                            
                return False
                    
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception) as e:
            print(f"Error checking if Steam is running: {e}")
            return False
        
        return False
