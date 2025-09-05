"""
Improved and robust mod management system for ME3 Manager.
Addresses the key issues with package mod enabling, regulation file management,
and path handling consistency.
"""

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ModType(Enum):
    DLL = "dll"
    PACKAGE = "package"
    NESTED = "nested"  # Mods that are inside package mods (like DLLs in subfolders)


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
    parent_package: Optional[str] = None  # For nested mods, the parent package name

    def __post_init__(self):
        if self.advanced_options is None:
            self.advanced_options = {}


class ImprovedModManager:
    """
    Improved mod management system that fixes the key issues:
    1. Allows multiple package mods to be enabled
    2. Properly manages regulation files (only one active at a time)
    3. Uses consistent path handling (relative for internal, absolute only for external DLLs)
    4. Provides robust error handling and validation
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.acceptable_folders = [
            "_backup",
            "_unknown",
            "action",
            "asset",
            "chr",
            "cutscene",
            "event",
            "font",
            "map",
            "material",
            "menu",
            "movie",
            "msg",
            "other",
            "param",
            "parts",
            "script",
            "sd",
            "sfx",
            "shader",
            "sound",
        ]

    def _normalize_path(self, path_str: str) -> str:
        """
        Normalize path to use forward slashes consistently.
        This fixes the path consistency issue between enable/disable operations.
        """
        if not path_str:
            return ""
        return str(Path(path_str)).replace("\\", "/")

    def get_all_mods(self, game_name: str) -> Dict[str, ModInfo]:
        """
        Get all mods for a game with improved logic.
        Returns a dictionary mapping mod paths to ModInfo objects.
        """
        mods_dir = self.config_manager.get_mods_dir(game_name)
        profile_path = self.config_manager.get_profile_path(game_name)

        if not mods_dir.exists():
            return {}

        # Parse profile for enabled status and advanced options
        config_data = self.config_manager._parse_toml_config(profile_path)
        enabled_status = self._parse_enabled_status(config_data, game_name)
        advanced_options = self._parse_advanced_options(config_data)

        all_mods = {}

        # 1. Scan filesystem for internal mods
        internal_mods = self._scan_internal_mods(
            game_name, mods_dir, enabled_status, advanced_options
        )
        all_mods.update(internal_mods)

        # 2. Scan for nested mods within package folders
        nested_mods = self._scan_nested_mods(
            game_name, mods_dir, enabled_status, advanced_options
        )
        all_mods.update(nested_mods)

        # 3. Add tracked external mods
        external_mods = self._get_external_mods(
            game_name, enabled_status, advanced_options
        )
        all_mods.update(external_mods)

        # 4. Clean up orphaned entries
        self._cleanup_orphaned_entries(game_name, all_mods)

        return all_mods

    def _scan_internal_mods(
        self,
        game_name: str,
        mods_dir: Path,
        enabled_status: Dict,
        advanced_options: Dict,
    ) -> Dict[str, ModInfo]:
        """Scan filesystem for internal mods (DLLs and packages)"""
        mods = {}

        # Scan for DLL mods
        for dll_file in mods_dir.glob("*.dll"):
            mod_path = str(dll_file)
            # Use normalized path format for consistency
            mods_dir_name = self.config_manager.games[game_name]["mods_dir"]
            config_key = self._normalize_path(f"{mods_dir_name}/{dll_file.name}")

            mod_info = ModInfo(
                path=mod_path,
                name=dll_file.stem,
                mod_type=ModType.DLL,
                status=ModStatus.ENABLED
                if enabled_status.get(config_key, False)
                else ModStatus.DISABLED,
                is_external=False,
                advanced_options=advanced_options.get(config_key, {}),
            )
            mods[mod_path] = mod_info

        # Scan for package mods
        active_regulation_mod = self._get_active_regulation_mod(mods_dir)

        for folder in mods_dir.iterdir():
            if (
                not folder.is_dir()
                or folder.name == self.config_manager.games[game_name]["mods_dir"]
            ):
                continue

            # Check if it's a valid mod folder
            is_valid = self._is_valid_mod_folder(folder)

            if is_valid:
                mod_path = str(folder)
                has_regulation = (folder / "regulation.bin").exists() or (
                    folder / "regulation.bin.disabled"
                ).exists()
                regulation_active = (
                    has_regulation and folder.name == active_regulation_mod
                )

                mod_info = ModInfo(
                    path=mod_path,
                    name=folder.name,
                    mod_type=ModType.PACKAGE,
                    status=ModStatus.ENABLED
                    if enabled_status.get(folder.name, False)
                    else ModStatus.DISABLED,
                    is_external=False,
                    has_regulation=has_regulation,
                    regulation_active=regulation_active,
                    advanced_options=advanced_options.get(folder.name, {}),
                )
                mods[mod_path] = mod_info

        return mods

    def _is_valid_mod_folder(self, folder: Path) -> bool:
        """Check if a folder is a valid mod folder"""
        # Check if folder name is in acceptable folders
        if folder.name in self.acceptable_folders:
            return True

        # Check if it contains acceptable subfolders
        if any(
            sub.is_dir() and sub.name in self.acceptable_folders
            for sub in folder.iterdir()
        ):
            return True

        # Check if it has regulation files
        if (folder / "regulation.bin").exists() or (
            folder / "regulation.bin.disabled"
        ).exists():
            return True

        return False

    def _get_active_regulation_mod(self, mods_dir: Path) -> Optional[str]:
        """Find which mod currently has the active regulation.bin file"""
        for folder in mods_dir.iterdir():
            if folder.is_dir() and (folder / "regulation.bin").exists():
                return folder.name
        return None

    def _scan_nested_mods(
        self,
        game_name: str,
        mods_dir: Path,
        enabled_status: Dict,
        advanced_options: Dict,
    ) -> Dict[str, ModInfo]:
        """
        Scan for nested mods within package folders.
        These are DLLs that exist inside package mod folders and should be treated as separate mods.
        """
        nested_mods = {}

        # Scan through all package folders
        for folder in mods_dir.iterdir():
            if (
                not folder.is_dir()
                or folder.name == self.config_manager.games[game_name]["mods_dir"]
            ):
                continue

            # Check if this folder is a valid mod package
            if not self._is_valid_mod_folder(folder):
                continue

            # Recursively scan for DLL files within this package
            for dll_file in folder.rglob("*.dll"):
                # Create a relative path from the mods directory
                try:
                    relative_path = dll_file.relative_to(mods_dir)
                    # Use the same format as _set_native_enabled: mods-dir-name/relative-path
                    mods_dir_name = self.config_manager.games[game_name]["mods_dir"]
                    config_key = self._normalize_path(
                        f"{mods_dir_name}/{relative_path}"
                    )

                    # Create a unique identifier for this nested mod
                    nested_mod_path = str(dll_file)

                    mod_info = ModInfo(
                        path=nested_mod_path,
                        name=f"{folder.name}/{dll_file.stem}",  # Show parent/child relationship
                        mod_type=ModType.NESTED,
                        status=ModStatus.ENABLED
                        if enabled_status.get(config_key, False)
                        else ModStatus.DISABLED,
                        is_external=False,
                        parent_package=folder.name,
                        advanced_options=advanced_options.get(config_key, {}),
                    )

                    nested_mods[nested_mod_path] = mod_info

                except ValueError:
                    # Skip if we can't get relative path
                    continue

        return nested_mods

    def _get_external_mods(
        self, game_name: str, enabled_status: Dict, advanced_options: Dict
    ) -> Dict[str, ModInfo]:
        """Get tracked external mods"""
        mods = {}

        # Get tracked external mods for active profile
        active_profile_id = self.config_manager.active_profiles.get(
            game_name, "default"
        )
        game_external_mods = self.config_manager.tracked_external_mods.get(
            game_name, {}
        )

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
                    mod_type=ModType.DLL,
                    status=ModStatus.MISSING,
                    is_external=True,
                    advanced_options=advanced_options.get(mod_path, {}),
                )
            else:
                # Use full path for external mods
                mod_info = ModInfo(
                    path=mod_path,
                    name=path_obj.stem,
                    mod_type=ModType.DLL,
                    status=ModStatus.ENABLED
                    if enabled_status.get(mod_path, False)
                    else ModStatus.DISABLED,
                    is_external=True,
                    advanced_options=advanced_options.get(mod_path, {}),
                )

            mods[mod_path] = mod_info

        return mods

    def _parse_enabled_status(
        self, config_data: Dict, game_name: str
    ) -> Dict[str, bool]:
        """Parse enabled status from profile config - presence means enabled"""
        enabled_status = {}

        # Parse natives - if present in config, it's enabled
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]

                # Use the same key format as in _scan_internal_mods for consistency
                if Path(path).is_absolute():
                    # External mod - use full path
                    enabled_status[path] = True
                else:
                    # Internal mod - use the full path format (mods-dir\filename.dll)
                    enabled_status[path] = True

        # Parse packages - if present in config, it's enabled
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                # Skip the main mods directory package
                if pkg_id != self.config_manager.games[game_name]["mods_dir"]:
                    enabled_status[pkg_id] = True

        return enabled_status

    def _parse_advanced_options(self, config_data: Dict) -> Dict[str, Dict]:
        """Parse advanced options from profile config"""
        advanced_options = {}

        # Parse natives advanced options
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]
                options = {
                    k: v for k, v in native.items() if k not in ["path", "enabled"]
                }
                if options:
                    # Use the same key format as in _scan_internal_mods for consistency
                    if Path(path).is_absolute():
                        advanced_options[path] = options
                    else:
                        # Use the full path format (mods-dir\filename.dll) as key
                        advanced_options[path] = options

        # Parse packages advanced options
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                options = {
                    k: v
                    for k, v in package.items()
                    if k not in ["id", "path", "source", "enabled"]
                }
                if options:
                    advanced_options[pkg_id] = options

        return advanced_options

    def _cleanup_orphaned_entries(
        self, game_name: str, current_mods: Dict[str, ModInfo]
    ):
        """Clean up orphaned entries from profile and tracking"""
        profile_path = self.config_manager.get_profile_path(game_name)
        config_data = self.config_manager._parse_toml_config(profile_path)

        # Get current mod identifiers including nested mods
        current_dll_names = set()
        current_package_names = set()
        current_external_paths = set()
        current_nested_paths = set()  # NEW: Track nested mod paths

        mods_dir = self.config_manager.get_mods_dir(game_name)

        for mod_path, mod_info in current_mods.items():
            if mod_info.is_external:
                current_external_paths.add(mod_path)
            elif mod_info.mod_type == ModType.DLL:
                current_dll_names.add(mod_info.name + ".dll")
            elif mod_info.mod_type == ModType.NESTED:
                # For nested mods, store the full path with mods directory prefix
                try:
                    relative_path = Path(mod_path).relative_to(mods_dir)
                    mods_dir_name = self.config_manager.games[game_name]["mods_dir"]
                    full_config_path = self._normalize_path(
                        f"{mods_dir_name}/{relative_path}"
                    )
                    current_nested_paths.add(full_config_path)
                except ValueError:
                    pass
            else:  # PACKAGE
                current_package_names.add(mod_info.name)

        # Clean up natives
        valid_natives = []
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]
                normalized_path = self._normalize_path(path)

                if Path(path).is_absolute():
                    # External mod
                    if path in current_external_paths:
                        valid_natives.append(native)
                else:
                    # Internal mod - check if it's a direct DLL or nested mod
                    filename = Path(path).name
                    if (
                        filename in current_dll_names
                        or normalized_path in current_nested_paths
                    ):
                        valid_natives.append(native)

        # Clean up packages (keep main mods dir)
        valid_packages = []
        main_mods_dir = self.config_manager.games[game_name]["mods_dir"]

        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                if pkg_id == main_mods_dir or pkg_id in current_package_names:
                    valid_packages.append(package)

        # Update config if needed
        if len(valid_natives) != len(config_data.get("natives", [])) or len(
            valid_packages
        ) != len(config_data.get("packages", [])):
            config_data["natives"] = valid_natives
            config_data["packages"] = valid_packages
            self._write_improved_config(profile_path, config_data, game_name)

    def set_mod_enabled(
        self, game_name: str, mod_path: str, enabled: bool
    ) -> Tuple[bool, str]:
        """
        Set mod enabled status with improved logic.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)
            profile_path = self.config_manager.get_profile_path(game_name)
            config_data = self.config_manager._parse_toml_config(profile_path)

            if mod_path_obj.is_dir():
                # Handle package mod
                success, msg = self._set_package_enabled(
                    config_data, mod_path_obj.name, enabled, game_name
                )
            else:
                # Handle DLL mod
                success, msg = self._set_native_enabled(
                    config_data, mod_path, enabled, game_name
                )

            if success:
                self._write_improved_config(profile_path, config_data, game_name)
                action = "enabled" if enabled else "disabled"
                return True, f"Successfully {action} {mod_path_obj.name}"
            else:
                return False, msg

        except Exception as e:
            return False, f"Error setting mod status: {str(e)}"

    def _set_native_enabled(
        self, config_data: Dict, mod_path: str, enabled: bool, game_name: str
    ) -> Tuple[bool, str]:
        """Set enabled status for a native (DLL) mod with improved path handling"""
        natives = config_data.get("natives", [])
        mod_path_obj = Path(mod_path)
        mods_dir = self.config_manager.get_mods_dir(game_name)
        mods_dir_name = self.config_manager.games[game_name]["mods_dir"]

        # Determine the correct path format for the config - always use normalized paths
        try:
            # Check if this is a nested mod (inside mods directory but not directly in it)
            relative_path = mod_path_obj.relative_to(mods_dir)
            # For nested mods, prepend the mods directory name like regular DLLs
            config_path = self._normalize_path(f"{mods_dir_name}/{relative_path}")
        except ValueError:
            # Not inside mods directory - external mod
            if mod_path_obj.parent == mods_dir:
                # Direct child of mods directory - internal mod
                config_path = self._normalize_path(
                    f"{mods_dir_name}/{mod_path_obj.name}"
                )
            else:
                # External mod - use normalized absolute path
                config_path = self._normalize_path(str(mod_path_obj.resolve()))

        # Find existing entry using normalized path comparison
        native_entry = None
        native_index = -1
        for i, native in enumerate(natives):
            if isinstance(native, dict) and "path" in native:
                existing_path = self._normalize_path(native.get("path", ""))
                if existing_path == config_path:
                    native_entry = native
                    native_index = i
                    break

        if enabled:
            if native_entry is None:
                # Create new entry
                native_entry = {"path": config_path}
                natives.append(native_entry)
                config_data["natives"] = natives
                return True, "Created new native entry"
            else:
                # Entry already exists
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

    def _set_package_enabled(
        self, config_data: Dict, mod_name: str, enabled: bool, game_name: str
    ) -> Tuple[bool, str]:
        """Set enabled status for a package (folder) mod with improved logic"""
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
                # Create new entry with normalized path that includes mods directory
                mods_dir_name = self.config_manager.games[game_name]["mods_dir"]
                package_path = self._normalize_path(f"{mods_dir_name}/{mod_name}")

                package_entry = {
                    "id": mod_name,
                    "path": package_path,  # Use normalized mods-dir/mod-name format for consistency
                    "load_after": [],
                    "load_before": [],
                }
                packages.append(package_entry)
                config_data["packages"] = packages
                return True, "Created new package entry"
            else:
                # Entry already exists
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

    def set_regulation_active(self, game_name: str, mod_name: str) -> Tuple[bool, str]:
        """
        Set which mod should have the active regulation.bin file.
        Only one regulation file can be active at a time.
        """
        try:
            mods_dir = self.config_manager.get_mods_dir(game_name)

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
                    return True, f"Set {mod_name} as active regulation mod"
                else:
                    return False, f"No regulation file found for {mod_name}"
            else:
                return False, f"Mod folder not found: {mod_name}"

        except Exception as e:
            return False, f"Error setting regulation active: {str(e)}"

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

            if not mod_path_obj.is_file() or mod_path_obj.suffix.lower() != ".dll":
                return False, "Only DLL files can be added as external mods"

            # Check if it's already in the mods directory
            mods_dir = self.config_manager.get_mods_dir(game_name)
            if mod_path_obj.parent == mods_dir:
                return False, "This mod is already in the game's mods folder"

            # Normalize path
            normalized_path = str(mod_path_obj.resolve()).replace("\\", "/")

            # Check if already tracked
            active_profile_id = self.config_manager.active_profiles.get(
                game_name, "default"
            )
            game_external_mods = self.config_manager.tracked_external_mods.get(
                game_name, {}
            )

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

            # Check if this is a nested mod
            mods_dir = self.config_manager.get_mods_dir(game_name)
            is_nested_mod = False

            if mod_path_obj.is_file() and mod_path_obj.suffix.lower() == ".dll":
                try:
                    relative_path = mod_path_obj.relative_to(mods_dir)
                    # If relative path has more than one part, it's nested
                    if len(relative_path.parts) > 1:
                        is_nested_mod = True
                except ValueError:
                    pass

            if is_nested_mod:
                # Nested mod - just remove from profile, don't delete file
                return True, f"Removed nested mod from profile: {mod_path_obj.name}"
            elif mod_path_obj.is_dir():
                # Handle folder mod
                if mod_path_obj.parent == mods_dir:
                    # Internal folder mod - delete from filesystem
                    shutil.rmtree(mod_path_obj)
                    return True, f"Deleted folder mod: {mod_path_obj.name}"
                else:
                    return False, "Cannot delete external folder mods"
            else:
                # Handle DLL mod
                if mod_path_obj.parent == mods_dir:
                    # Internal DLL mod - delete from filesystem
                    mod_path_obj.unlink()

                    # Also remove config folder if it exists
                    config_folder = mod_path_obj.parent / mod_path_obj.stem
                    if config_folder.is_dir():
                        shutil.rmtree(config_folder)

                    return True, f"Deleted DLL mod: {mod_path_obj.name}"
                else:
                    # External DLL mod - just untrack it
                    self.config_manager.untrack_external_mod(game_name, mod_path)
                    return True, f"Untracked external mod: {mod_path_obj.name}"

        except Exception as e:
            return False, f"Error removing mod: {str(e)}"

    def _write_improved_config(
        self, config_path: Path, config_data: Dict[str, Any], game_name: str
    ):
        """Write TOML config file with improved path handling"""
        lines = []

        # Profile version
        lines.append(f'profileVersion = "{config_data.get("profileVersion", "v1")}"')
        lines.append("")

        # Natives
        natives = config_data.get("natives", [])
        if natives:
            lines.append("natives = [")
            native_items = []
            for native in natives:
                if isinstance(native, dict):
                    path = native.get("path", "")

                    # Build the native entry with all advanced options
                    native_parts = [f"path = '{path}'"]

                    # Add optional flag if present
                    if "optional" in native:
                        native_parts.append(
                            f"optional = {str(native['optional']).lower()}"
                        )

                    # Add initializer if present
                    if "initializer" in native:
                        initializer = native["initializer"]
                        if isinstance(initializer, dict):
                            if "function" in initializer:
                                native_parts.append(
                                    f'initializer = {{function = "{initializer["function"]}"}}'
                                )
                            elif "delay" in initializer:
                                delay_ms = initializer["delay"].get("ms", 1000)
                                native_parts.append(
                                    f"initializer = {{delay = {{ms = {delay_ms}}}}}"
                                )

                    # Add finalizer if present
                    if "finalizer" in native:
                        native_parts.append(f'finalizer = "{native["finalizer"]}"')

                    # Add load_before if present
                    if "load_before" in native and native["load_before"]:
                        deps = []
                        for dep in native["load_before"]:
                            dep_id = dep.get("id", "")
                            dep_optional = str(dep.get("optional", False)).lower()
                            deps.append(
                                f'{{id = "{dep_id}", optional = {dep_optional}}}'
                            )
                        native_parts.append(f"load_before = [{', '.join(deps)}]")

                    # Add load_after if present
                    if "load_after" in native and native["load_after"]:
                        deps = []
                        for dep in native["load_after"]:
                            dep_id = dep.get("id", "")
                            dep_optional = str(dep.get("optional", False)).lower()
                            deps.append(
                                f'{{id = "{dep_id}", optional = {dep_optional}}}'
                            )
                        native_parts.append(f"load_after = [{', '.join(deps)}]")

                    # Join all parts in a single line
                    native_items.append(f"    {{{', '.join(native_parts)}}}")

            lines.append(",\n".join(native_items))
            lines.append("]")
        else:
            lines.append("natives = []")
        lines.append("")

        # Supports
        supports = config_data.get("supports", [])
        if supports:
            lines.append("supports = [")
            support_items = []
            for support in supports:
                game = support["game"] if isinstance(support, dict) else support
                support_items.append(f'    {{game = "{game}"}}')
            lines.append(",\n".join(support_items))
            lines.append("]")
        else:
            lines.append("supports = []")
        lines.append("")

        # Packages
        all_packages = config_data.get("packages", [])
        # Filter out the main mods directory package from the output list
        main_mods_dirs = {
            game_info["mods_dir"] for game_info in self.config_manager.games.values()
        }
        packages_to_write = [
            p for p in all_packages if p.get("id") not in main_mods_dirs
        ]

        if packages_to_write:
            lines.append("packages = [")
            package_items = []
            for package in packages_to_write:
                package_parts = []
                if "id" in package:
                    package_parts.append(f'id = "{package["id"]}"')

                # Use path field with normalized paths for consistency
                if "path" in package:
                    path = self._normalize_path(package["path"])
                    package_parts.append(f"path = '{path}'")
                elif "source" in package:
                    # Legacy support for source field
                    source = package["source"]
                    # Convert to relative path if it's internal
                    if Path(source).is_absolute():
                        try:
                            relative_path = Path(source).relative_to(
                                self.config_manager.get_mods_dir(game_name).parent
                            )
                            path = self._normalize_path(str(relative_path))
                        except ValueError:
                            path = self._normalize_path(source)
                    else:
                        path = self._normalize_path(source)
                    package_parts.append(f"path = '{path}'")

                # Add load_before if present
                if "load_before" in package and package["load_before"]:
                    deps = []
                    for dep in package["load_before"]:
                        dep_id = dep.get("id", "")
                        dep_optional = str(dep.get("optional", False)).lower()
                        deps.append(f'{{id = "{dep_id}", optional = {dep_optional}}}')
                    package_parts.append(f"load_before = [{', '.join(deps)}]")

                # Add load_after if present
                if "load_after" in package and package["load_after"]:
                    deps = []
                    for dep in package["load_after"]:
                        dep_id = dep.get("id", "")
                        dep_optional = str(dep.get("optional", False)).lower()
                        deps.append(f'{{id = "{dep_id}", optional = {dep_optional}}}')
                    package_parts.append(f"load_after = [{', '.join(deps)}]")

                package_str = "{" + ", ".join(package_parts) + "}"
                package_items.append(f"    {package_str}")

            lines.append(",\n".join(package_items))
            lines.append("]")
        else:
            lines.append("packages = []")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def has_advanced_options(self, mod_info: ModInfo) -> bool:
        """Check if a mod has any advanced options configured"""
        if not mod_info.advanced_options:
            return False

        # Check for any advanced options beyond basic ones
        advanced_keys = [
            "optional",
            "initializer",
            "finalizer",
            "load_before",
            "load_after",
        ]
        return any(
            key in mod_info.advanced_options and mod_info.advanced_options[key]
            for key in advanced_keys
        )
