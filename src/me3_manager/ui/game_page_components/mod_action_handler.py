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

    def toggle_mod(self, mod_path: str, enabled: bool):
        """Toggles a mod's enabled state."""
        success, message = self.mod_manager.set_mod_enabled(
            self.game_page.game_name, mod_path, enabled
        )

        if success:
            self.game_page.load_mods(reset_page=False)
            self.game_page.status_label.setText(message)
            QTimer.singleShot(
                2000, lambda: self.game_page.status_label.setText(tr("status_ready"))
            )
        else:
            QMessageBox.warning(self.game_page, tr("toggle_mod_error_title"), message)

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

            if success:
                self.game_page.load_mods(reset_page=False)
                self.game_page.status_label.setText(message)
                QTimer.singleShot(
                    2000,
                    lambda: self.game_page.status_label.setText(tr("status_ready")),
                )
            else:
                QMessageBox.warning(self.game_page, tr("delete_error_title"), message)

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

            if success:
                self.game_page.status_label.setText(message)
                self.game_page.load_mods(reset_page=False)
                QTimer.singleShot(
                    3000,
                    lambda: self.game_page.status_label.setText(tr("status_ready")),
                )
            else:
                QMessageBox.warning(
                    self.game_page, tr("add_external_mod_error_title"), message
                )

    def activate_regulation_mod(self, mod_path: str):
        """Activates the regulation.bin file for a specific mod."""
        mod_name = Path(mod_path).name
        # If the clicked mod is already the active regulation, interpret the action as disabling all
        mod_info = self.game_page.mod_infos.get(mod_path)
        if getattr(mod_info, "regulation_active", False):
            success, message = self.mod_manager.disable_all_regulations(
                self.game_page.game_name
            )
        else:
            success, message = self.mod_manager.set_regulation_active(
                self.game_page.game_name, mod_name
            )

        if success:
            self.game_page.load_mods(reset_page=False)
            self.game_page.status_label.setText(message)
            QTimer.singleShot(
                3000, lambda: self.game_page.status_label.setText(tr("status_ready"))
            )
        else:
            QMessageBox.warning(self.game_page, tr("regulation_error_title"), message)
