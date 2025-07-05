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

class ConfigManager:
    """Manages ME3 configuration files and mod directories"""
    
    def __init__(self):
        self.config_root = Path(os.path.expandvars(r"%LocalAppData%\garyttierney\me3\config\profiles"))
        self.settings_file = self.config_root.parent / "manager_settings.json"
        
        # Load games from JSON configuration
        self.games = self._load_games_config()
        
        settings = self._load_settings()
        self.custom_config_paths = settings.get('custom_config_paths', {})
        self.game_exe_paths = settings.get('game_exe_paths', {})
        self.ui_settings = settings.get('ui_settings', {}) # Load UI settings
        
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
        """Saves custom settings to the JSON file."""
        try:
            all_settings = {
                'custom_config_paths': self.custom_config_paths,
                'game_exe_paths': self.game_exe_paths,
                'game_order': getattr(self, 'game_order', list(self.games.keys())),
                'ui_settings': self.ui_settings
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(all_settings, f, indent=4)
        except IOError as e:
            print(f"Error saving settings: {e}")

    def _load_games_config(self) -> dict:
        """Load games configuration from JSON file."""
        games_config_path = Path(resource_path("resources/games_config.json"))
        
        # Fallback to hardcoded games if JSON file doesn't exist
        fallback_games = {
            "Elden Ring": {
                "mods_dir": "eldenring-mods",
                "profile": "eldenring-default.me3",
                "cli_id": "elden-ring"
            },
            "Nightreign": {
                "mods_dir": "nightreign-mods", 
                "profile": "nightreign-default.me3",
                "cli_id": "nightreign"
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
        """
        mod_filename = Path(mod_path_str).name
        
        # Check for a saved custom path
        custom_path = self.custom_config_paths.get(game_name, {}).get(mod_filename)
        if custom_path:
            return Path(custom_path)
            
        # Fallback to default path convention
        mod_path = Path(mod_path_str)
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def set_mod_config_path(self, game_name: str, mod_path_str: str, config_path: str):
        """Saves a custom config path for a mod."""
        mod_filename = Path(mod_path_str).name
        
        # Ensure the game's dictionary exists
        self.custom_config_paths.setdefault(game_name, {})
        
        self.custom_config_paths[game_name][mod_filename] = config_path
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
            
            # Extract natives paths
            native_pattern = r'\[\[natives\]\]\s*\n\s*path\s*=\s*[\'"]([^\'"]+)[\'"]'
            native_matches = re.findall(native_pattern, content, re.MULTILINE | re.IGNORECASE)
            config_data["natives"] = [{"path": path} for path in native_matches]
            
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
        """Setup file system watcher for mod directories"""
        for game_info in self.games.values():
            mods_dir = self.config_root / game_info["mods_dir"]
            self.file_watcher.addPath(str(mods_dir))
    
    def get_mods_dir(self, game_name: str) -> Path:
        """Get mods directory for a game"""
        return self.config_root / self.games[game_name]["mods_dir"]
    
    def get_profile_path(self, game_name: str) -> Path:
        """Get profile path for a game"""
        return self.config_root / self.games[game_name]["profile"]
    
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
        """Get information about all mods for a game"""
        mods_info = {}
        
        # Get profile config
        profile_path = self.get_profile_path(game_name)
        config_data = self._parse_toml_config(profile_path)
        enabled_paths = self.parse_me3_config(profile_path)
        enabled_mods = set(enabled_paths)
        
        # Get enabled folder mods from packages
        enabled_folder_mods = set()
        if "packages" in config_data:
            for package in config_data["packages"]:
                pkg_id = package.get("id", "")
                if pkg_id != self.games[game_name]['mods_dir']:  # Skip the main mods directory package
                    enabled_folder_mods.add(pkg_id)
        
        # Find which regulation mod is currently active
        active_regulation_mod = self._get_active_regulation_mod(game_name)

        # Scan mods directory for DLL files
        mods_dir = self.get_mods_dir(game_name)
        for dll_file in mods_dir.glob("*.dll"):
            relative_path = f"{self.games[game_name]['mods_dir']}\\{dll_file.name}"
            mods_info[str(dll_file)] = {
                'name': dll_file.stem,
                'enabled': relative_path in enabled_mods,
                'external': False,
                'is_folder_mod': False
            }

        
        
        # Scan mods directory for folder mods
        acceptable_folders = ['_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
                            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
                            'parts', 'script', 'sd', 'sfx', 'shader', 'sound']
        
        for folder in mods_dir.iterdir():
            if folder.is_dir() and folder.name != self.games[game_name]['mods_dir']:
                # Check if it's a valid mod folder
                is_valid = False
                has_regulation = (folder / "regulation.bin").exists()
                has_disabled_regulation = (folder / "regulation.bin.disabled").exists()
                
                if folder.name in acceptable_folders:
                    is_valid = True
                else:
                    # Check if it contains acceptable subfolders
                    for subfolder in folder.iterdir():
                        if subfolder.is_dir() and subfolder.name in acceptable_folders:
                            is_valid = True
                            break
                
                # Also consider it valid if it contains regulation files
                if not is_valid and (has_regulation or has_disabled_regulation):
                    is_valid = True
                
                if is_valid:
                    mod_info = {
                        'name': folder.name,
                        'enabled': folder.name in enabled_folder_mods,
                        'external': False,
                        'is_folder_mod': True
                    }
                    
                    # Add regulation info if present
                    if has_regulation or has_disabled_regulation:
                        mod_info['has_regulation'] = True
                        mod_info['regulation_active'] = has_regulation and folder.name == active_regulation_mod
                    
                    mods_info[str(folder)] = mod_info
        
        # Add external DLL mods from profile
        for enabled_path in enabled_mods:
            if not enabled_path.startswith(self.games[game_name]['mods_dir']):
                # External mod
                mod_name = Path(enabled_path).stem
                mods_info[enabled_path] = {
                    'name': mod_name,
                    'enabled': True,
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
        
        # Check if it's a folder mod
        if mod_path_obj.is_dir():
            # Handle folder mod
            if enabled:
                self.add_folder_mod(game_name, mod_path_obj.name, mod_path)
            else:
                self.remove_folder_mod(game_name, mod_path_obj.name)
        else:
            # Handle DLL mod (existing logic unchanged)
            profile_path = self.get_profile_path(game_name)
            
            # Get current enabled paths
            current_paths = self.parse_me3_config(profile_path)
            
            # Determine the path to use in config
            if Path(mod_path).is_absolute() and not mod_path.startswith(str(self.config_root)):
                # External mod - use full path with forward slashes
                config_path = mod_path.replace('\\', '/')
            else:
                # Internal mod - use relative path with backslashes
                config_path = f"{self.games[game_name]['mods_dir']}\\{Path(mod_path).name}"
            
            # Remove existing entry for this mod (handle both slash types)
            current_paths = [p for p in current_paths if 
                            p != config_path and 
                            p.replace('\\', '/') != config_path.replace('\\', '/') and
                            p.replace('/', '\\') != config_path.replace('/', '\\')]
            
            # Add entry if enabling
            if enabled:
                current_paths.append(config_path)
            
            # Write updated config
            self.write_me3_config(profile_path, current_paths)

    def _disable_other_regulation_mods(self, game_name: str, current_mod_path: str):
        """Disable all other mods that contain regulation.bin"""
        mods_info = self.get_mods_info(game_name)
        
        for mod_path, info in mods_info.items():
            if mod_path == current_mod_path or not info['enabled']:
                continue
                
            # Check if this mod has regulation.bin
            has_regulation = False
            
            if info.get('is_folder_mod', False):
                # Check if folder mod contains regulation.bin
                folder_path = Path(mod_path)
                if (folder_path / "regulation.bin").exists():
                    has_regulation = True
            
            if has_regulation:
                # Disable this mod
                if info.get('is_folder_mod', False):
                    self.remove_folder_mod(game_name, Path(mod_path).name)

    
    def delete_mod(self, game_name: str, mod_path: str):
        """Delete a mod"""
        mod_path_obj = Path(mod_path)
        
        if mod_path_obj.is_dir():
            # Handle folder mod
            self.remove_folder_mod(game_name, mod_path_obj.name)
            # Delete folder if it's in our mods directory
            if mod_path_obj.parent == self.get_mods_dir(game_name):
                shutil.rmtree(mod_path_obj)
        else:
            # Handle DLL mod (existing logic)
            # Remove from config first
            self.set_mod_enabled(game_name, mod_path, False)
            
            # Delete file if it's in our mods directory
            if mod_path_obj.parent == self.get_mods_dir(game_name):
                mod_path_obj.unlink()

    def add_folder_mod(self, game_name: str, mod_name: str, mod_path: str):
        """Add a folder mod to the packages section"""
        profile_path = self.get_profile_path(game_name)
        config_data = self._parse_toml_config(profile_path)
        
        # Ensure packages section exists
        if "packages" not in config_data:
            config_data["packages"] = []
        
        # Check if mod already exists
        existing_ids = [pkg.get("id", "") for pkg in config_data["packages"]]
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
            # Read and parse the config
            config_data = self._parse_toml_config(profile_path)
            
            # Check if the file needs fixing
            needs_fixing = False
            
            # Check for missing profileVersion
            if "profileVersion" not in config_data:
                config_data["profileVersion"] = "v1"
                needs_fixing = True
            
            # Check natives format
            if "natives" in config_data:
                fixed_natives = []
                for native in config_data["natives"]:
                    if isinstance(native, str):
                        fixed_natives.append({"path": native})
                        needs_fixing = True
                    elif isinstance(native, dict) and "path" in native:
                        fixed_natives.append(native)
                config_data["natives"] = fixed_natives
            
            # Ensure supports has correct format
            if "supports" in config_data:
                fixed_supports = []
                for support in config_data["supports"]:
                    if isinstance(support, dict):
                        # Handle old format conversions
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
            
            # Ensure packages section exists and has required path field
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
                # Check existing packages for missing path field
                for package in config_data["packages"]:
                    if "path" not in package and "source" not in package:
                        # Add path field if missing
                        if "id" in package:
                            package["path"] = str(self.config_root / package["id"])
                            needs_fixing = True
            
            # Write back if fixes were needed
            # We always write back now when called from the startup check
            # to ensure the format is corrected.
            print(f"Validating and writing profile: {profile_path}")
            self._write_toml_config(profile_path, config_data)
            
            return config_data
            
        except Exception as e:
            print(f"Error validating/fixing profile {profile_path}: {e}")
            # Create a completely new profile if parsing fails
            self.create_default_profile(profile_path)
            return self._parse_toml_config(profile_path)

    def get_game_order(self) -> List[str]:
        """Get the current game order"""
        return self.game_order.copy()

    def set_game_order(self, new_order: List[str]):
        """Set a new game order and save it"""
        # Validate that all games in the new order exist
        valid_games = set(self.games.keys())
        if set(new_order) == valid_games:
            self.game_order = new_order.copy()
            self._save_settings()

    def get_profile_content(self, game_name: str) -> str:
        """Reads the raw content of a game's .me3 profile file."""
        profile_path = self.get_profile_path(game_name)
        if not profile_path.exists():
            # If it doesn't exist, create a default one first
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
            # After saving, immediately try to validate and reformat it.
            # This ensures that any user errors are caught/fixed, and the file
            # is always in the standard format we expect.
            self.check_and_reformat_profile(profile_path)
        except IOError as e:
            print(f"Error writing to profile file {profile_path}: {e}")
            raise
