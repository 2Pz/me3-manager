import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
from PyQt6.QtCore import QFileSystemWatcher
import tomllib

class ConfigManager:
    """Manages ME3 configuration files and mod directories"""
    
    def __init__(self):
        self.config_root = Path(os.path.expandvars(r"%LocalAppData%\garyttierney\me3\config\profiles"))
        self.settings_file = self.config_root.parent / "manager_settings.json"
        self.custom_config_paths = self._load_settings()
        self.games = {
            "Elden Ring": {
                "mods_dir": "eldenring-mods",
                "profile": "eldenring-default.me3"
            },
            "Nightreign": {
                "mods_dir": "nightreign-mods", 
                "profile": "nightreign-default.me3"
            }
        }
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
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_config_paths, f, indent=4)
        except IOError as e:
            print(f"Error saving settings: {e}")

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
        """Create necessary directories if they don't exist"""
        self.config_root.mkdir(parents=True, exist_ok=True)
        
        for game_info in self.games.values():
            mods_dir = self.config_root / game_info["mods_dir"]
            mods_dir.mkdir(exist_ok=True)
            
            profile_path = self.config_root / game_info["profile"]
            if not profile_path.exists():
                self.create_default_profile(profile_path)
    
    def create_default_profile(self, profile_path: Path):
        """Create a default ME3 profile with proper structure"""
        game_name = "nightreign" if "nightreign" in profile_path.name else "eldenring"
        mods_dir = self.games.get("Nightreign" if "nightreign" in profile_path.name else "Elden Ring", {}).get("mods_dir", "")
        
        # Create proper TOML structure
        config_data = {
            "profileVersion": "v1",
            "natives": [],
            "packages": [
                {
                    "id": mods_dir,
                    "path": str(self.config_root / mods_dir),
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
                    # Convert old format to new format
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
        # The standard TOML libraries write arrays inline, but ME3 expects [[section]] format
        self._write_config_manual(config_path, config_data)
    
    def _write_config_manual(self, config_path: Path, config_data: Dict[str, Any]):
        """Manual TOML formatting for ME3 compatibility using [[section]] format"""
        lines = []
        
        # Profile version
        lines.append(f'profileVersion = "{config_data.get("profileVersion", "v1")}"')
        
        # Natives - each as separate [[natives]] section
        for native in config_data.get("natives", []):
            lines.append("[[natives]]")
            lines.append(f"path = '{native['path']}'")
        
        # Supports - each as separate [[supports]] section  
        for support in config_data.get("supports", []):
            lines.append("[[supports]]")
            lines.append(f"game = \"{support['game']}\"")
        
        # Packages - each as separate [[packages]] section
        for package in config_data.get("packages", []):
            lines.append("[[packages]]")
            if "id" in package:
                lines.append(f"id = \"{package['id']}\"")
            # Path is required for packages - ensure it exists
            if "path" in package:
                lines.append(f"path = '{package['path']}'")
            elif "source" in package:
                lines.append(f"source = \"{package['source']}\"")
            else:
                # If no path or source, create default path based on id
                if "id" in package:
                    default_path = str(self.config_root / package["id"])
                    lines.append(f"path = '{default_path}'")
            
            lines.append(f"load_after = {package.get('load_after', [])}")
            lines.append(f"load_before = {package.get('load_before', [])}")
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
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

        # Check for regulation.bin (enabled or disabled)
        regulation_file = mods_dir / "regulation.bin"
        disabled_regulation_file = mods_dir / "regulation.bin.disabled"

        # The mod exists if either the enabled or disabled version is present.
        if regulation_file.exists() or disabled_regulation_file.exists():
            # It's enabled if the non-.disabled file exists.
            is_enabled = regulation_file.exists()
            
            # Use the enabled path as the canonical key for the mod item.
            # This ensures that actions like toggling or deleting work correctly.
            canonical_path = str(regulation_file)
            
            mods_info[canonical_path] = {
                'name': 'regulation.bin',
                'enabled': is_enabled,
                'external': False,
                'is_folder_mod': False,
                'is_regulation': True
            }
        
        # Scan mods directory for folder mods
        acceptable_folders = ['_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
                            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
                            'parts', 'script', 'sd', 'sfx', 'shader', 'sound']
        
        for folder in mods_dir.iterdir():
            if folder.is_dir() and folder.name != self.games[game_name]['mods_dir']:
                # Check if it's a valid mod folder
                is_valid = False
                if folder.name in acceptable_folders:
                    is_valid = True
                else:
                    # Check if it contains acceptable subfolders
                    for subfolder in folder.iterdir():
                        if subfolder.is_dir() and subfolder.name in acceptable_folders:
                            is_valid = True
                            break
                
                if is_valid:
                    mods_info[str(folder)] = {
                        'name': folder.name,
                        'enabled': folder.name in enabled_folder_mods,
                        'external': False,
                        'is_folder_mod': True
                    }
        
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
    
    def set_mod_enabled(self, game_name: str, mod_path: str, enabled: bool):
        """Enable or disable a mod"""
        mod_path_obj = Path(mod_path)
        
        # NEW BLOCK - Handle regulation.bin
        if mod_path_obj.name == "regulation.bin":
            mods_dir = self.get_mods_dir(game_name)
            regulation_file = mods_dir / "regulation.bin"
            disabled_regulation = mods_dir / "regulation.bin.disabled"
            
            if enabled:
                # Enable: rename from .disabled back to .bin (if disabled exists)
                if disabled_regulation.exists():
                    disabled_regulation.rename(regulation_file)
            else:
                # Disable: rename to .disabled
                if regulation_file.exists():
                    regulation_file.rename(disabled_regulation)
            return
        
        # Check if it's a folder mod
        if mod_path_obj.is_dir():
            # Handle folder mod
            if enabled:
                self.add_folder_mod(game_name, mod_path_obj.name, mod_path)
            else:
                self.remove_folder_mod(game_name, mod_path_obj.name)
        else:
            # Handle DLL mod (existing logic)
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
    
    def delete_mod(self, game_name: str, mod_path: str):
        """Delete a mod"""
        mod_path_obj = Path(mod_path)
        
        # NEW BLOCK - Handle regulation.bin deletion
        if mod_path_obj.name == "regulation.bin":
            mods_dir = self.get_mods_dir(game_name)
            regulation_file = mods_dir / "regulation.bin"
            disabled_regulation = mods_dir / "regulation.bin.disabled"
            
            # Delete both enabled and disabled versions
            if regulation_file.exists():
                regulation_file.unlink()
            if disabled_regulation.exists():
                disabled_regulation.unlink()
            return
        
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
                "path": mod_path,
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
            if needs_fixing:
                print(f"Fixing profile format: {profile_path}")
                self._write_toml_config(profile_path, config_data)
            
            return config_data
            
        except Exception as e:
            print(f"Error validating/fixing profile {profile_path}: {e}")
            # Create a completely new profile if parsing fails
            self.create_default_profile(profile_path)
            return self._parse_toml_config(profile_path)
