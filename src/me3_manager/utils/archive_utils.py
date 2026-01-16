"""
Archive extraction utilities.

Provides a unified interface for extracting .zip, .rar, and .7z archives.
Optimized to use Python's built-in zipfile for ZIPs and native 7-Zip for others where possible,
falling back to patoolib for robustness.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

log = logging.getLogger(__name__)


# Supported extensions (strict)
ARCHIVE_EXTENSIONS = frozenset({".zip", ".rar", ".7z"})


def is_archive(path: Path) -> bool:
    """Check if a file is a supported archive format (.zip, .rar, .7z)."""
    return path.is_file() and path.suffix.lower() in ARCHIVE_EXTENSIONS


# Cached path to 7-Zip executable
_7ZIP_PATH: str | None = None


def _find_7zip() -> str | None:
    """
    Find 7-Zip executable path.
    Checks PATH first, then Windows Registry and common paths on Windows.
    """
    global _7ZIP_PATH
    if _7ZIP_PATH:
        return _7ZIP_PATH

    # 1. Check PATH (Works on Linux/macOS/Windows if added to PATH)
    # '7z' is the standard command name for p7zip-full on Linux and 7-Zip on Windows
    if shutil.which("7z"):
        _7ZIP_PATH = "7z"
        return _7ZIP_PATH

    # 2. Check Windows Registry and common paths
    if platform.system() == "Windows":
        # Registry lookup (like patool does)
        if winreg:
            try:
                keyname = r"SOFTWARE\7-Zip"
                # Check both 64-bit and 32-bit registry views
                for access_mask in [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]:
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            keyname,
                            0,
                            winreg.KEY_READ | access_mask,
                        ) as key:
                            path_val = winreg.QueryValueEx(key, "Path")[0]
                            exe_path = Path(path_val) / "7z.exe"
                            if exe_path.exists():
                                _7ZIP_PATH = str(exe_path)
                                return _7ZIP_PATH
                    except OSError:
                        continue
            except Exception:
                pass

        # Manual check of common installation paths
        candidates = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
        for path in candidates:
            if Path(path).exists():
                _7ZIP_PATH = path
                return _7ZIP_PATH

    return None


def extract_archive(archive: Path, dest_dir: Path) -> bool:
    """
    Extract an archive to the destination directory.

    Supported formats: .zip, .rar, .7z

    Args:
        archive: Path to the archive file
        dest_dir: Directory to extract contents to

    Returns:
        True if extraction succeeded, False otherwise

    Raises:
        ValueError: If archive format is not supported
        Exception: If extraction fails
    """
    suffix = archive.suffix.lower()

    if not is_archive(archive):
        # Strict checking
        raise ValueError(f"Unsupported archive format: {suffix}")

    # 1. Optimize for ZIP files - use built-in module
    if suffix == ".zip":
        try:
            return _extract_zip(archive, dest_dir)
        except Exception as e:
            log.warning("zipfile extraction failed (%s), trying 7-zip/patool", e)
            # Fallthrough to 7-Zip/patool

    # 2. Try direct 7-Zip extraction (faster than patool overhead)
    # Works for .rar, .7z, and failed .zip
    if _extract_with_7zip(archive, dest_dir):
        return True

    # 3. Fallback to patool (handles standard detection and other edge cases)
    return _extract_with_patool(archive, dest_dir)


def _extract_zip(archive: Path, dest_dir: Path) -> bool:
    """Extract a ZIP archive using Python's built-in zipfile module."""
    with zipfile.ZipFile(archive, "r") as z:
        z.extractall(dest_dir)
    return True


def _extract_with_7zip(archive: Path, dest_dir: Path) -> bool:
    """Attempt extraction using 7-Zip subprocess directly."""
    exe = _find_7zip()
    if not exe:
        return False

    try:
        # x: extract with full paths
        # -y: assume yes on all queries
        # -o{dir}: output directory (no space after -o)
        cmd = [exe, "x", "-y", f"-o{dest_dir}", str(archive)]

        if platform.system() == "Windows":
            creation_flags = subprocess.CREATE_NO_WINDOW
        else:
            creation_flags = 0

        # Suppress output unless error
        subprocess.check_call(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
        return True
    except Exception as e:
        log.debug("Direct 7-Zip extraction failed/skipped: %s", e)
        return False


def _extract_with_patool(archive: Path, dest_dir: Path) -> bool:
    """Extract an archive using patool (auto-detects format from content)."""
    try:
        import patoolib
    except ImportError:
        log.error(
            "patool is not installed. Cannot extract %s archives.", archive.suffix
        )
        raise

    # patool requires string paths
    # verbosity=-1 silences standard output
    patoolib.extract_archive(str(archive), outdir=str(dest_dir), verbosity=-1)
    return True
