from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo


class PathUtils:
    """
    Qt-friendly path helpers.
    - Normalization with forward slashes
    - Basic existence checks via QFileInfo
    """

    @staticmethod
    def normalize(path_str: str) -> str:
        if not path_str:
            return ""
        return str(Path(path_str)).replace("\\", "/")

    @staticmethod
    def exists(path_str: str) -> bool:
        info = QFileInfo(path_str)
        return info.exists()

    @staticmethod
    def is_file(path_str: str) -> bool:
        info = QFileInfo(path_str)
        return info.isFile()

    @staticmethod
    def is_dir(path_str: str) -> bool:
        info = QFileInfo(path_str)
        return info.isDir()
