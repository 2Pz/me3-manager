"""
Profile Settings Dialog for ME3 Manager.
Provides a user-friendly interface for configuring profile-level settings like savefile and start_online.
"""

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from me3_manager.utils.translator import tr


class ProfileSettingsDialog(QDialog):
    """Dialog for configuring profile-level settings (savefile, start_online, etc.)"""

    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.current_settings = {}

        self.setWindowTitle(tr("profile_settings_title", game_name=game_name))
        self.setModal(True)
        self.resize(600, 400)

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel(tr("profile_settings_title", game_name=self.game_name))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)

        # Description
        desc = QLabel(tr("profile_settings_description"))
        desc.setStyleSheet("color: #cccccc; margin-bottom: 16px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Save File Settings group
        savefile_group = QGroupBox(tr("savefile_settings_group"))
        savefile_group.setStyleSheet(self._get_group_style())
        savefile_layout = QFormLayout(savefile_group)
        savefile_layout.setSpacing(12)

        # Custom savefile checkbox
        self.custom_savefile_cb = QCheckBox(tr("use_custom_savefile"))
        self.custom_savefile_cb.setStyleSheet(self._get_checkbox_style())
        self.custom_savefile_cb.toggled.connect(self.on_custom_savefile_toggled)
        savefile_layout.addRow("", self.custom_savefile_cb)

        # Savefile name and extension layout
        savefile_input_layout = QHBoxLayout()

        # Savefile name input
        self.savefile_edit = QLineEdit()
        self.savefile_edit.setPlaceholderText(tr("savefile_placeholder"))
        self.savefile_edit.setStyleSheet(self._get_lineedit_style())
        self.savefile_edit.setEnabled(False)
        savefile_input_layout.addWidget(self.savefile_edit, 1)

        # Extension dropdown
        self.extension_combo = QComboBox()
        self.extension_combo.addItem(tr("extension_sl2_vanilla"), ".sl2")
        self.extension_combo.addItem(tr("extension_co2_seamless"), ".co2")
        self.extension_combo.setStyleSheet(self._get_combobox_style())
        self.extension_combo.setEnabled(False)
        self.extension_combo.setMinimumWidth(150)
        savefile_input_layout.addWidget(self.extension_combo)

        savefile_layout.addRow(tr("savefile_name_label"), savefile_input_layout)

        # Savefile info
        savefile_info = QLabel(tr("savefile_info"))
        savefile_info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 8px;")
        savefile_info.setWordWrap(True)
        savefile_layout.addWidget(savefile_info)

        layout.addWidget(savefile_group)

        # Online Settings group
        online_group = QGroupBox(tr("online_settings_group"))
        online_group.setStyleSheet(self._get_group_style())
        online_layout = QFormLayout(online_group)
        online_layout.setSpacing(12)

        # Start online checkbox
        self.start_online_cb = QCheckBox(tr("start_online_checkbox"))
        self.start_online_cb.setStyleSheet(self._get_checkbox_style())
        online_layout.addRow(tr("start_online_label"), self.start_online_cb)

        # Online info
        online_info = QLabel(tr("start_online_info"))
        online_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        online_info.setWordWrap(True)
        online_layout.addWidget(online_info)

        layout.addWidget(online_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton(tr("cancel_button"))
        self.cancel_btn.setStyleSheet(self._get_cancel_button_style())
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton(tr("save_button"))
        self.save_btn.setStyleSheet(self._get_save_button_style())
        self.save_btn.clicked.connect(self.save_settings)

        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def load_current_settings(self):
        """Load current profile settings"""
        try:
            # Parse the current profile to get settings
            profile_path = self.config_manager.get_profile_path(self.game_name)
            if profile_path.exists():
                config_data = self.config_manager._parse_toml_config(profile_path)

                # Load savefile setting
                savefile = config_data.get("savefile", "")
                if savefile:
                    self.custom_savefile_cb.setChecked(True)

                    # Parse filename and extension
                    if savefile.endswith(".co2"):
                        filename = savefile[:-4]  # Remove .co2
                        self.extension_combo.setCurrentIndex(1)  # co2 is index 1
                    elif savefile.endswith(".sl2"):
                        filename = savefile[:-4]  # Remove .sl2
                        self.extension_combo.setCurrentIndex(0)  # sl2 is index 0
                    else:
                        filename = savefile
                        self.extension_combo.setCurrentIndex(0)  # Default to sl2

                    self.savefile_edit.setText(filename)
                    self.on_custom_savefile_toggled(True)
                else:
                    self.custom_savefile_cb.setChecked(False)
                    self.on_custom_savefile_toggled(False)

                # Load start_online setting
                start_online = config_data.get("start_online", False)
                self.start_online_cb.setChecked(bool(start_online))

                self.current_settings = config_data
            else:
                # Profile doesn't exist, use defaults
                self.custom_savefile_cb.setChecked(False)
                self.start_online_cb.setChecked(False)
                self.on_custom_savefile_toggled(False)
                self.current_settings = {}

        except Exception as e:
            QMessageBox.warning(
                self, tr("load_error"), tr("profile_load_error_msg", error=str(e))
            )

    def on_custom_savefile_toggled(self, checked):
        """Handle custom savefile checkbox toggle"""
        self.savefile_edit.setEnabled(checked)
        self.extension_combo.setEnabled(checked)
        if not checked:
            self.savefile_edit.clear()

    def save_settings(self):
        """Save the profile settings"""
        try:
            # Start with current settings to preserve other data
            updated_config = self.current_settings.copy()

            # Update savefile setting
            if self.custom_savefile_cb.isChecked():
                savefile_name = self.savefile_edit.text().strip()
                if not savefile_name:
                    QMessageBox.warning(
                        self,
                        tr("savefile_required_title"),
                        tr("savefile_required_message"),
                    )
                    return

                # Get selected extension
                selected_extension = self.extension_combo.currentData()

                # Remove any existing extension from the filename
                if savefile_name.endswith((".sl2", ".co2")):
                    savefile_name = savefile_name.rsplit(".", 1)[0]

                # Add the selected extension
                full_savefile_name = savefile_name + selected_extension

                # Validate savefile name
                if not self._is_valid_savefile_name(full_savefile_name):
                    QMessageBox.warning(
                        self,
                        tr("invalid_savefile_title"),
                        tr("invalid_savefile_message"),
                    )
                    return

                updated_config["savefile"] = full_savefile_name
            else:
                # Remove savefile setting if unchecked
                updated_config.pop("savefile", None)

            # Update start_online setting
            updated_config["start_online"] = self.start_online_cb.isChecked()

            # Write the updated profile
            profile_path = self.config_manager.get_profile_path(self.game_name)

            # Use the TOML profile writer to maintain proper formatting
            from me3_manager.core.profiles import TomlProfileWriter

            TomlProfileWriter.write_profile(
                profile_path, updated_config, self.game_name
            )

            QMessageBox.information(
                self, tr("save_success"), tr("profile_settings_save_success")
            )
            self.accept()

        except Exception as e:
            QMessageBox.warning(
                self, tr("save_error"), tr("profile_settings_save_error", error=str(e))
            )

    def _is_valid_savefile_name(self, filename: str) -> bool:
        """Validate savefile name"""
        if not filename:
            return False

        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            return False

        # Check length
        if len(filename) > 255:
            return False

        # Should have a valid extension for save files
        valid_extensions = [".sl2", ".co2"]
        if not any(filename.lower().endswith(ext) for ext in valid_extensions):
            # Auto-add .sl2 extension for Elden Ring-style games
            return True  # We'll add the extension in the save logic

        return True

    def _get_group_style(self):
        """Get group box stylesheet"""
        return """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #ffffff;
            }
        """

    def _get_checkbox_style(self):
        """Get checkbox stylesheet"""
        return """
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #106ebe;
                border-color: #106ebe;
            }
            QCheckBox::indicator:hover {
                border-color: #4d4d4d;
            }
        """

    def _get_lineedit_style(self):
        """Get line edit stylesheet"""
        return """
            QLineEdit {
                background-color: #3d3d3d;
                border: 2px solid #4d4d4d;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: #ffffff;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QLineEdit:hover {
                border-color: #5d5d5d;
            }
            QLineEdit:disabled {
                background-color: #2d2d2d;
                color: #666666;
                border-color: #3d3d3d;
            }
        """

    def _get_cancel_button_style(self):
        """Get cancel button stylesheet"""
        return """
            QPushButton {
                background-color: #666666;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
        """

    def _get_combobox_style(self):
        """Get combobox stylesheet"""
        return """
            QComboBox {
                background-color: #3d3d3d;
                border: 2px solid #4d4d4d;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: #ffffff;
                min-height: 20px;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox:hover {
                border-color: #5d5d5d;
            }
            QComboBox:disabled {
                background-color: #2d2d2d;
                color: #666666;
                border-color: #3d3d3d;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            QComboBox::down-arrow:disabled {
                border-top-color: #666666;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                border: 2px solid #4d4d4d;
                selection-background-color: #0078d4;
                color: #ffffff;
            }
        """

    def _get_save_button_style(self):
        """Get save button stylesheet"""
        return """
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """
