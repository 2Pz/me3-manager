"""
Archive extraction utilities.

Provides a unified interface for extracting various archive formats using patool.
Patool auto-detects format from file content and supports many formats including:
ZIP, RAR, 7z, TAR, GZIP, BZIP2, XZ, CAB, ISO, and many more.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)


def get_supported_extensions() -> frozenset[str]:
    """
    Get all archive extensions supported by patool.

    Returns a frozenset of extensions like {'.zip', '.rar', '.7z', ...}
    Falls back to common extensions if patool is not available.
    """
    try:
        import patoolib

        extensions: set[str] = set()
        # patoolib.ArchiveFormats maps format names to their extensions
        for _fmt, data in patoolib.ArchiveFormats.items():
            if data and "extensions" in data:
                for ext in data["extensions"]:
                    # Normalize to lowercase with leading dot
                    if not ext.startswith("."):
                        ext = f".{ext}"
                    extensions.add(ext.lower())
        if extensions:
            return frozenset(extensions)
    except Exception as e:
        log.debug("Could not get patool extensions: %s", e)

    # Fallback to common formats
    return frozenset({".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"})


# Dynamically populated on module load
ARCHIVE_EXTENSIONS = get_supported_extensions()


def is_archive(path: Path) -> bool:
    """Check if a file is a supported archive format."""
    return path.is_file() and path.suffix.lower() in ARCHIVE_EXTENSIONS


def extract_archive(archive: Path, dest_dir: Path) -> bool:
    """
    Extract an archive to the destination directory.

    Uses patool which auto-detects format from file content (not extension).
    Falls back to Python's zipfile if patool is unavailable and file is a zip.

    Args:
        archive: Path to the archive file
        dest_dir: Directory to extract contents to

    Returns:
        True if extraction succeeded, False otherwise

    Raises:
        Exception: If extraction fails
    """
    # Try patool first - it auto-detects format from content, not extension
    try:
        return _extract_with_patool(archive, dest_dir)
    except ImportError:
        # patool not available, try zipfile as fallback for zip files
        log.warning("patool not available, trying zipfile fallback")
        return _extract_zip(archive, dest_dir)
    except Exception as e:
        # patool failed, try zipfile as fallback for actual zip files
        log.warning("patool extraction failed (%s), trying zipfile fallback", e)
        try:
            return _extract_zip(archive, dest_dir)
        except Exception:
            # Both failed, re-raise the original patool error
            raise e from None


def _extract_zip(archive: Path, dest_dir: Path) -> bool:
    """Extract a ZIP archive using Python's built-in zipfile module."""
    with zipfile.ZipFile(archive, "r") as z:
        z.extractall(dest_dir)
    return True


def _extract_with_patool(archive: Path, dest_dir: Path) -> bool:
    """Extract an archive using patool (auto-detects format from content)."""
    try:
        import patoolib
    except ImportError as e:
        log.error(
            "patool is not installed. Cannot extract %s archives.", archive.suffix
        )
        raise ImportError(
            f"patool is required to extract {archive.suffix} archives. "
            "Please install it with: pip install patool"
        ) from e

    # patool requires string paths
    patoolib.extract_archive(str(archive), outdir=str(dest_dir), verbosity=-1)
    return True
