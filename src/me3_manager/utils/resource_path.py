import os
import sys
from pathlib import Path


def _discover_base_dir() -> Path:
    """
    Discover a stable base directory for resources in both dev and frozen builds.
    Priority:
      1) PyInstaller's _MEIPASS
      2) Project root discovered by walking up from this file until 'resources' exists
      3) Current working directory
    """
    # 1) PyInstaller bundle location
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    except Exception:
        pass

    # 2) Walk up from this file to find a 'resources' directory at some ancestor
    try:
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "resources"
            if candidate.exists() and candidate.is_dir():
                return parent
    except Exception:
        pass

    # 3) Fallback to current working directory
    return Path(os.path.abspath("."))


def resource_path(relative_path: str) -> str:
    base_path = _discover_base_dir()
    return str((base_path / relative_path).resolve())
