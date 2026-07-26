"""
Shared path utilities for ME3 profile configuration.
Provides common path resolution used by multiple modules.
"""

import json
import os
import sys
from pathlib import Path


def get_default_os_profiles_root() -> Path:
    """Get the standard OS ME3 profiles root directory based on platform."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "garyttierney" / "me3" / "config" / "profiles"

    # Linux/macOS
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "me3" / "profiles"


def get_manager_settings_path() -> Path:
    """Get the permanent system location of manager_settings.json."""
    return get_default_os_profiles_root().parent / "manager_settings.json"


def get_custom_me3_location() -> Path | None:
    """Read custom ME3 installation location from manager_settings.json if configured."""
    settings_file = get_manager_settings_path()
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_loc = data.get("custom_me3_location")
                if custom_loc and isinstance(custom_loc, str) and custom_loc.strip():
                    p = Path(custom_loc.strip())
                    if p.name.lower() == "bin":
                        p = p.parent
                    return p
        except Exception:
            pass
    return None


def get_me3_profiles_root() -> Path:
    """Get the ME3 profiles root directory based on platform or custom settings.

    Returns:
        Path to the profiles directory (e.g., .../me3/config/profiles)
    """
    custom_root = get_custom_me3_location()
    if custom_root:
        return custom_root / "config" / "profiles"
    return get_default_os_profiles_root()


def get_me3_root(profiles_root: Path | None = None) -> Path:
    """Get the base ME3 directory (e.g., .../me3)."""
    if profiles_root:
        root = profiles_root
    else:
        custom_root = get_custom_me3_location()
        if custom_root:
            return custom_root
        root = get_default_os_profiles_root()

    if root.parent.name == "config":
        return root.parent.parent
    return root.parent


def get_me3_bin_dir(profiles_root: Path | None = None) -> Path:
    """Get the directory where portable ME3 binary is installed (e.g., .../me3/bin)."""
    return get_me3_root(profiles_root) / "bin"
