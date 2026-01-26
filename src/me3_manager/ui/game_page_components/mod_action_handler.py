"""
Mod Interaction Handler for GamePage.

This module handles direct user actions performed on individual mods, such as
enabling/disabling, deleting, adding external mods, and activating regulation files.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class ModActionHandler:
    """Handles direct user actions on mods like toggling, deleting, and adding."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.mod_manager = game_page.mod_manager

    def _handle_result(
        self, success: bool, message: str, error_title: str, delay_ms: int = 2000
    ):
        """
        Common handler for mod operation results.
        Shows status message on success, warning dialog on failure.
        """
        if success:
            self.game_page.status_label.setText(message)
            self.game_page.load_mods(reset_page=False)
            QTimer.singleShot(
                delay_ms,
                lambda: self.game_page.status_label.setText(tr("status_ready")),
            )
        else:
            QMessageBox.warning(self.game_page, tr(error_title), message)

    def toggle_mod(self, mod_path: str, enabled: bool):
        """Toggles a mod's enabled state."""
        # Check if it is a container mod
        mod_info = self.game_page.mod_infos.get(mod_path)

        # Only treat strict containers (no content) as containers for group toggling.
        # Mods that have content AND children (e.g. Boss Arena) should behave like normal mods.
        if mod_info and mod_info.is_container:
            success, message = self.mod_manager.set_container_enabled(
                self.game_page.game_name, mod_path, enabled
            )
        else:
            success, message = self.mod_manager.set_mod_enabled(
                self.game_page.game_name, mod_path, enabled
            )
        self._handle_result(success, message, "toggle_mod_error_title")

    def delete_mod(self, mod_path: str):
        """Deletes a mod after user confirmation."""
        mod_name = Path(mod_path).name
        reply = QMessageBox.question(
            self.game_page,
            tr("delete_mod_title"),
            tr("delete_mod_confirm_question", mod_name=mod_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.mod_manager.remove_mod(
                self.game_page.game_name, mod_path
            )
            self._handle_result(success, message, "delete_error_title")

    def add_external_mod(self):
        """Opens a file dialog to add a new external DLL mod."""
        file_name, _ = QFileDialog.getOpenFileName(
            self.game_page,
            tr("select_external_mod_title"),
            str(Path.home()),
            tr("dll_files_filter"),
        )
        if file_name:
            success, message = self.mod_manager.add_external_mod(
                self.game_page.game_name, file_name
            )
            self._handle_result(success, message, "add_external_mod_error_title", 3000)

    def add_external_package_mod(self):
        """Opens a folder dialog to add a new external package mod."""
        folder_path = QFileDialog.getExistingDirectory(
            self.game_page,
            tr("select_external_package_mod_title"),
            str(Path.home()),
        )

        if folder_path:
            success, message = self.mod_manager.add_external_mod(
                self.game_page.game_name, folder_path
            )
            self._handle_result(success, message, "add_external_mod_error_title", 3000)

    def activate_regulation_mod(self, mod_path: str):
        """Activates the regulation.bin file for a specific mod."""
        # If the clicked mod is already the active regulation, interpret the action as disabling all
        mod_info = self.game_page.mod_infos.get(mod_path)
        if getattr(mod_info, "regulation_active", False):
            success, message = self.mod_manager.disable_all_regulations(
                self.game_page.game_name
            )
        else:
            success, message = self.mod_manager.set_regulation_active(
                self.game_page.game_name, mod_path
            )
        self._handle_result(success, message, "regulation_error_title", 3000)
