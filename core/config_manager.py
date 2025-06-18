# core/config_manager.py

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtCore import QFileSystemWatcher



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
        """Create a default ME3 profile"""
        game_id = "ER" if "eldenring" in profile_path.name else "NR"
        game_name = "ELDEN RING" if "eldenring" in profile_path.name else "NIGHTREIGN"
        
        default_config = f"""[[supports]]
name = "{game_name}"
id = "{game_id}"
"""
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            f.write(default_config)
    
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
        native_paths = []
        
        if not config_path.exists():
            return native_paths
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use regex to find all [[natives]] sections with path entries
            # Pattern matches: [[natives]] followed by path = 'something'
            pattern = r'\[\[natives\]\]\s*\n\s*path\s*=\s*[\'"]([^\'"]+)[\'"]'
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            
            native_paths = matches
                
        except Exception as e:
            print(f"Error parsing ME3 config: {e}")
            
        return native_paths
    
    def write_me3_config(self, config_path: Path, native_paths: List[str]):
        """Write ME3 configuration file with native DLL paths"""
        try:
            # Read existing content 
            existing_content = ""
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Remove all existing [[natives]] sections
            # Pattern to match [[natives]] section including the path line
            pattern = r'\[\[natives\]\]\s*\n\s*path\s*=\s*[\'"][^\'"]+[\'"]'
            cleaned_content = re.sub(pattern, '', existing_content, flags=re.MULTILINE | re.IGNORECASE)
            
            # Remove extra blank lines
            cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_content)
            cleaned_content = cleaned_content.strip()
            
            # Add native paths before [[supports]] section
            native_sections = []
            for path in native_paths:
                native_sections.append(f"[[natives]]\npath = '{path}'")
            
            if native_sections:
                natives_text = '\n\n'.join(native_sections) + '\n\n'
                
                # Find [[supports]] section and insert before it
                supports_match = re.search(r'\[\[supports\]\]', cleaned_content, re.IGNORECASE)
                if supports_match:
                    insertion_point = supports_match.start()
                    final_content = (
                        cleaned_content[:insertion_point] + 
                        natives_text + 
                        cleaned_content[insertion_point:]
                    )
                else:
                    # If no [[supports]] section, add natives at the end
                    final_content = cleaned_content + '\n\n' + natives_text.rstrip()
            else:
                final_content = cleaned_content
            
            # Write back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
                
        except Exception as e:
            print(f"Error writing ME3 config: {e}")
    def get_mods_info(self, game_name: str) -> Dict[str, Dict]:
        """Get information about all mods for a game"""
        mods_info = {}
        
        # Get profile config using simple text parser
        profile_path = self.get_profile_path(game_name)
        enabled_paths = self.parse_me3_config(profile_path)
        enabled_mods = set(enabled_paths)
        
        # Scan mods directory
        mods_dir = self.get_mods_dir(game_name)
        for dll_file in mods_dir.glob("*.dll"):
            relative_path = f"{self.games[game_name]['mods_dir']}\\{dll_file.name}"
            mods_info[str(dll_file)] = {
                'name': dll_file.stem,
                'enabled': relative_path in enabled_mods,
                'external': False
            }
        
        # Add external mods from profile
        for enabled_path in enabled_mods:
            if not enabled_path.startswith(self.games[game_name]['mods_dir']):
                # External mod
                mod_name = Path(enabled_path).stem
                mods_info[enabled_path] = {
                    'name': mod_name,
                    'enabled': True,
                    'external': True
                }
        
        return mods_info
    
    def set_mod_enabled(self, game_name: str, mod_path: str, enabled: bool):
        """Enable or disable a mod"""
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
        # Remove from config first
        self.set_mod_enabled(game_name, mod_path, False)
        
        # Delete file if it's in our mods directory
        mod_path_obj = Path(mod_path)
        if mod_path_obj.parent == self.get_mods_dir(game_name):
            mod_path_obj.unlink()