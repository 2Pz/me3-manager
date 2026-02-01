"""
Download watcher for system-browser downloads.

Used as a compliant fallback when embedded webviews are blocked by Cloudflare/Turnstile.
We watch the user's Downloads folder for a newly completed archive and then install it.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from me3_manager.utils.archive_utils import ARCHIVE_EXTENSIONS

log = logging.getLogger(__name__)


def get_downloads_dir() -> Path:
    """
    Best-effort resolution of the user's Downloads directory.
    - Windows: %USERPROFILE%\\Downloads
    - Linux: XDG user-dirs if available, else ~/Downloads
    """
    if os.name == "nt":
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            # FOLDERID_Downloads
            FOLDERID_Downloads = "{374DE290-123F-4565-9164-39C4925E467B}"

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8),
                ]

            SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
            SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(GUID),
                wintypes.DWORD,
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p),
            ]

            u = uuid.UUID(FOLDERID_Downloads)
            guid = GUID()
            guid.Data1 = u.time_low
            guid.Data2 = u.time_mid
            guid.Data3 = u.time_hi_version
            for i in range(8):
                guid.Data4[i] = u.bytes[8 + i]

            path_ptr = ctypes.c_wchar_p()
            if (
                SHGetKnownFolderPath(
                    ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
                )
                == 0
            ):
                path = path_ptr.value
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                return Path(path)
        except Exception as e:
            log.warning("Failed to resolve Windows Downloads folder via API: %s", e)

        home = os.environ.get("USERPROFILE") or str(Path.home())
        return Path(home) / "Downloads"

    # Linux/macOS: prefer XDG user-dirs
    xdg_config = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    user_dirs = Path(xdg_config) / "user-dirs.dirs"
    if user_dirs.is_file():
        try:
            raw = user_dirs.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'XDG_DOWNLOAD_DIR="?([^"\n]+)"?', raw)
            if m:
                val = m.group(1).strip()
                val = val.replace("$HOME", str(Path.home()))
                return Path(val).expanduser()
        except Exception:
            pass

    return Path.home() / "Downloads"


class DownloadWatcher(QThread):
    """
    Watches a directory for a newly completed download.

    Emits:
      - found(file_path)
      - status(text)
      - failed(error_text)
    """

    found = Signal(str)
    status = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        directory: Path,
        allowed_exts: tuple[str, ...] | None = None,
        timeout_s: int = 600,
        parent=None,
    ):
        super().__init__(parent)
        self._dir = Path(directory)
        # Use ARCHIVE_EXTENSIONS if no specific extensions provided
        if allowed_exts is None:
            self._allowed_exts = tuple(e.lower() for e in ARCHIVE_EXTENSIONS)
        else:
            self._allowed_exts = tuple(e.lower() for e in allowed_exts)
        self._timeout_s = int(timeout_s)

    def run(self) -> None:
        start = time.time()
        if not self._dir.exists():
            self.failed.emit(f"Downloads folder not found: {self._dir}")
            return

        # Snapshot existing files (so we only consider new ones).
        baseline = {p.name for p in self._dir.iterdir() if p.is_file()}
        self.status.emit(f"Waiting for download in {self._dir}...")

        last_candidate: Path | None = None
        stable_count = 0
        last_size = -1

        while True:
            if self.isInterruptionRequested():
                self.failed.emit("Cancelled.")
                return

            if time.time() - start > self._timeout_s:
                self.failed.emit("Timed out waiting for browser download.")
                return

            try:
                files = [p for p in self._dir.iterdir() if p.is_file()]
            except Exception:
                time.sleep(0.5)
                continue

            # Ignore temp/in-progress extensions used by common browsers.
            in_progress_exts = {".crdownload", ".part", ".tmp"}
            completed = []
            for p in files:
                if p.name in baseline:
                    continue
                suf = p.suffix.lower()
                if suf in in_progress_exts:
                    continue
                if self._allowed_exts and suf not in self._allowed_exts:
                    continue
                completed.append(p)

            # Prefer newest completed file.
            if completed:
                try:
                    completed.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                except Exception:
                    pass
                candidate = completed[0]
            else:
                candidate = None

            if candidate is None:
                time.sleep(0.5)
                continue

            # Wait for size to stabilize to avoid racing with final write/rename.
            try:
                size = candidate.stat().st_size
            except Exception:
                time.sleep(0.5)
                continue

            if last_candidate != candidate:
                last_candidate = candidate
                stable_count = 0
                last_size = size
                self.status.emit(f"Detected download: {candidate.name} (finishing...)")
                time.sleep(0.5)
                continue

            if size == last_size and size > 0:
                stable_count += 1
            else:
                stable_count = 0
                last_size = size

            if stable_count >= 3:
                # One last sanity check: ensure no matching temp file still exists.
                temp_cr = candidate.with_suffix(candidate.suffix + ".crdownload")
                temp_part = candidate.with_suffix(candidate.suffix + ".part")
                if temp_cr.exists() or temp_part.exists():
                    time.sleep(0.5)
                    continue

                self.found.emit(str(candidate))
                return

            time.sleep(0.5)
