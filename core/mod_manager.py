"""
Simplified and robust mod management system for ME3 Manager.
This module provides clean, reliable methods for managing mods.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json
from dataclasses import dataclass
from enum import Enum

class ModType(Enum):
    DLL = "dll"
    PACKAGE = "package"

class ModStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    MISSING = "missing"

@dataclass
class ModInfo:
    """Clean data structure for mod information"""
    path: str
    name: str
    mod_type: ModType
    status: ModStatus
    is_external: bool
    has_regulation: bool = False
    regulation_active: bool = False
    advanced_options: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.advanced_options is None:
            self.advanced_options = {}

class ModManager:
    """
    Clean, simplified mod management system.
    Separates concerns and provides reliable mod operations.
    """
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._mod_cache = {}
        self._external_mods_cache = {}
    
    def get_all_mods(self, game_name: str) -> Dict[str, ModInfo]:
        """
        Get all mods for a game with clean, reliable logic.
        Returns a dictionary mapping mod paths to ModInfo objects.
        """
        # Clear cache to ensure fresh data
        self._mod_cache.clear()
        
        # Get mods directory and profile
        mods_dir = self.config_manager.get_mods_dir(game_name)
        profile_path = self.config_manager.get_profile_path(game_name)
        
        if not mods_dir.exists():
            return {}
        
        # Parse profile for enabled status and advanced options
        config_data = self.config_manager._parse_toml_config(profile_path)
        enabled_status = self._parse_enabled_status(config_data)
        advanced_options = self._parse_advanced_options(config_data)
        
        all_mods = {}
        
        # 1. Scan filesystem for internal mods
        internal_mods = self._scan_internal_mods(game_name, mods_dir, enabled_status, advanced_options)
        all_mods.update(internal_mods)
        
        # 2. Add tracked external mods
        external_mods = self._get_external_mods(game_name, enabled_status, advanced_options)
        all_mods.update(external_mods)
        
        # 3. Clean up orphaned entries
        self._cleanup_orphaned_entries(game_name, all_mods)
        
        return all_mods
    
    def _scan_internal_mods(self, game_name: str, mods_dir: Path, enabled_status: Dict, advanced_options: Dict) -> Dict[str, ModInfo]:
        """Scan filesystem for internal mods (DLLs and packages)"""
        mods = {}
        
        # Scan for DLL mods
        for dll_file in mods_dir.glob("*.dll"):
            mod_path = str(dll_file)
            config_path = self._get_config_path_for_mod(game_name, mod_path)
            
            mod_info = ModInfo(
                path=mod_path,
                name=dll_file.stem,
                mod_type=ModType.DLL,
                status=ModStatus.ENABLED if enabled_status.get(config_path, False) else ModStatus.DISABLED,
                is_external=False,
                advanced_options=advanced_options.get(config_path, {})
            )
            mods[mod_path] = mod_info
        
        # Scan for package mods
        acceptable_folders = ['_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
                            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
                            'parts', 'script', 'sd', 'sfx', 'shader', 'sound']
        
        for folder in mods_dir.iterdir():
            if not folder.is_dir() or folder.name == self.config_manager.games[game_name]['mods_dir']:
                continue
            
            # Check if it's a valid mod folder
            is_valid = False
            has_regulation = (folder / "regulation.bin").exists() or (folder / "regulation.bin.disabled").exists()
            
            if folder.name in acceptable_folders:
                is_valid = True
            elif any(sub.is_dir() and sub.name in acceptable_folders for sub in folder.iterdir()):
                is_valid = True
            elif has_regulation:
                is_valid = True
            
            if is_valid:
                mod_path = str(folder)
                regulation_active = has_regulation and (folder / "regulation.bin").exists()
                
                mod_info = ModInfo(
                    path=mod_path,
                    name=folder.name,
                    mod_type=ModType.PACKAGE,
                    status=ModStatus.ENABLED if enabled_status.get(folder.name, False) else ModStatus.DISABLED,
                    is_external=False,
                    has_regulation=has_regulation,
                    regulation_active=regulation_active,
                    advanced_options=advanced_options.get(folder.name, {})
                )
                mods[mod_path] = mod_info
        
        return mods
    
    def _get_external_mods(self, game_name: str, enabled_status: Dict, advanced_options: Dict) -> Dict[str, ModInfo]:
        """Get tracked external mods"""
        mods = {}
        
        # Get tracked external mods for active profile
        active_profile_id = self.config_manager.active_profiles.get(game_name, 'default')
        game_external_mods = self.config_manager.tracked_external_mods.get(game_name, {})
        
        if isinstance(game_external_mods, dict):
            tracked_paths = game_external_mods.get(active_profile_id, [])
        else:
            tracked_paths = []
        
        for mod_path in tracked_paths:
            path_obj = Path(mod_path)
            
            if not path_obj.exists():
                # Mark as missing but keep in list
                mod_info = ModInfo(
                    path=mod_path,
                    name=path_obj.stem,
                    mod_type=ModType.DLL,  # External mods are typically DLLs
                    status=ModStatus.MISSING,
                    is_external=True,
                    advanced_options=advanced_options.get(mod_path, {})
                )
            else:
                mod_info = ModInfo(
                    path=mod_path,
                    name=path_obj.stem,
                    mod_type=ModType.DLL,
                    status=ModStatus.ENABLED if enabled_status.get(mod_path, False) else ModStatus.DISABLED,
                    is_external=True,
                    advanced_options=advanced_options.get(mod_path, {})
                )
            
            mods[mod_path] = mod_info
        
        return mods
    
    def _parse_enabled_status(self, config_data: Dict) -> Dict[str, bool]:
        """Parse enabled status from profile config - presence means enabled"""
        enabled_status = {}
        
        # Parse natives - if present in config, it's enabled
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]
                # If entry exists in config, it's enabled (regardless of enabled field)
                enabled_status[path] = True
        
        # Parse packages - if present in config, it's enabled
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                # If entry exists in config, it's enabled (regardless of enabled field)
                enabled_status[pkg_id] = True
        
        return enabled_status
    
    def _parse_advanced_options(self, config_data: Dict) -> Dict[str, Dict]:
        """Parse advanced options from profile config"""
        advanced_options = {}
        
        # Parse natives advanced options
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]
                options = {k: v for k, v in native.items() if k not in ["path", "enabled"]}
                if options:
                    advanced_options[path] = options
        
        # Parse packages advanced options
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                options = {k: v for k, v in package.items() if k not in ["id", "path", "source", "enabled"]}
                if options:
                    advanced_options[pkg_id] = options
        
        return advanced_options
    
    def _get_config_path_for_mod(self, game_name: str, mod_path: str) -> str:
        """Get the config path format used in the profile for a mod"""
        mod_path_obj = Path(mod_path)
        active_mods_dir = self.config_manager.get_mods_dir(game_name)
        default_mods_dir_path = self.config_manager.config_root / self.config_manager.games[game_name]["mods_dir"]
        
        if mod_path_obj.parent == default_mods_dir_path:
            # Internal mod: use relative path format
            return f"{self.config_manager.games[game_name]['mods_dir']}\\{mod_path_obj.name}"
        else:
            # External mod: use absolute path format
            return mod_path.replace('\\', '/')
    
    def _cleanup_orphaned_entries(self, game_name: str, current_mods: Dict[str, ModInfo]):
        """Clean up orphaned entries from profile and tracking"""
        profile_path = self.config_manager.get_profile_path(game_name)
        config_data = self.config_manager._parse_toml_config(profile_path)
        
        # Get current mod paths and config paths
        current_paths = set(current_mods.keys())
        current_config_paths = set()
        
        for mod_path, mod_info in current_mods.items():
            if mod_info.mod_type == ModType.DLL:
                config_path = self._get_config_path_for_mod(game_name, mod_path)
                current_config_paths.add(config_path)
            else:
                current_config_paths.add(mod_info.name)
        
        # Clean up natives
        valid_natives = []
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                if native["path"] in current_config_paths:
                    valid_natives.append(native)
        
        # Clean up packages (keep main mods dir)
        valid_packages = []
        main_mods_dir = self.config_manager.games[game_name]["mods_dir"]
        
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                if pkg_id == main_mods_dir or pkg_id in current_config_paths:
                    valid_packages.append(package)
        
        # Update config if needed
        if len(valid_natives) != len(config_data.get("natives", [])) or \
           len(valid_packages) != len(config_data.get("packages", [])):
            config_data["natives"] = valid_natives
            config_data["packages"] = valid_packages
            self.config_manager._write_toml_config(profile_path, config_data)
    
    def add_external_mod(self, game_name: str, mod_path: str) -> Tuple[bool, str]:
        """
        Add an external mod with robust error handling.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)
            
            # Validate mod file
            if not mod_path_obj.exists():
                return False, f"Mod file not found: {mod_path}"
            
            if not mod_path_obj.is_file() or mod_path_obj.suffix.lower() != '.dll':
                return False, "Only DLL files can be added as external mods"
            
            # Check if it's already in the mods directory
            mods_dir = self.config_manager.get_mods_dir(game_name)
            if mod_path_obj.parent == mods_dir:
                return False, "This mod is already in the game's mods folder"
            
            # Normalize path
            normalized_path = str(mod_path_obj.resolve()).replace('\\', '/')
            
            # Check if already tracked
            active_profile_id = self.config_manager.active_profiles.get(game_name, 'default')
            game_external_mods = self.config_manager.tracked_external_mods.get(game_name, {})
            
            if isinstance(game_external_mods, dict):
                tracked_paths = game_external_mods.get(active_profile_id, [])
            else:
                tracked_paths = []
            
            if normalized_path in tracked_paths:
                return False, "This external mod is already tracked"
            
            # Add to tracking
            self.config_manager.track_external_mod(game_name, normalized_path)
            
            # Enable the mod by default
            success, msg = self.set_mod_enabled(game_name, normalized_path, True)
            if not success:
                # Remove from tracking if enabling failed
                self.config_manager.untrack_external_mod(game_name, normalized_path)
                return False, f"Failed to enable mod: {msg}"
            
            return True, f"Successfully added external mod: {mod_path_obj.name}"
            
        except Exception as e:
            return False, f"Error adding external mod: {str(e)}"
    
    def set_mod_enabled(self, game_name: str, mod_path: str, enabled: bool) -> Tuple[bool, str]:
        """
        Set mod enabled status with robust error handling.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)
            profile_path = self.config_manager.get_profile_path(game_name)
            config_data = self.config_manager._parse_toml_config(profile_path)
            
            if mod_path_obj.is_dir():
                # Handle package mod
                success, msg = self._set_package_enabled(config_data, mod_path_obj.name, enabled)
            else:
                # Handle DLL mod
                config_path = self._get_config_path_for_mod(game_name, mod_path)
                success, msg = self._set_native_enabled(config_data, config_path, enabled)
            
            if success:
                self.config_manager._write_toml_config(profile_path, config_data)
                action = "enabled" if enabled else "disabled"
                return True, f"Successfully {action} {mod_path_obj.name}"
            else:
                return False, msg
                
        except Exception as e:
            return False, f"Error setting mod status: {str(e)}"
    
    def _set_native_enabled(self, config_data: Dict, config_path: str, enabled: bool) -> Tuple[bool, str]:
        """Set enabled status for a native (DLL) mod"""
        natives = config_data.get("natives", [])
        
        # Find existing entry
        native_entry = None
        native_index = -1
        for i, native in enumerate(natives):
            if isinstance(native, dict) and native.get("path") == config_path:
                native_entry = native
                native_index = i
                break
        
        if enabled:
            if native_entry is None:
                # Create new entry without enabled field
                native_entry = {"path": config_path}
                # Preserve any existing advanced options if they exist
                natives.append(native_entry)
                config_data["natives"] = natives
                return True, "Created new native entry"
            else:
                # Entry already exists, ensure no enabled field
                if "enabled" in native_entry:
                    del native_entry["enabled"]
                return True, "Native entry already exists"
        else:
            if native_entry is not None:
                # Remove the entry completely when disabling
                natives.pop(native_index)
                config_data["natives"] = natives
                return True, "Removed native entry"
            else:
                # Nothing to disable
                return True, "Mod was already disabled"
    
    def _set_package_enabled(self, config_data: Dict, mod_name: str, enabled: bool) -> Tuple[bool, str]:
        """Set enabled status for a package (folder) mod"""
        packages = config_data.get("packages", [])
        
        # Find existing entry
        package_entry = None
        package_index = -1
        for i, package in enumerate(packages):
            if isinstance(package, dict) and package.get("id") == mod_name:
                package_entry = package
                package_index = i
                break
        
        if enabled:
            if package_entry is None:
                # Create new entry - we need to determine the source path
                # For package mods, we can infer the path from the mod name
                # This assumes the package is in the current game's mods directory
                package_entry = {
                    "id": mod_name,
                    "source": mod_name,  # Will be resolved to full path by config manager
                    "load_after": [],
                    "load_before": []
                }
                packages.append(package_entry)
                config_data["packages"] = packages
                return True, "Created new package entry"
            else:
                # Entry already exists, ensure no enabled field
                if "enabled" in package_entry:
                    del package_entry["enabled"]
                return True, "Package entry already exists"
        else:
            if package_entry is not None:
                # Remove the entry completely when disabling
                packages.pop(package_index)
                config_data["packages"] = packages
                return True, "Removed package entry"
            else:
                # Nothing to disable
                return True, "Package was already disabled"
    
    def remove_mod(self, game_name: str, mod_path: str) -> Tuple[bool, str]:
        """
        Remove a mod completely with robust error handling.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)
            
            # First disable the mod
            success, msg = self.set_mod_enabled(game_name, mod_path, False)
            if not success:
                return False, f"Failed to disable mod before removal: {msg}"
            
            if mod_path_obj.is_dir():
                # Handle folder mod
                mods_dir = self.config_manager.get_mods_dir(game_name)
                if mod_path_obj.parent == mods_dir:
                    # Internal folder mod - delete from filesystem
                    import shutil
                    shutil.rmtree(mod_path_obj)
                    return True, f"Deleted folder mod: {mod_path_obj.name}"
                else:
                    return False, "Cannot delete external folder mods"
            else:
                # Handle DLL mod
                mods_dir = self.config_manager.get_mods_dir(game_name)
                if mod_path_obj.parent == mods_dir:
                    # Internal DLL mod - delete from filesystem
                    mod_path_obj.unlink()
                    
                    # Also remove config folder if it exists
                    config_folder = mod_path_obj.parent / mod_path_obj.stem
                    if config_folder.is_dir():
                        import shutil
                        shutil.rmtree(config_folder)
                    
                    return True, f"Deleted DLL mod: {mod_path_obj.name}"
                else:
                    # External DLL mod - just untrack it
                    self.config_manager.untrack_external_mod(game_name, mod_path)
                    return True, f"Untracked external mod: {mod_path_obj.name}"
                    
        except Exception as e:
            return False, f"Error removing mod: {str(e)}"
    
    def has_advanced_options(self, mod_info: ModInfo) -> bool:
        """Check if a mod has any advanced options configured"""
        if not mod_info.advanced_options:
            return False
        
        # Check for any advanced options beyond basic ones
        advanced_keys = ['optional', 'initializer', 'finalizer', 'load_before', 'load_after']
        return any(key in mod_info.advanced_options and mod_info.advanced_options[key] 
                  for key in advanced_keys)
