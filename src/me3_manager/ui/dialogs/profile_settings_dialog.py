"""
Profile Settings Dialog for ME3 Manager.
Provides a user-friendly interface for configuring profile-level settings like savefile and start_online.
"""

import json
import shutil
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from me3_manager.ui.dialogs.dialog_utils import (
    GameDialogBase,
    NoEnterLineEdit,
    StyleUtils,
)
from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr


class ProfileSettingsDialog(GameDialogBase):
    """Dialog for configuring profile-level settings (savefile, start_online, etc.)"""

    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(game_name, config_manager, parent)
        self.seamless_enabled = False
        self.resize(860, 660)

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel(tr("profile_settings_title", game_name=self.game_name))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)

        # Description
        desc = QLabel(tr("profile_settings_description"))
        desc.setStyleSheet("color: #cccccc; margin-bottom: 8px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Save File Settings group
        savefile_group = QGroupBox(tr("savefile_settings_group"))
        savefile_group.setStyleSheet(StyleUtils.get_group_style())
        savefile_layout = QVBoxLayout(savefile_group)
        savefile_layout.setSpacing(8)
        savefile_layout.setContentsMargins(12, 12, 12, 12)
        savefile_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Custom savefile checkbox
        self.custom_savefile_cb = QCheckBox(tr("use_custom_savefile"))
        self.custom_savefile_cb.setStyleSheet(StyleUtils.get_checkbox_style())
        self.custom_savefile_cb.toggled.connect(self.on_custom_savefile_toggled)
        savefile_layout.addWidget(self.custom_savefile_cb)

        # Savefile name and extension layout
        savefile_input_layout = QHBoxLayout()

        savefile_input_layout.addWidget(QLabel(tr("savefile_name_label")))

        # Savefile name input
        self.savefile_edit = NoEnterLineEdit()
        self.savefile_edit.setPlaceholderText(tr("savefile_placeholder"))
        self.savefile_edit.setStyleSheet(StyleUtils.get_lineedit_style())
        self.savefile_edit.setEnabled(False)
        savefile_input_layout.addWidget(self.savefile_edit, 1)

        # Extension dropdown
        self.extension_combo = QComboBox()
        self.extension_combo.addItem(tr("extension_sl2_vanilla"), ".sl2")
        self.extension_combo.addItem(tr("extension_co2_seamless"), ".co2")
        # FIXME: Disable .co2 (index 1) as it is not supported yet
        self.extension_combo.model().item(1).setEnabled(False)
        self.extension_combo.setStyleSheet(StyleUtils.get_combobox_style())
        self.extension_combo.setEnabled(False)
        self.extension_combo.setMinimumWidth(150)
        self.extension_combo.hide()  # Hidden until .co2 is supported
        savefile_input_layout.addWidget(self.extension_combo)

        savefile_layout.addLayout(savefile_input_layout)

        # Savefile info
        savefile_info = QLabel(tr("savefile_info"))
        savefile_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 4px;")
        savefile_info.setWordWrap(True)
        savefile_layout.addWidget(savefile_info)

        # Warning when custom savefile is not enabled
        self.savefile_warning = QLabel(tr("savefile_warning_recommend_custom"))
        self.savefile_warning.setStyleSheet(
            "color: #ff5555; font-size: 12px; font-weight: 600; margin-top: 6px;"
        )
        self.savefile_warning.setWordWrap(True)
        savefile_layout.addWidget(self.savefile_warning)

        # Online Settings group
        online_group = QGroupBox(tr("online_settings_group"))
        online_group.setStyleSheet(StyleUtils.get_group_style())
        online_layout = QVBoxLayout(online_group)
        online_layout.setSpacing(8)
        online_layout.setContentsMargins(12, 12, 12, 12)
        online_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Start online checkbox
        self.start_online_cb = QCheckBox(tr("start_online_checkbox"))
        self.start_online_cb.setStyleSheet(StyleUtils.get_checkbox_style())
        online_layout.addWidget(self.start_online_cb)

        # Online info
        online_info = QLabel(tr("start_online_info"))
        online_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 4px;")
        online_info.setWordWrap(True)
        online_layout.addWidget(online_info)

        # Compatibility Settings group
        compat_group = QGroupBox(tr("compatibility_settings_group"))
        compat_group.setStyleSheet(StyleUtils.get_group_style())
        compat_layout = QVBoxLayout(compat_group)
        compat_layout.setSpacing(8)
        compat_layout.setContentsMargins(12, 12, 12, 12)
        compat_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Disable Arxan checkbox
        self.disable_arxan_cb = QCheckBox(tr("disable_arxan_checkbox"))
        self.disable_arxan_cb.setStyleSheet(StyleUtils.get_checkbox_style())
        compat_layout.addWidget(self.disable_arxan_cb)

        # Disable Arxan info
        disable_arxan_info = QLabel(tr("disable_arxan_info"))
        disable_arxan_info.setStyleSheet(
            "color: #ffaa00; font-size: 11px; margin-top: 4px;"
        )
        disable_arxan_info.setWordWrap(True)
        compat_layout.addWidget(disable_arxan_info)

        compat_layout.addSpacing(8)

        # Memory Patch checkbox
        self.mem_patch_cb = QCheckBox(tr("mem_patch_checkbox"))
        self.mem_patch_cb.setStyleSheet(StyleUtils.get_checkbox_style())
        self.mem_patch_cb.toggled.connect(self.on_mem_patch_toggled)
        compat_layout.addWidget(self.mem_patch_cb)

        # Mem Patch info
        mem_patch_info = QLabel(tr("mem_patch_info"))
        mem_patch_info.setStyleSheet(
            "color: #ffaa00; font-size: 11px; margin-top: 4px;"
        )
        mem_patch_info.setWordWrap(True)
        compat_layout.addWidget(mem_patch_info)

        compat_layout.addSpacing(8)

        # Memory Patch Heap Size
        heap_layout = QHBoxLayout()
        heap_layout.addWidget(QLabel(tr("mem_patch_heap_size_label")))
        self.mem_patch_heap_size_spin = QSpinBox()
        self.mem_patch_heap_size_spin.setRange(0, 999999)
        self.mem_patch_heap_size_spin.setSpecialValueText(tr("default"))
        self.mem_patch_heap_size_spin.setStyleSheet(
            StyleUtils._get_input_widget_style("QSpinBox")
        )
        self.mem_patch_heap_size_spin.setEnabled(False)
        heap_layout.addWidget(self.mem_patch_heap_size_spin)
        heap_layout.addStretch()
        compat_layout.addLayout(heap_layout)

        # Heap Size info
        heap_size_info = QLabel(tr("mem_patch_heap_size_info"))
        heap_size_info.setStyleSheet(
            "color: #ffaa00; font-size: 11px; margin-top: 4px;"
        )
        heap_size_info.setWordWrap(True)
        compat_layout.addWidget(heap_size_info)

        compat_layout.addSpacing(8)

        # Debug Properties
        debug_layout = QHBoxLayout()
        debug_layout.addWidget(QLabel(tr("debug_properties_label")))
        self.debug_properties_edit = QLineEdit()
        self.debug_properties_edit.setPlaceholderText(
            tr("debug_properties_placeholder")
        )
        self.debug_properties_edit.setStyleSheet(
            StyleUtils._get_input_widget_style("QLineEdit")
        )
        debug_layout.addWidget(self.debug_properties_edit, 1)
        compat_layout.addLayout(debug_layout)

        debug_properties_info = QLabel(tr("debug_properties_info"))
        debug_properties_info.setStyleSheet(
            "color: #ffaa00; font-size: 11px; margin-top: 4px;"
        )
        debug_properties_info.setWordWrap(True)
        compat_layout.addWidget(debug_properties_info)

        # Profile Version group
        version_group = QGroupBox(tr("profile_version_group"))
        version_group.setStyleSheet(StyleUtils.get_group_style())
        version_layout = QVBoxLayout(version_group)
        version_layout.setSpacing(8)
        version_layout.setContentsMargins(12, 12, 12, 12)
        version_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        version_combo_layout = QHBoxLayout()
        version_combo_layout.addWidget(QLabel(tr("default_profile_version_label")))
        self.version_combo = QComboBox()
        self.version_combo.addItem("v1")
        self.version_combo.addItem("v2")
        # FIXME: Disable v2 (index 1) as it is not supported yet
        self.version_combo.model().item(1).setEnabled(False)
        self.version_combo.setStyleSheet(StyleUtils.get_combobox_style())
        version_combo_layout.addWidget(self.version_combo)
        version_combo_layout.addStretch()
        version_layout.addLayout(version_combo_layout)

        version_info = QLabel(tr("default_profile_version_info"))
        version_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 4px;")
        version_info.setWordWrap(True)
        version_layout.addWidget(version_info)

        # Hide the profile version section as requested, but keep it easy to re-enable
        version_group.setVisible(False)

        # Steam Integration group
        steam_group = QGroupBox(tr("steam_integration_header"))
        steam_group.setStyleSheet(StyleUtils.get_group_style())
        steam_layout = QVBoxLayout(steam_group)
        steam_layout.setSpacing(12)
        steam_layout.setContentsMargins(12, 12, 12, 12)
        steam_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.add_to_steam_btn = QPushButton(tr("add_to_steam_button"))
        self.add_to_steam_btn.setStyleSheet(StyleUtils.get_save_button_style())
        self.add_to_steam_btn.clicked.connect(self.on_add_to_steam_clicked)
        steam_layout.addWidget(self.add_to_steam_btn)

        steam_info = QLabel(tr("add_to_steam_info"))
        steam_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        steam_info.setWordWrap(True)
        steam_layout.addWidget(steam_info)

        # Arrange groups into two columns to reduce vertical height
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        left_col.addWidget(savefile_group)
        left_col.addWidget(online_group)
        left_col.addWidget(version_group)
        left_col.addWidget(steam_group)
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(compat_group)
        right_col.addStretch()

        columns_layout.addLayout(left_col, 1)
        columns_layout.addLayout(right_col, 1)

        layout.addLayout(columns_layout)

        StyleUtils.setup_standard_dialog_buttons(layout, self, self.save_settings)

    def on_add_to_steam_clicked(self):
        """Create a Steam shortcut for the current profile."""
        try:
            # Resolve Steam directory from ME3 info if available
            steam_dir = None
            try:
                if hasattr(self.config_manager, "get_steam_path"):
                    steam_dir = self.config_manager.get_steam_path()
            except Exception:
                steam_dir = None

            if not steam_dir:
                QMessageBox.information(
                    self,
                    tr("feature_not_available_title"),
                    tr("steam_not_found_status"),
                )
                return

            # Determine profile and launch details
            profile_path = self.config_manager.get_profile_path(self.game_name)
            if not profile_path or not profile_path.exists():
                QMessageBox.warning(
                    self,
                    tr("launch_error_title"),
                    tr("profile_not_found_msg", path=str(profile_path)),
                )
                return

            cli_id = self.config_manager.get_game_cli_id(self.game_name)
            if not cli_id:
                QMessageBox.warning(
                    self,
                    tr("launch_error_title"),
                    tr("cli_id_not_found_msg", game_name=self.game_name),
                )
                return

            # Build non-Steam shortcut launching through me3 CLI
            appname = f"{self.game_name} ({profile_path.stem})"
            # Prefer absolute path to 'me3' if we can resolve it, else rely on PATH
            exe = "me3"
            try:
                bin_dir = self.config_manager.path_manager.get_me3_binary_path()
                exe_candidate = bin_dir / (
                    "me3.exe" if sys.platform == "win32" else "me3"
                )
                if exe_candidate.exists():
                    exe = str(exe_candidate)
            except Exception:
                pass

            # On Linux (e.g., Steam Deck), ensure we have a full path since Steam
            # launches shortcuts without a proper PATH environment
            if sys.platform == "linux" and exe == "me3":
                from me3_manager.utils.platform_utils import PlatformUtils

                resolved = PlatformUtils._find_me3_executable_linux()
                if resolved:
                    exe = resolved
            startdir = str(profile_path.parent)
            launch_options = f'-q launch --game {cli_id} -p "{profile_path}"'

            from pathlib import Path as _Path

            from me3_manager.services.steam_shortcuts import (
                ShortcutParams,
                SteamShortcuts,
                detect_steam_dir_from_path,
            )

            normalized_steam = detect_steam_dir_from_path(_Path(steam_dir))
            if not normalized_steam or not normalized_steam.exists():
                QMessageBox.warning(
                    self,
                    tr("steam_validation_title"),
                    tr("steam_validation_message", steam_path=str(steam_dir)),
                )
                return

            # Pick app icon (ICO on Windows, PNG elsewhere) and copy it to a stable, user-writable location
            icon_rel = (
                "resources/icon/icon.ico"
                if sys.platform == "win32"
                else "resources/icon/icon.png"
            )
            bundled_icon = _Path(resource_path(icon_rel))

            # Derive a stable base under the ME3 config root (…/me3)
            try:
                base_me3_dir = (
                    self.config_manager.path_manager.config_root.parent.parent
                )
            except Exception:
                base_me3_dir = _Path.home() / (
                    "AppData/Local/garyttierney/me3"
                    if sys.platform == "win32"
                    else ".config/me3"
                )

            icons_dir = base_me3_dir / "icons"
            icon_dest = icons_dir / (
                "me3-manager.ico" if sys.platform == "win32" else "me3-manager.png"
            )
            icon_path = ""
            try:
                if bundled_icon.exists():
                    icons_dir.mkdir(parents=True, exist_ok=True)
                    # Copy or overwrite if source is newer/missing
                    if (
                        not icon_dest.exists()
                        or bundled_icon.stat().st_mtime > icon_dest.stat().st_mtime
                    ):
                        shutil.copyfile(bundled_icon, icon_dest)
                    icon_path = str(icon_dest)
            except Exception:
                icon_path = ""

            ok, msg = SteamShortcuts.add_shortcut_for_all_users(
                normalized_steam,
                ShortcutParams(
                    appname=appname,
                    exe=exe,
                    startdir=startdir,
                    launch_options=launch_options,
                    icon=icon_path,
                    tags=["ME3"],
                ),
            )

            if ok:
                QMessageBox.information(self, tr("SUCCESS"), msg)
            else:
                QMessageBox.warning(self, tr("ERROR"), msg)

        except Exception as e:
            QMessageBox.warning(
                self,
                tr("ERROR"),
                tr("could_not_perform_action", e=str(e)),
            )

    def _set_version_combo_to_default(self):
        """Set the version combo box to the default profile version."""
        try:
            default_version = (
                self.config_manager.ui_settings.get_default_profile_version()
            )
        except Exception:
            default_version = "v1"
        idx = 1 if default_version == "v2" else 0
        self.version_combo.setCurrentIndex(idx)

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

                # Load disable_arxan setting
                disable_arxan = config_data.get("disable_arxan", False)
                self.disable_arxan_cb.setChecked(bool(disable_arxan))

                # Load mem_patch setting
                mem_patch = config_data.get("mem_patch", False)
                self.mem_patch_cb.setChecked(bool(mem_patch))

                # Load mem_patch_heap_size setting
                mem_patch_heap_size = config_data.get("mem_patch_heap_size")
                if mem_patch_heap_size is not None:
                    self.mem_patch_heap_size_spin.setValue(int(mem_patch_heap_size))
                else:
                    self.mem_patch_heap_size_spin.setValue(0)

                # Load debug_properties setting
                debug_properties = config_data.get("debug_properties", {})
                if debug_properties:
                    try:
                        self.debug_properties_edit.setText(json.dumps(debug_properties))
                    except Exception:
                        self.debug_properties_edit.setText("")
                else:
                    self.debug_properties_edit.setText("")

                self.on_mem_patch_toggled(bool(mem_patch))

                # Detect Seamless Co-op enablement via natives entries
                try:
                    self.seamless_enabled = False
                    for native in config_data.get("natives", []):
                        if isinstance(native, dict):
                            p = str(native.get("path", "")).lower().replace("\\", "/")
                            if p.endswith(("/ersc.dll", "/nrsc.dll")):
                                self.seamless_enabled = True
                                break
                except Exception:
                    self.seamless_enabled = False

                self.current_settings = config_data
                # Load default profile version from UI settings
                self._set_version_combo_to_default()
            else:
                # Profile doesn't exist, use defaults
                self.custom_savefile_cb.setChecked(False)
                self.start_online_cb.setChecked(False)
                self.disable_arxan_cb.setChecked(False)
                self.mem_patch_cb.setChecked(False)
                self.mem_patch_heap_size_spin.setValue(0)
                self.debug_properties_edit.setText("")
                self.on_mem_patch_toggled(False)
                self.on_custom_savefile_toggled(False)
                self.current_settings = {}
                self.seamless_enabled = False
                self._set_version_combo_to_default()

        except Exception as e:
            QMessageBox.warning(
                self, tr("load_error"), tr("profile_load_error_msg", error=str(e))
            )
        # Ensure the warning reflects current state (custom savefile vs seamless)
        self._update_savefile_warning_visibility()

    def on_custom_savefile_toggled(self, checked):
        """Handle custom savefile checkbox toggle"""
        self.savefile_edit.setEnabled(checked)
        self.extension_combo.setEnabled(checked)
        if not checked:
            self.savefile_edit.clear()
        # Update warning visibility considering Seamless Co-op state
        self._update_savefile_warning_visibility()

    def on_mem_patch_toggled(self, checked):
        """Handle mem_patch checkbox toggle"""
        self.mem_patch_heap_size_spin.setEnabled(checked)

    def _update_savefile_warning_visibility(self):
        try:
            show_warning = (not self.custom_savefile_cb.isChecked()) and (
                not bool(getattr(self, "seamless_enabled", False))
            )
            self.savefile_warning.setVisible(show_warning)
        except Exception:
            self.savefile_warning.setVisible(False)

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

            # Update disable_arxan setting
            updated_config["disable_arxan"] = self.disable_arxan_cb.isChecked()

            # Update mem_patch setting
            updated_config["mem_patch"] = self.mem_patch_cb.isChecked()

            if (
                self.mem_patch_cb.isChecked()
                and self.mem_patch_heap_size_spin.value() > 0
            ):
                updated_config["mem_patch_heap_size"] = (
                    self.mem_patch_heap_size_spin.value()
                )
            else:
                updated_config.pop("mem_patch_heap_size", None)

            # Update debug_properties setting
            debug_prop_text = self.debug_properties_edit.text().strip()
            if debug_prop_text:
                try:
                    debug_props = json.loads(debug_prop_text)
                    if isinstance(debug_props, dict):
                        updated_config["debug_properties"] = debug_props
                    else:
                        raise ValueError("Debug properties must be a JSON object")
                except Exception as e:
                    QMessageBox.warning(
                        self, tr("ERROR"), f"Invalid debug properties JSON: {e}"
                    )
                    return
            else:
                updated_config.pop("debug_properties", None)

            # Persist default profile version choice
            chosen_version = self.version_combo.currentText()
            try:
                self.config_manager.ui_settings.set_default_profile_version(
                    chosen_version
                )
            except Exception:
                pass

            # Also set the target profileVersion for this profile write
            updated_config["profileVersion"] = chosen_version

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
