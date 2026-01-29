"""
Improved and robust mod management system for ME3 Manager.
Addresses the key issues with package mod enabling, regulation file management,
and path handling consistency.
"""

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from me3_manager.core.nexus_metadata import NexusMetadataManager
from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
from me3_manager.utils.path_utils import PathUtils


class ModType(Enum):
    """Simplified mod types: all mods live in folders."""

    DLL = "dll"  # Individual DLL files within mod folders
    FOLDER = "folder"  # Mod folders (can contain DLLs, game assets, both, or configs)


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
    advanced_options: dict[str, Any] = None
    parent_package: str | None = None
    is_container: bool = False
    child_count: int = 0

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
        self.acceptable_folders = ACCEPTABLE_FOLDERS

    def _ensure_package_entry(
        self,
        config_data: dict,
        mod_name: str,
        normalized_path: str,
        initial_enabled: bool = True,
    ) -> dict:
        """
        Ensure a package entry exists in the config data.
        Returns the existing or newly created entry.
        """
        packages = config_data.get("packages", [])

        # Check for existing entry
        for package in packages:
            if isinstance(package, dict):
                if package.get("id") == mod_name:
                    return package
                path = package.get("path") or package.get("source")
                if path and self._normalize_path(path) == normalized_path:
                    return package

        # Create new entry
        entry = {
            "id": mod_name,
            "path": normalized_path,
        }
        if not initial_enabled:
            entry["enabled"] = False

        packages.append(entry)
        config_data["packages"] = packages
        return entry

    def _normalize_path(self, path_str: str) -> str:
        """
        Normalize path to use forward slashes consistently.
        This fixes the path consistency issue between enable/disable operations.
        """
        return PathUtils.normalize(path_str)

    def _analyze_folder_content(self, folder_path: Path) -> tuple[bool, bool]:
        """
        Analyze folder content to determine properties.
        Returns: (has_regulation, has_mod_content)
        """
        has_regulation = (folder_path / "regulation.bin").exists() or (
            folder_path / "regulation.bin.disabled"
        ).exists()

        has_mod_content = has_regulation or any(
            (folder_path / acceptable).exists()
            for acceptable in self.acceptable_folders
        )

        return has_regulation, has_mod_content

    def get_all_mods(self, game_name: str) -> dict[str, ModInfo]:
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

        # Reconcile pending mods using metadata
        if self._reconcile_pending_mods(game_name, config_data):
            self._write_improved_config(profile_path, config_data, game_name)

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

    def _get_config_key_for_mod(self, mod_path: str, game_name: str) -> str:
        """
        Get the correct config key for a mod path, using the same logic for both
        scanning and enabling/disabling operations.
        """
        mod_path_obj = Path(mod_path)
        mods_dir = self.config_manager.get_mods_dir(game_name)
        mods_dir_name = self.config_manager.games[game_name]["mods_dir"]

        # Check if we're using a custom profile
        is_custom_profile = mods_dir != (
            self.config_manager.config_root / mods_dir_name
        )

        if is_custom_profile:
            # Custom profiles are IN the mods directory, so relative paths are direct
            prefix = ""
        else:
            # Default profiles live in a parallel directory, so they need the mods folder name prefix
            prefix = f"{mods_dir_name}/"

        try:
            # Try to get relative path from mods directory
            relative_path = mod_path_obj.relative_to(mods_dir)
            # Combine prefix + relative path (e.g. "eldenring-mods/Mod.dll" or just "Mod.dll")
            return self._normalize_path(f"{prefix}{relative_path}")
        except ValueError:
            # External mod - use absolute path
            return self._normalize_path(str(mod_path_obj.resolve()))

    def _find_native_entry(
        self, natives: list[dict], config_key: str
    ) -> tuple[dict | None, int]:
        """
        Find a native entry by config key with normalized path comparison.
        Returns (entry, index) or (None, -1) if not found.
        """
        normalized_search_key = config_key.replace("\\", "/")

        for i, native in enumerate(natives):
            if isinstance(native, dict) and "path" in native:
                existing_path = native.get("path", "").replace("\\", "/")
                if existing_path == normalized_search_key:
                    return native, i
        return None, -1

    def _get_nexus_id_from_link(self, link: str) -> int | None:
        """Extract mod ID from Nexus link."""
        import re

        try:
            # Pattern: .../mods/123...
            match = re.search(r"/mods/(\d+)", link)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _reconcile_pending_mods(self, game_name: str, config_data: dict) -> bool:
        """
        Match pending profile entries to installed mods using Nexus metadata.
        Returns True if changes were made.
        """
        pending_entries = []
        natives = config_data.get("natives", [])

        # Identify pending entries
        for native in natives:
            if (
                isinstance(native, dict)
                and not native.get("path")
                and native.get("nexus_link")
            ):
                mod_id = self._get_nexus_id_from_link(native["nexus_link"])
                if mod_id:
                    pending_entries.append((mod_id, native))

        if not pending_entries:
            return False

        try:
            metadata_manager = NexusMetadataManager(
                self.config_manager.config_root, game_name
            )
            updates = False
            game_domain = (
                self.config_manager.get_game_nexus_domain(game_name) or "eldenring"
            )

            for mod_id, native in pending_entries:
                domain = game_domain
                if "/nexusmods.com/" in native["nexus_link"]:
                    try:
                        parts = native["nexus_link"].split("/nexusmods.com/")
                        if len(parts) > 1:
                            domain = parts[1].split("/")[0]
                    except IndexError:
                        pass

                cached = metadata_manager.get_cached_for_mod(domain, mod_id)
                if cached and cached.local_mod_path:
                    local_path = Path(cached.local_mod_path)
                    if local_path.exists():
                        config_key = self._get_config_key_for_mod(
                            str(local_path), game_name
                        )
                        native["path"] = config_key
                        updates = True

        except Exception:
            return False

        return updates

    def _scan_internal_mods(
        self,
        game_name: str,
        mods_dir: Path,
        enabled_status: dict,
        advanced_options: dict,
    ) -> dict[str, ModInfo]:
        """Scan filesystem for mods."""
        mods = {}
        active_regulation_mod = self._get_active_regulation_mod(mods_dir)

        for folder in mods_dir.iterdir():
            if (
                not folder.is_dir()
                or folder.name == self.config_manager.games[game_name]["mods_dir"]
            ):
                continue

            if folder.name.lower() in [f.lower() for f in self.acceptable_folders]:
                continue

            mod_path = str(folder)
            has_regulation, has_mod_content = self._analyze_folder_content(folder)
            regulation_active = has_regulation and folder.name == active_regulation_mod

            folder_mod_info = ModInfo(
                path=mod_path,
                name=folder.name,
                mod_type=ModType.FOLDER,
                status=ModStatus.ENABLED
                if enabled_status.get(folder.name, False)
                else ModStatus.DISABLED,
                is_external=False,
                has_regulation=has_regulation,
                regulation_active=regulation_active,
                is_container=not has_mod_content,
                advanced_options=advanced_options.get(folder.name, {}),
            )
            mods[mod_path] = folder_mod_info

            try:
                for subfolder in folder.rglob("*"):
                    if not subfolder.is_dir():
                        continue

                    if subfolder.name.lower() in [
                        f.lower() for f in self.acceptable_folders
                    ]:
                        continue

                    has_acceptable_content = any(
                        child.is_dir()
                        and child.name.lower()
                        in [f.lower() for f in self.acceptable_folders]
                        for child in subfolder.iterdir()
                    )

                    if has_acceptable_content:
                        subfolder_path = str(subfolder)

                        if subfolder_path == mod_path:
                            continue

                        rel_path = subfolder.relative_to(folder)
                        display_name = (
                            f"{folder.name}/{str(rel_path).replace(chr(92), '/')}"
                        )

                        has_regulation, _ = self._analyze_folder_content(subfolder)
                        regulation_active = (
                            has_regulation and (subfolder / "regulation.bin").exists()
                        )

                        subfolder_mod_info = ModInfo(
                            path=subfolder_path,
                            name=display_name,
                            mod_type=ModType.FOLDER,
                            status=ModStatus.ENABLED
                            if enabled_status.get(display_name, False)
                            else ModStatus.DISABLED,
                            is_external=False,
                            has_regulation=has_regulation,
                            regulation_active=regulation_active,
                            parent_package=folder.name,
                            advanced_options=advanced_options.get(display_name, {}),
                        )
                        mods[subfolder_path] = subfolder_mod_info
            except (PermissionError, OSError):
                pass

            try:
                for dll_file in folder.rglob("*.dll"):
                    dll_path = str(dll_file)
                    config_key = self._get_config_key_for_mod(dll_path, game_name)
                    display_name = f"{folder.name}/{dll_file.stem}"

                    dll_mod_info = ModInfo(
                        path=dll_path,
                        name=display_name,
                        mod_type=ModType.DLL,
                        status=ModStatus.ENABLED
                        if enabled_status.get(config_key, False)
                        else ModStatus.DISABLED,
                        is_external=False,
                        parent_package=folder.name,
                        advanced_options=advanced_options.get(config_key, {}),
                    )
                    mods[dll_path] = dll_mod_info
            except (PermissionError, OSError):
                continue

        # Calculate child count for all mods
        parent_children_map = {}
        for mod in mods.values():
            if mod.parent_package:
                parent_children_map[mod.parent_package] = (
                    parent_children_map.get(mod.parent_package, 0) + 1
                )

        # Update child_count in mod infos
        for _path, mod in mods.items():
            if mod.mod_type == ModType.FOLDER and mod.name in parent_children_map:
                mod.child_count = parent_children_map[mod.name]

        return mods

    def _scan_nested_mods(
        self,
        game_name: str,
        mods_dir: Path,
        enabled_status: dict,
        advanced_options: dict,
    ) -> dict[str, ModInfo]:
        """Deprecated - merged into _scan_internal_mods.

        Kept for compatibility but returns empty dict.
        """
        return {}

    def _get_active_regulation_mod(self, mods_dir: Path) -> str | None:
        """Find which mod currently has the active regulation.bin file"""
        for folder in mods_dir.iterdir():
            if folder.is_dir() and (folder / "regulation.bin").exists():
                return folder.name
        return None

    def _get_external_mods(
        self, game_name: str, enabled_status: dict, advanced_options: dict
    ) -> dict[str, ModInfo]:
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

        for stored_path in tracked_paths:
            normalized_path = self._normalize_path(stored_path)
            path_obj = Path(normalized_path)
            path_exists = path_obj.exists()
            is_directory = path_exists and path_obj.is_dir()
            is_dll = normalized_path.lower().endswith(".dll")

            if path_exists:
                if is_directory:
                    mod_type = ModType.FOLDER
                    mod_name = path_obj.name

                    has_regulation, has_mod_content = self._analyze_folder_content(
                        path_obj
                    )
                    regulation_active = (path_obj / "regulation.bin").exists()
                    is_container = not has_mod_content

                    enabled = enabled_status.get(
                        normalized_path, False
                    ) or enabled_status.get(mod_name, False)
                    advanced = advanced_options.get(
                        normalized_path
                    ) or advanced_options.get(mod_name, {})
                else:
                    mod_type = ModType.DLL
                    mod_name = path_obj.stem
                    has_regulation = False
                    regulation_active = False
                    is_container = False
                    enabled = enabled_status.get(normalized_path, False)
                    advanced = advanced_options.get(normalized_path, {})
            else:
                mod_type = ModType.DLL if is_dll else ModType.FOLDER
                mod_name = path_obj.stem if mod_type == ModType.DLL else path_obj.name
                has_regulation = False
                regulation_active = False
                is_container = False  # Default missing to false
                enabled = enabled_status.get(
                    normalized_path, False
                ) or enabled_status.get(mod_name, False)
                advanced = advanced_options.get(
                    normalized_path
                ) or advanced_options.get(mod_name, {})

            status = (
                ModStatus.MISSING
                if not path_exists
                else (ModStatus.ENABLED if enabled else ModStatus.DISABLED)
            )

            mod_info = ModInfo(
                path=normalized_path,
                name=mod_name,
                mod_type=mod_type,
                status=status,
                is_external=True,
                has_regulation=has_regulation,
                regulation_active=regulation_active,
                is_container=is_container,
                advanced_options=advanced,
            )

            mods[normalized_path] = mod_info

        return mods

    def _parse_enabled_status(
        self, config_data: dict, game_name: str
    ) -> dict[str, bool]:
        """Parse enabled status from profile config.

        A mod entry is considered enabled unless it explicitly sets `enabled = false`.
        This allows preserving advanced options while toggling mods on/off.
        """
        enabled_status = {}

        # Parse natives - if present in config, it's enabled
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                if native.get("enabled", True) is False:
                    continue
                path = native["path"]
                # Ensure path is normalized
                normalized_path = path.replace("\\", "/")

                # Use the same key format as in _scan_internal_mods for consistency
                if Path(normalized_path).is_absolute():
                    # External mod - use full normalized path
                    enabled_status[normalized_path] = True
                else:
                    # Internal mod - use the normalized path format
                    enabled_status[normalized_path] = True

        # Parse packages - if present in config, it's enabled
        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                if package.get("enabled", True) is False:
                    continue
                pkg_id = package["id"]
                # Skip the main mods directory package
                if pkg_id != self.config_manager.games[game_name]["mods_dir"]:
                    enabled_status[pkg_id] = True

                raw_path = package.get("path") or package.get("source")
                if raw_path:
                    normalized_path = self._normalize_path(str(raw_path))
                    if Path(normalized_path).is_absolute():
                        enabled_status[normalized_path] = True

        # Special case: If a folder is NOT in packages but contains enabled natives,
        # it should be considered enabled for UI purposes (display as green).
        # This handles native-only mods that aren't registered as packages.
        mods_dir = self.config_manager.get_mods_dir(game_name)
        if mods_dir.exists():
            for folder in mods_dir.iterdir():
                if not folder.is_dir():
                    continue

                folder_name = folder.name
                if folder_name not in enabled_status:
                    # Check for child DLLs
                    try:
                        for dll in folder.rglob("*.dll"):
                            config_key = self._get_config_key_for_mod(
                                str(dll), game_name
                            )
                            if enabled_status.get(config_key):
                                enabled_status[folder_name] = True
                                break
                    except (PermissionError, OSError):
                        pass

        return enabled_status

    def _parse_advanced_options(self, config_data: dict) -> dict[str, dict]:
        """Parse advanced options from profile config"""
        advanced_options = {}

        # Parse natives advanced options
        for native in config_data.get("natives", []):
            if isinstance(native, dict) and "path" in native:
                path = native["path"]
                # Ensure path is normalized
                normalized_path = path.replace("\\", "/")

                options = {
                    k: v for k, v in native.items() if k not in ["path", "enabled"]
                }
                if options:
                    # Use the normalized path as key
                    if Path(normalized_path).is_absolute():
                        advanced_options[normalized_path] = options
                    else:
                        # Use the normalized path format
                        advanced_options[normalized_path] = options

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
                    raw_path = package.get("path") or package.get("source")
                    if raw_path:
                        normalized_path = self._normalize_path(str(raw_path))
                        if Path(normalized_path).is_absolute():
                            advanced_options[normalized_path] = options

        return advanced_options

    def _cleanup_orphaned_entries(
        self, game_name: str, current_mods: dict[str, ModInfo]
    ):
        """Clean up orphaned entries from profile and tracking"""
        profile_path = self.config_manager.get_profile_path(game_name)
        config_data = self.config_manager._parse_toml_config(profile_path)

        # Get current mod config keys using the helper function
        current_config_keys = set()
        current_package_names = set()
        current_external_paths = set()

        for mod_path, mod_info in current_mods.items():
            if mod_info.is_external:
                norm_path = self._normalize_path(mod_path)
                current_external_paths.add(norm_path)
                # For external DLLs, also track as config key
                if mod_info.mod_type == ModType.DLL:
                    config_key = self._get_config_key_for_mod(mod_path, game_name)
                    current_config_keys.add(config_key)
            elif mod_info.mod_type == ModType.DLL:
                # Internal nested DLLs
                config_key = self._get_config_key_for_mod(mod_path, game_name)
                current_config_keys.add(config_key)
            else:  # FOLDER mods
                current_package_names.add(mod_info.name)

        # Clean up natives using normalized path comparison
        valid_natives = []
        for native in config_data.get("natives", []):
            # Keep if it has no path but has nexus_link (pending)
            if (
                isinstance(native, dict)
                and not native.get("path")
                and native.get("nexus_link")
            ):
                valid_natives.append(native)
                continue

            if isinstance(native, dict) and "path" in native:
                normalized_path = self._normalize_path(native["path"])
                if (
                    normalized_path in current_config_keys
                    or normalized_path in current_external_paths
                ):
                    valid_natives.append(native)

        # Clean up packages (keep main mods dir and tracked externals)
        valid_packages = []
        main_mods_dir = self.config_manager.games[game_name]["mods_dir"]

        for package in config_data.get("packages", []):
            if isinstance(package, dict) and "id" in package:
                pkg_id = package["id"]
                raw_path = package.get("path") or package.get("source")
                normalized_path = self._normalize_path(raw_path) if raw_path else None

                if (
                    pkg_id == main_mods_dir
                    or pkg_id in current_package_names
                    or (
                        normalized_path is not None
                        and (
                            normalized_path in current_external_paths
                            or normalized_path in current_config_keys
                            or any(
                                p.lower() == normalized_path.lower()
                                for p in current_external_paths
                            )
                        )
                    )
                ):
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
    ) -> tuple[bool, str]:
        """
        Set mod enabled status with improved logic.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)
            profile_path = self.config_manager.get_profile_path(game_name)
            config_data = self.config_manager._parse_toml_config(profile_path)

            if mod_path_obj.is_dir():
                # IMPROVEMENT: If the folder is a "container" (native-only mod),
                # toggling it should toggle its child DLLs instead of adding it to packages.
                has_regulation, has_mod_content = self._analyze_folder_content(
                    mod_path_obj
                )

                if not has_mod_content:
                    # Native-only mod: toggle all contained DLLs
                    modified = False
                    try:
                        for dll in mod_path_obj.rglob("*.dll"):
                            self._set_native_enabled(
                                config_data, str(dll), enabled, game_name
                            )
                            modified = True
                    except (PermissionError, OSError):
                        pass

                    if modified:
                        success, msg = (
                            True,
                            f"Toggled native mods in {mod_path_obj.name}",
                        )
                    else:
                        success, msg = False, "No native mods found to toggle"
                else:
                    # Regular package mod: add/remove from packages
                    success, msg = self._set_package_enabled(
                        config_data, str(mod_path_obj), enabled, game_name
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

    def enable_native_with_options(
        self, game_name: str, mod_path: str, options: dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """
        Enable a native (DLL) mod with additional options from a profile.

        This is used when installing mods from hosted profiles to preserve
        settings like load_early.

        Args:
            game_name: Name of the game
            mod_path: Path to the DLL mod
            options: Optional dict of options to apply (e.g., load_early=True)

        Returns:
            (success, message) tuple
        """
        try:
            profile_path = self.config_manager.get_profile_path(game_name)
            config_data = self.config_manager._parse_toml_config(profile_path)

            success, msg = self._set_native_enabled(
                config_data, mod_path, True, game_name, extra_options=options
            )

            if success:
                self._write_improved_config(profile_path, config_data, game_name)
                return True, f"Successfully enabled {Path(mod_path).name} with options"
            return False, msg

        except Exception as e:
            return False, f"Error enabling mod with options: {str(e)}"

    def _set_native_enabled(
        self,
        config_data: dict,
        mod_path: str,
        enabled: bool,
        game_name: str,
        extra_options: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Set enabled status for a native (DLL) mod with consistent path handling.

        Args:
            config_data: The profile config dictionary
            mod_path: Path to the DLL mod
            enabled: Whether to enable or disable
            game_name: Name of the game
            extra_options: Optional dict of additional options to merge (e.g., load_early)
        """
        natives = config_data.get("natives", [])

        # Use helper function for consistent config key generation
        config_key = self._get_config_key_for_mod(mod_path, game_name)

        # Find existing entry using helper function
        native_entry, native_index = self._find_native_entry(natives, config_key)

        if enabled:
            if native_entry is None:
                # Create new entry with optional extra options
                native_entry = {"path": config_key}
                if extra_options:
                    for key, value in extra_options.items():
                        if key not in ("path", "enabled"):
                            native_entry[key] = value
                natives.append(native_entry)
                config_data["natives"] = natives
                return True, "Created new native entry"
            else:
                # Entry already exists - re-enable if needed
                if native_entry.get("enabled", True) is False:
                    # Keep the entry (preserves advanced options), just toggle enabled on
                    native_entry.pop("enabled", None)
                    config_data["natives"] = natives
                    return True, "Re-enabled native entry"
                # Merge extra_options if provided (for existing entries)
                if extra_options:
                    for key, value in extra_options.items():
                        if key not in ("path", "enabled"):
                            native_entry[key] = value
                    config_data["natives"] = natives
                return True, "Native entry already exists"
        else:
            if native_entry is not None:
                # Preserve entry + advanced options, just mark disabled
                native_entry["enabled"] = False
                config_data["natives"] = natives
                return True, "Disabled native entry"
            else:
                # Nothing to disable
                return True, "Mod was already disabled"

    def _set_package_enabled(
        self, config_data: dict, mod_path: str, enabled: bool, game_name: str
    ) -> tuple[bool, str]:
        """Set enabled status for a package (folder) mod with improved logic"""
        packages = config_data.get("packages", [])
        if not isinstance(packages, list):
            packages = []
            config_data["packages"] = packages

        mod_path_obj = Path(mod_path)

        # Check if this is a nested folder by looking it up in current mods
        # to get its display name (which includes parent path)
        mod_name = mod_path_obj.name
        all_mods = self.get_all_mods(game_name)
        if mod_path in all_mods:
            mod_info = all_mods[mod_path]
            # For nested folders, use the display name which includes parent path
            # e.g., "ERR - ELDEN RING Reforged/ERRv2.1.2.3/mod"
            if mod_info.parent_package and mod_info.mod_type == ModType.FOLDER:
                mod_name = mod_info.name
            # Otherwise use the simple folder name

        # Use the shared helper to generate the consistent config key/path
        # This handles custom profiles (relative path) vs default profiles (prefix)
        # and external mods (absolute path) automatically.
        normalized_package_path = self._get_config_key_for_mod(
            str(mod_path_obj.resolve()), game_name
        )

        package_entry = None
        for package in packages:
            if not isinstance(package, dict) or "id" not in package:
                continue
            existing_id = package.get("id")
            existing_path_raw = package.get("path") or package.get("source")
            existing_path_normalized = (
                self._normalize_path(existing_path_raw) if existing_path_raw else None
            )

            if existing_id == mod_name or (
                existing_path_normalized == normalized_package_path
            ):
                package_entry = package
                break

        if enabled:
            if package_entry is None:
                package_entry = {
                    "id": mod_name,
                    "path": normalized_package_path,
                    "load_after": [],
                    "load_before": [],
                }
                packages.append(package_entry)
                config_data["packages"] = packages
                # Enforce single active regulation on enable
                try:
                    if mod_path_obj.is_dir():
                        folders = self._candidate_regulation_folders(game_name)
                        other_active = self._find_other_active_regulation(
                            folders, mod_path_obj
                        )
                        if other_active is not None:
                            self._disable_folder_regulation(mod_path_obj)
                        else:
                            self._enable_folder_regulation(mod_path_obj)
                except Exception:
                    pass
                return True, "Created new package entry"
            else:
                updated = False
                # Ensure enabled flag is cleared (enabled by default)
                if package_entry.get("enabled", True) is False:
                    package_entry.pop("enabled", None)
                    updated = True
                current_path = package_entry.get("path") or package_entry.get("source")
                current_normalized = (
                    self._normalize_path(current_path)
                    if current_path is not None
                    else None
                )
                if current_normalized != normalized_package_path:
                    package_entry["path"] = normalized_package_path
                    package_entry.pop("source", None)
                    updated = True

                if updated:
                    config_data["packages"] = packages
                    # Enforce single active regulation when path changes
                    try:
                        if mod_path_obj.is_dir():
                            folders = self._candidate_regulation_folders(game_name)
                            other_active = self._find_other_active_regulation(
                                folders, mod_path_obj
                            )
                            if other_active is not None:
                                self._disable_folder_regulation(mod_path_obj)
                            else:
                                self._enable_folder_regulation(mod_path_obj)
                    except Exception:
                        pass
                    return True, "Updated package entry"

                return True, "Package entry already exists"
        else:
            if package_entry is not None:
                # Preserve entry + advanced options, just mark disabled
                package_entry["enabled"] = False
                config_data["packages"] = packages
                # Disable regulation when disabling a package
                try:
                    if mod_path_obj.is_dir():
                        self._disable_folder_regulation(mod_path_obj)
                except Exception:
                    pass
                return True, "Disabled package entry"
            else:
                return True, "Package was already disabled"

    def set_container_enabled(
        self, game_name: str, container_path: str, enabled: bool
    ) -> tuple[bool, str]:
        """
        Enable/Disable a container (package) mod and all its children.
        When disabling, it remembers which children were enabled.
        When enabling, it restores the previous state (or enables all if no history).
        """
        try:
            mod_path_obj = Path(container_path)
            profile_path = self.config_manager.get_profile_path(game_name)
            config_data = self.config_manager._parse_toml_config(profile_path)

            # Find the container entry in packages
            mod_name = mod_path_obj.name
            normalized_path = self._get_config_key_for_mod(
                str(mod_path_obj.resolve()), game_name
            )

            container_entry = None
            packages = config_data.get("packages", [])

            for pkg in packages:
                if pkg.get("id") == mod_name or pkg.get("path") == normalized_path:
                    container_entry = pkg
                    break

            # Get all mods to identify children
            all_mods = self.get_all_mods(game_name)
            children = []

            for _path, mod_info in all_mods.items():
                if mod_info.parent_package == mod_name:
                    children.append(mod_info)

            # if not children:
            #     return False, "Container has no children"

            if not enabled:
                # DISABLE: Save state of currently enabled children
                enabled_children = []
                for child in children:
                    if child.status == ModStatus.ENABLED:
                        # Store relative path or ID
                        enabled_children.append(child.name)

                # Update container entry with saved state
                # Update container entry with saved state
                if container_entry is None:
                    container_entry = self._ensure_package_entry(
                        config_data, mod_name, normalized_path, initial_enabled=False
                    )

                container_entry["saved_child_state"] = enabled_children
                container_entry["enabled"] = False  # Mark container as disabled

                # Disable all children (BATCH UPDATE on shared config_data)
                for child in children:
                    child_path_obj = Path(child.path)
                    if child_path_obj.is_dir():
                        self._set_package_enabled(
                            config_data, child.path, False, game_name
                        )
                    else:
                        self._set_native_enabled(
                            config_data, child.path, False, game_name
                        )

                self._write_improved_config(profile_path, config_data, game_name)
                return True, f"Disabled container and {len(children)} children"

            else:
                # ENABLE: Restore state

                # Ensure container entry exists in config
                # Ensure container entry exists in config
                if container_entry is None:
                    container_entry = self._ensure_package_entry(
                        config_data, mod_name, normalized_path, initial_enabled=True
                    )

                # Mark container as explicitly enabled (remove disabled flag)
                if isinstance(container_entry, dict) or hasattr(container_entry, "pop"):
                    container_entry.pop("enabled", None)

                saved_state = container_entry.get("saved_child_state", None)
                container_enabled_count = 0

                if saved_state is not None:
                    # Restore specific children (BATCH UPDATE)
                    for child in children:
                        should_enable = child.name in saved_state
                        child_path_obj = Path(child.path)

                        if child_path_obj.is_dir():
                            self._set_package_enabled(
                                config_data, child.path, should_enable, game_name
                            )
                        else:
                            self._set_native_enabled(
                                config_data, child.path, should_enable, game_name
                            )

                        if should_enable:
                            container_enabled_count += 1
                    msg = f"Restored container with {container_enabled_count} enabled mods"
                else:
                    # Enable ALL children (default behavior) (BATCH UPDATE)
                    for child in children:
                        child_path_obj = Path(child.path)
                        if child_path_obj.is_dir():
                            self._set_package_enabled(
                                config_data, child.path, True, game_name
                            )
                        else:
                            self._set_native_enabled(
                                config_data, child.path, True, game_name
                            )
                        container_enabled_count += 1

                    if not children:
                        msg = "Enabled container (empty)"
                    else:
                        msg = f"Enabled container and all {container_enabled_count} children"

                # Update config to save container enabled state
                self._write_improved_config(profile_path, config_data, game_name)
                return True, msg

        except Exception as e:
            return False, f"Error toggling container: {str(e)}"

    def _get_tracked_external_package_paths(self, game_name: str) -> list[Path]:
        """Return tracked external mod paths that are directories."""
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

        package_paths: list[Path] = []
        for stored_path in tracked_paths:
            path_obj = Path(stored_path)
            if path_obj.is_dir():
                package_paths.append(path_obj)

        return package_paths

    def _candidate_regulation_folders(self, game_name: str) -> list[Path]:
        """Collect unique package folders (internal + tracked external) for regulation checks."""
        mods_dir = self.config_manager.get_mods_dir(game_name)
        candidate_folders: list[Path] = []

        if mods_dir.exists():
            for folder in mods_dir.iterdir():
                if folder.is_dir():
                    candidate_folders.append(folder)

        candidate_folders.extend(self._get_tracked_external_package_paths(game_name))

        seen: set[Path] = set()
        unique_candidates: list[Path] = []
        for folder in candidate_folders:
            try:
                resolved = folder.resolve()
            except Exception:
                continue

            if resolved in seen:
                continue

            seen.add(resolved)
            unique_candidates.append(resolved)

        return unique_candidates

    def _find_other_active_regulation(
        self, folders: list[Path], exclude_folder: Path
    ) -> Path | None:
        """Return a folder (not exclude_folder) that has an active regulation.bin, if any."""
        try:
            exclude_resolved = exclude_folder.resolve()
        except Exception:
            exclude_resolved = exclude_folder

        for folder in folders:
            if folder == exclude_resolved:
                continue
            if (folder / "regulation.bin").exists():
                return folder
        return None

    def _disable_folder_regulation(self, folder: Path) -> None:
        """Rename regulation.bin to regulation.bin.disabled in the given folder, if present."""
        regulation_file = folder / "regulation.bin"
        disabled_file = folder / "regulation.bin.disabled"
        if regulation_file.exists():
            try:
                regulation_file.rename(disabled_file)
            except Exception:
                pass

    def _enable_folder_regulation(self, folder: Path) -> bool:
        """Ensure regulation.bin is active in the given folder. Returns True if active after call."""
        disabled_file = folder / "regulation.bin.disabled"
        regulation_file = folder / "regulation.bin"
        if disabled_file.exists():
            try:
                disabled_file.rename(regulation_file)
                return True
            except Exception:
                return False
        return regulation_file.exists()

    def set_regulation_active(self, game_name: str, mod_path: str) -> tuple[bool, str]:
        """
        Set which mod should have the active regulation.bin file.
        Only one regulation file can be active at a time.
        """
        try:
            target_folder = Path(mod_path)

            if not target_folder.exists():
                return False, f"Mod folder not found: {mod_path}"

            if not target_folder.is_dir():
                return False, "Regulation files can only be managed for folder mods"

            mods_dir = self.config_manager.get_mods_dir(game_name)
            candidate_folders: list[Path] = []

            if mods_dir.exists():
                # Recursively search for ALL folders (including nested) that might have regulation.bin
                for folder in mods_dir.rglob("*"):
                    if folder.is_dir():
                        candidate_folders.append(folder)

            candidate_folders.extend(
                self._get_tracked_external_package_paths(game_name)
            )

            target_resolved = target_folder.resolve()
            seen: set[Path] = set()
            unique_candidates: list[Path] = []

            for folder in candidate_folders:
                try:
                    resolved = folder.resolve()
                except Exception:
                    continue

                if resolved in seen:
                    continue

                seen.add(resolved)
                unique_candidates.append(resolved)

            for folder in unique_candidates:
                if folder == target_resolved:
                    continue

                regulation_file = folder / "regulation.bin"
                disabled_file = folder / "regulation.bin.disabled"

                if regulation_file.exists():
                    try:
                        regulation_file.rename(disabled_file)
                    except Exception:
                        continue

            disabled_file = target_resolved / "regulation.bin.disabled"
            regulation_file = target_resolved / "regulation.bin"

            if disabled_file.exists():
                disabled_file.rename(regulation_file)
                return True, f"Set {target_folder.name} as active regulation mod"

            if regulation_file.exists():
                return True, f"{target_folder.name} regulation file is already active"

            return False, f"No regulation file found for {target_folder.name}"

        except Exception as e:
            return False, f"Error setting regulation active: {str(e)}"

    def disable_all_regulations(self, game_name: str) -> tuple[bool, str]:
        """
        Disable regulation.bin across all mods (internal and tracked external)
        by renaming any active files to regulation.bin.disabled. This leaves
        no active regulation.
        """
        try:
            mods_dir = self.config_manager.get_mods_dir(game_name)
            if not mods_dir or not mods_dir.exists():
                return False, "Mods directory not found"

            disabled_count = 0

            # Recursively search for ALL folders with regulation.bin (including nested)
            for folder in mods_dir.rglob("*"):
                try:
                    if not folder.is_dir():
                        continue
                    regulation_file = folder / "regulation.bin"
                    disabled_file = folder / "regulation.bin.disabled"
                    if regulation_file.exists():
                        regulation_file.rename(disabled_file)
                        disabled_count += 1
                except Exception:
                    # Ignore failures on a single folder and continue
                    continue

            # Also check tracked external mods
            external_paths = self._get_tracked_external_package_paths(game_name)
            for folder in external_paths:
                try:
                    if not folder.is_dir():
                        continue
                    regulation_file = folder / "regulation.bin"
                    disabled_file = folder / "regulation.bin.disabled"
                    if regulation_file.exists():
                        regulation_file.rename(disabled_file)
                        disabled_count += 1
                except Exception:
                    continue

            # Even if nothing changed, it's a successful no-op
            return True, f"Regulation disabled ({disabled_count} file(s))"
        except Exception as e:
            return False, f"Error disabling regulation: {str(e)}"

    def add_external_mod(self, game_name: str, mod_path: str) -> tuple[bool, str]:
        """
        Add an external mod with robust error handling.
        Returns (success, message)
        """
        try:
            mod_path_obj = Path(mod_path)

            if not mod_path_obj.exists():
                return False, f"Mod path not found: {mod_path}"

            mods_dir = self.config_manager.get_mods_dir(game_name)

            # Prevent tracking items already inside the mods directory
            try:
                mod_path_obj.resolve().relative_to(mods_dir.resolve())
                return False, "This mod is already in the game's mods folder"
            except ValueError:
                pass

            is_valid = False
            if mod_path_obj.is_file():
                if mod_path_obj.suffix.lower() != ".dll":
                    return (
                        False,
                        "Only DLL files or mod folders can be added as external mods",
                    )
                is_valid = True
            elif mod_path_obj.is_dir():
                if not self._is_valid_mod_folder(mod_path_obj):
                    return (
                        False,
                        "Selected folder does not appear to be a valid mod package",
                    )
                is_valid = True

            if not is_valid:
                return (
                    False,
                    "Only DLL files or mod folders can be added as external mods",
                )

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

    def _is_dll_only_wrapper_folder(self, folder: Path) -> bool:
        """
        Check if a folder is a "DLL-only wrapper folder" - a folder that only
        contains DLLs and their associated config folders (no other mod content).

        These folders are created when installing DLL-only mods from Nexus and
        should be fully deleted when the DLL is removed.

        Allows common documentation/config files that don't indicate game mod content.
        """
        if not folder.is_dir():
            return False

        # Extensions that are allowed in DLL-only mod folders (not game content)
        allowed_extensions = {
            ".dll",  # The DLL itself
            ".exe",  # Mod launchers/tools (e.g., nrsc_launcher.exe)
            ".ini",  # Config files
            ".toml",  # Config files (like settings.toml)
            ".json",  # Config files
            ".txt",  # README, LICENSE, etc.
            ".md",  # Documentation
            ".me3",  # ME3 profile files
            ".log",  # Log files
            ".cfg",  # Config files
        }

        # Filenames that are always allowed (case-insensitive)
        allowed_filenames = {
            "readme",
            "license",
            "changelog",
            "credits",
            "readme.txt",
            "license.txt",
            "changelog.txt",
            "readme.md",
            "license.md",
            "changelog.md",
        }

        dll_stems = set()
        has_game_content = False

        for item in folder.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                name_lower = item.name.lower()

                if ext == ".dll":
                    dll_stems.add(item.stem)
                elif ext in allowed_extensions or name_lower in allowed_filenames:
                    # Allowed non-DLL files - skip
                    continue
                else:
                    # Has game content files (like .pak, .bin, etc.)
                    has_game_content = True
                    break
            elif item.is_dir():
                # Check if it's a config folder for a DLL (will verify after scan)
                # For now, just continue and verify later
                pass

        if has_game_content or not dll_stems:
            return False

        # Verify all folders are either config folders for DLLs or don't contain game files
        for item in folder.iterdir():
            if item.is_dir():
                # Config folders named after DLLs are always ok
                if item.name in dll_stems:
                    continue
                # Check if this subfolder contains game content
                if self._folder_has_game_content(item):
                    return False

        return True

    def _folder_has_game_content(self, folder: Path) -> bool:
        """Check if a folder contains game content files (like .pak, .bin, etc.)."""
        game_extensions = {".pak", ".bin", ".bdt", ".bhd", ".dcx", ".flver", ".tpf"}
        try:
            for item in folder.rglob("*"):
                if item.is_file() and item.suffix.lower() in game_extensions:
                    return True
        except Exception:
            pass
        return False

    def _folder_has_no_game_content(self, folder: Path) -> bool:
        """
        Check if a folder has no game content and can be safely deleted.

        This is used for cleanup after deleting nested mods. A folder can be
        deleted if it only contains non-essential files like:
        - Executables (.exe) - mod launchers/tools
        - Config files (.ini, .toml, .json, .cfg)
        - Documentation (.txt, .md)
        - Empty directories
        """
        if not folder.is_dir():
            return False

        # Game content extensions that should NOT be deleted
        game_extensions = {".pak", ".bin", ".bdt", ".bhd", ".dcx", ".flver", ".tpf"}

        try:
            for item in folder.rglob("*"):
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in game_extensions:
                        return False  # Has game content
        except Exception:
            return False

        return True

    @staticmethod
    def _remove_readonly(func, path, exc_info):
        """
        Error handler for shutil.rmtree to handle read-only files on Windows.
        If the error is due to access rights, it tries to change the file to writable and retry.
        """
        import errno
        import os
        import stat

        # Check if the error is an access error
        if (
            func in (os.rmdir, os.remove, os.unlink)
            and exc_info[1].errno == errno.EACCES
        ):
            # Change the file to be writable
            os.chmod(path, stat.S_IWRITE)
            # Retry the function
            func(path)
        else:
            # Re-raise the exception if it's not a permission error
            raise

    def remove_mod(self, game_name: str, mod_path: str) -> tuple[bool, str]:
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
            wrapper_folder = None

            if mod_path_obj.is_file() and mod_path_obj.suffix.lower() == ".dll":
                try:
                    relative_path = mod_path_obj.relative_to(mods_dir)
                    # If relative path has more than one part, it's nested
                    if len(relative_path.parts) > 1:
                        is_nested_mod = True
                        # Check if the parent folder is a DLL-only wrapper
                        wrapper_folder = mod_path_obj.parent
                except ValueError:
                    pass

            # Create metadata manager access
            nexus_metadata = NexusMetadataManager(
                self.config_manager.config_root,
                game_name,
                legacy_roots=[
                    self.config_manager.config_root,
                    self.config_manager.get_mods_dir(game_name),
                ],
            )

            # Helper to remove metadata for a path
            def _remove_meta(path_to_remove: Path):
                try:
                    # Metadata uses normalized paths, but maybe absolute or relative depending on type
                    # Try both forms to be safe

                    # 1. Absolute resolved path (most consistent key)
                    resolved = str(path_to_remove.resolve())
                    nexus_metadata.remove_mod_metadata(resolved)

                    # 2. Key format used in _get_config_key_for_mod
                    config_key = self._get_config_key_for_mod(
                        str(path_to_remove), game_name
                    )
                    if config_key != resolved:
                        nexus_metadata.remove_mod_metadata(config_key)
                except Exception:
                    pass

            if is_nested_mod:
                # Check if the DLL is in a "DLL-only wrapper folder"
                if wrapper_folder and self._is_dll_only_wrapper_folder(wrapper_folder):
                    # Delete the entire wrapper folder
                    shutil.rmtree(wrapper_folder, onerror=self._remove_readonly)
                    _remove_meta(mod_path_obj)  # Remove metadata for the DLL

                    deleted_folder_name = wrapper_folder.name

                    # Check if parent folders should also be cleaned up
                    parent = wrapper_folder.parent
                    while parent != mods_dir and parent.is_relative_to(mods_dir):
                        # If parent is empty, delete it
                        remaining = list(parent.iterdir())
                        if not remaining:
                            parent.rmdir()
                            deleted_folder_name = parent.name
                            parent = parent.parent
                        elif self._folder_has_no_game_content(parent):
                            # Parent only has non-essential files (exe, txt, etc.)
                            shutil.rmtree(parent, onerror=self._remove_readonly)
                            deleted_folder_name = parent.name
                            break
                        else:
                            break

                    return True, f"Deleted DLL mod folder: {deleted_folder_name}"
                else:
                    # True nested mod inside a package - just remove from profile
                    _remove_meta(mod_path_obj)  # Remove metadata for the nested mod
                    return True, f"Removed nested mod from profile: {mod_path_obj.name}"
            elif mod_path_obj.is_dir():
                # Handle folder mod
                if mod_path_obj.parent == mods_dir:
                    # Top-level folder mod - delete from filesystem
                    shutil.rmtree(mod_path_obj, onerror=self._remove_readonly)
                    _remove_meta(mod_path_obj)
                    return True, f"Deleted folder mod: {mod_path_obj.name}"
                elif mods_dir in mod_path_obj.parents:
                    # Nested folder mod inside mods directory - delete from filesystem
                    shutil.rmtree(mod_path_obj, onerror=self._remove_readonly)
                    _remove_meta(mod_path_obj)

                    # Clean up empty parent folders
                    parent = mod_path_obj.parent
                    while parent != mods_dir and parent.is_relative_to(mods_dir):
                        try:
                            remaining = list(parent.iterdir())
                            if not remaining:
                                parent.rmdir()
                                parent = parent.parent
                            else:
                                break
                        except (PermissionError, OSError):
                            break

                    return True, f"Deleted nested folder mod: {mod_path_obj.name}"
                else:
                    # External folder mod - just untrack it
                    self.config_manager.untrack_external_mod(game_name, mod_path)
                    _remove_meta(mod_path_obj)
                    return True, f"Untracked external mod: {mod_path_obj.name}"
            else:
                # Handle DLL mod
                if mod_path_obj.parent == mods_dir:
                    # Internal DLL mod - delete from filesystem
                    try:
                        mod_path_obj.unlink()
                    except PermissionError:
                        # Try to remove read-only attribute
                        import os
                        import stat

                        os.chmod(mod_path_obj, stat.S_IWRITE)
                        mod_path_obj.unlink()

                    _remove_meta(mod_path_obj)  # Remove metadata for the DLL

                    # Also remove config folder if it exists
                    config_folder = mod_path_obj.parent / mod_path_obj.stem
                    if config_folder.is_dir():
                        shutil.rmtree(config_folder, onerror=self._remove_readonly)

                    return True, f"Deleted DLL mod: {mod_path_obj.name}"
                else:
                    # External DLL mod - just untrack it
                    self.config_manager.untrack_external_mod(game_name, mod_path)
                    _remove_meta(mod_path_obj)  # Remove metadata for the external DLL
                    return True, f"Untracked external mod: {mod_path_obj.name}"

        except Exception as e:
            return False, f"Error removing mod: {str(e)}"

    def _write_improved_config(
        self, config_path: Path, config_data: dict[str, Any], game_name: str
    ):
        """Write TOML config file using tomlkit for proper formatting"""
        # Import TomlProfileWriter here to avoid circular imports
        from me3_manager.core.profiles import TomlProfileWriter

        # Filter out the main mods directory package before writing
        main_mods_dirs = {
            game_info["mods_dir"] for game_info in self.config_manager.games.values()
        }

        # Create a copy of config_data to avoid modifying the original
        filtered_config = config_data.copy()

        # Filter packages
        if "packages" in filtered_config:
            filtered_config["packages"] = [
                p
                for p in filtered_config["packages"]
                if p.get("id") not in main_mods_dirs
            ]

        # Use the new TomlProfileWriter with array of tables syntax
        TomlProfileWriter.write_profile(config_path, filtered_config, game_name)

    def has_advanced_options(self, mod_info: ModInfo) -> bool:
        """Check if a mod has any advanced options configured"""
        if not mod_info.advanced_options:
            return False

        # Check for any advanced options beyond basic ones
        advanced_keys = [
            "optional",
            "load_early",
            "initializer",
            "finalizer",
            "load_before",
            "load_after",
        ]
        return any(
            key in mod_info.advanced_options and mod_info.advanced_options[key]
            for key in advanced_keys
        )

    def update_advanced_options(
        self, game_name: str, mod_path: str, new_options: dict, is_folder_mod: bool
    ):
        """Updates the advanced options for a specific mod in its profile file."""
        profile_path = self.config_manager.get_profile_path(game_name)
        config_data = self.config_manager._parse_toml_config(profile_path)
        mod_name = Path(mod_path).name

        target_entry = None
        if is_folder_mod:
            packages = config_data.get("packages", [])
            for pkg in packages:
                if pkg.get("id") == mod_name:
                    target_entry = pkg
                    break
        else:  # Native DLL mod
            # Use the same helper function for consistent config key generation
            config_key = self._get_config_key_for_mod(mod_path, game_name)

            natives = config_data.get("natives", [])

            for native in natives:
                native_path = self._normalize_path(native.get("path", ""))

                if native_path == config_key:
                    target_entry = native
                    break

        if target_entry is not None:
            # Purge all old advanced option keys from the entry
            keys_to_purge = [
                "load_before",
                "load_after",
                "optional",
                "load_early",
                "initializer",
                "finalizer",
            ]
            for key in keys_to_purge:
                if key in target_entry:
                    del target_entry[key]

            # Add the new options back, but ONLY if they are not the default value.

            for key, value in new_options.items():
                if key == "optional" and value is True:
                    target_entry[key] = True
                elif key == "load_early" and value is True:
                    target_entry[key] = True
                elif key in ["load_before", "load_after"] and value:
                    target_entry[key] = value
                elif (
                    key not in ["optional", "load_before", "load_after"]
                    and value is not None
                ):
                    target_entry[key] = value

            # Write the entire modified configuration back to disk

            self._write_improved_config(profile_path, config_data, game_name)
