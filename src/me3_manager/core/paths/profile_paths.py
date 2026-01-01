"""
Shared path utilities for ME3 profile configuration.
Provides common path resolution used by multiple modules.
"""

import os
import sys
from pathlib import Path


def get_me3_profiles_root() -> Path:
    """Get the ME3 profiles root directory based on platform.

    Returns:
        Path to the profiles directory (e.g., .../me3/config/profiles)
    """
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "garyttierney" / "me3" / "config" / "profiles"
        return (
            Path.home()
            / "AppData"
            / "Local"
            / "garyttierney"
            / "me3"
            / "config"
            / "profiles"
        )

    # Linux/macOS
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "me3" / "profiles"
    return Path.home() / ".config" / "me3" / "profiles"
