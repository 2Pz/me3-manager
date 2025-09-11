"""
General Utility Handler for GamePage.

Provides miscellaneous helper functions and utility actions, such as opening file
explorer paths, setting custom executable paths, and validating dropped files.
"""

import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


def is_frozen():
    """Check if running as a PyInstaller frozen executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _open_path(parent_widget: QWidget, path: Path):
    """Safely opens a folder path in the native file explorer."""
    try:
        if is_frozen():
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(path)], shell=True, env=env)
            else:
                subprocess.run(["xdg-open", str(path)], env=env)
        else:
            url = QUrl.fromLocalFile(str(path))
            if not QDesktopServices.openUrl(url):
                raise Exception("QDesktopServices failed to open URL.")
    except Exception as e:
        QMessageBox.warning(
            parent_widget,
            tr("open_folder_error"),
            tr("open_folder_error_msg", path=path, e=str(e)),
        )


class PageUtils:
    """A class for utility methods that require access to the GamePage instance."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self.game_name = game_page.game_name

    def open_mods_folder(self):
        """Opens the root mods directory for the current game."""
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        if not mods_dir.exists():
            QMessageBox.warning(
                self.game_page,
                tr("folder_not_found_title"),
                tr("mods_dir_not_exist_msg", mods_dir=mods_dir),
            )
            return
        _open_path(self.game_page, mods_dir)

    def open_mod_folder(self, mod_path: str):
        """Opens the parent folder of a specific mod file/directory."""
        folder_path = Path(mod_path).parent
        _open_path(self.game_page, folder_path)

    def is_valid_drop(self, paths: list[Path]) -> bool:
        """Checks if the dropped files/folders are valid for installation."""
        paths_to_check = deque(paths)
        while paths_to_check:
            path = paths_to_check.popleft()
            if not path.exists():
                continue
            if path.is_file():
                if (
                    path.suffix.lower() in [".dll", ".me3"]
                    or path.name.lower() == "regulation.bin"
                ):
                    return True
            elif path.is_dir():
                if path.name in self.game_page.acceptable_folders:
                    return True
                try:
                    for item in path.iterdir():
                        paths_to_check.append(item)
                except OSError:
                    continue
        return False

    def set_custom_exe_path(self):
        """Opens dialogs to guide the user in setting a custom game executable."""
        QMessageBox.warning(
            self.game_page,
            "Non-Recommended Action",
            "It is recommended to avoid setting a custom game executable path unless ME3 cannot detect your game installation automatically.\n\nOnly use this option if your game is installed in a non-standard location.",
        )
        current_path = self.config_manager.get_game_exe_path(self.game_name)
        if current_path:
            reply = QMessageBox.question(
                self.game_page,
                "Custom Executable Path",
                f"Current custom executable path:\n{current_path}\n\nDo you want to change it?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Reset,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            if reply == QMessageBox.StandardButton.Reset:
                self.config_manager.set_game_exe_path(self.game_name, None)
                self.game_page._update_status(
                    f"Cleared custom executable path for {self.game_name}"
                )
                return

        expected_exe_name = self.config_manager.get_game_executable_name(self.game_name)
        if not expected_exe_name:
            QMessageBox.critical(
                self.game_page,
                "Configuration Error",
                f"Expected executable name for '{self.game_name}' is not defined.",
            )
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self.game_page,
            f"Select {self.game_name} Executable ({expected_exe_name})",
            str(Path.home()),
            "Executable Files (*.exe);;All Files (*)",
        )
        if file_name:
            selected_path = Path(file_name)
            if selected_path.name.lower() != expected_exe_name.lower():
                # ... (error message logic)
                return
            try:
                self.config_manager.set_game_exe_path(self.game_name, file_name)
                self.game_page._update_status(
                    f"Set custom executable path for {self.game_name}"
                )
            except Exception as e:
                QMessageBox.warning(
                    self.game_page,
                    "Set Path Error",
                    f"Failed to set custom executable path: {str(e)}",
                )
