"""
Dialog Window Management Handler for GamePage.

Responsible for creating, showing, and processing the results from various
secondary dialogs, such as the config editor, advanced options, game options,
and profile settings.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QDialog, QMessageBox

from me3_manager.core.mod_manager import ModType
from me3_manager.ui.advanced_mod_options import AdvancedModOptionsDialog
from me3_manager.ui.config_editor import ConfigEditorDialog
from me3_manager.ui.game_options_dialog import GameOptionsDialog
from me3_manager.ui.profile_editor import ProfileEditor
from me3_manager.ui.profile_settings_dialog import ProfileSettingsDialog
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class DialogHandler:
    """Handles the creation and management of all dialog windows for GamePage."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self.mod_manager = game_page.mod_manager
        self.game_name = game_page.game_name

    def open_profile_editor(self):
        """Opens the main profile editor dialog."""
        editor_dialog = ProfileEditor(
            self.game_name, self.config_manager, self.game_page
        )
        if editor_dialog.exec() == QDialog.DialogCode.Accepted:
            self.game_page.status_label.setText(
                tr("profile_saved_status", game_name=self.game_name)
            )
            self.game_page.load_mods()
            self.game_page._update_status(tr("status_ready"))

    def open_config_editor(self, mod_path: str):
        """Opens the config file editor for a specific mod."""
        mod_name = Path(mod_path).stem
        initial_config_path = self.config_manager.get_mod_config_path(
            self.game_name, mod_path
        )
        dialog = ConfigEditorDialog(mod_name, initial_config_path, self.game_page)
        if dialog.exec():
            final_path = dialog.current_path
            if final_path and final_path != initial_config_path:
                self.config_manager.set_mod_config_path(
                    self.game_name, mod_path, str(final_path)
                )
                self.game_page._update_status(
                    tr("config_path_saved_status", mod_name=mod_name)
                )

    def open_advanced_options(self, mod_path: str):
        """Opens the advanced load order options dialog for a mod."""
        try:
            mod_name = Path(mod_path).name
            mod_info = self.game_page.mod_infos.get(mod_path)
            if not mod_info:
                raise ValueError(tr("mod_info_not_found_error"))

            is_folder_mod = mod_info.mod_type == ModType.PACKAGE
            available_mod_names = [
                info.name
                for path, info in self.game_page.mod_infos.items()
                if (info.mod_type == mod_info.mod_type) and (path != mod_path)
            ]
            dialog = AdvancedModOptionsDialog(
                mod_path=mod_path,
                mod_name=mod_name,
                is_folder_mod=is_folder_mod,
                current_options=mod_info.advanced_options,
                available_mods=available_mod_names,
                parent=self.game_page,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_options = dialog.get_options()
                # Use the mod_manager to apply the changes
                self.mod_manager.update_advanced_options(
                    self.game_name, mod_path, new_options, is_folder_mod
                )
                self.game_page.load_mods(reset_page=False)
                self.game_page._update_status(
                    tr("advanced_options_updated_status", mod_name=mod_name)
                )
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("advanced_options_error_title"),
                tr("advanced_options_open_failed_msg", error=str(e)),
            )

    def open_game_options(self):
        """Opens the game-specific options dialog."""
        try:
            dialog = GameOptionsDialog(
                self.game_name, self.config_manager, self.game_page
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("game_options_error_title"),
                tr("game_options_open_failed_msg", error=str(e)),
            )

    def open_profile_settings(self):
        """Opens the profile-specific settings dialog."""
        try:
            dialog = ProfileSettingsDialog(
                self.game_name, self.config_manager, self.game_page
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.game_page.status_label.setText(
                    tr("profile_settings_saved_status", game_name=self.game_name)
                )
                self.game_page.load_mods(reset_page=False)
                self.game_page._update_status(tr("status_ready"))
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("profile_settings_error_title"),
                tr("profile_settings_open_failed_msg", error=str(e)),
            )
