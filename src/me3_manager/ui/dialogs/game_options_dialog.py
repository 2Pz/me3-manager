import logging
import tomllib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.toml_config_writer import TomlConfigWriter
from me3_manager.utils.translator import tr

log = logging.getLogger(__name__)


class NoEnterLineEdit(QLineEdit):
    """QLineEdit that doesn't activate buttons when Enter is pressed."""

    def keyPressEvent(self, event: QKeyEvent):
        """Override key press event to handle Enter/Return keys."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Consume the event - don't let it propagate to activate buttons
            event.accept()
            return
        # For all other keys, use default behavior
        super().keyPressEvent(event)


class GameOptionsDialog(QDialog):
    """Dialog for configuring ME3 game options (skip_logos, boot_boost, skip_steam_init, exe, steam_dir)"""

    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.current_settings = {}

        self.setWindowTitle(tr("game_options_title", game_name=game_name))
        self.setModal(True)
        self.setMinimumSize(800, 560)
        self.resize(900, 680)

        self.init_ui()
        self.load_current_settings()

    def _open_path(self, path: Path):
        """Open a folder path using PlatformUtils (Qt-based)."""
        try:
            if not PlatformUtils.open_dir(str(path)):
                QMessageBox.warning(
                    self,
                    tr("open_path_error"),
                    tr(
                        "open_path_error_msg",
                        path=path,
                        e="Desktop service rejected request",
                    ),
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("open_path_error"),
                tr("open_path_error_msg", path=path, e=str(e)),
            )

    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel(tr("game_options_title", game_name=self.game_name))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)

        # Description
        desc = QLabel(tr("game_options_description", game_name=self.game_name))
        desc.setStyleSheet("color: #cccccc; margin-bottom: 16px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ME3 Config File group
        config_group = QGroupBox(tr("me3_config_file_group"))
        config_group.setStyleSheet(self._get_group_style())
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(12)

        # Config file path display and browse
        config_path_layout = QHBoxLayout()
        self.config_path_label = QLabel(tr("loading_config_path"))
        self.config_path_label.setStyleSheet(
            "color: #cccccc; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;"
        )
        self.config_path_label.setWordWrap(True)

        self.open_config_btn = QPushButton(tr("open_config_folder_button"))
        self.open_config_btn.setStyleSheet(self._get_button_style())
        self.open_config_btn.clicked.connect(self.open_config_folder)

        self.browse_config_btn = QPushButton(tr("change_location_button"))
        self.browse_config_btn.setStyleSheet(self._get_button_style())
        self.browse_config_btn.clicked.connect(self.browse_config_file)
        self.browse_config_btn.setToolTip(tr("change_location_tooltip"))

        config_path_layout.addWidget(self.config_path_label, 1)
        config_path_layout.addWidget(self.open_config_btn)
        config_path_layout.addWidget(self.browse_config_btn)

        config_layout.addLayout(config_path_layout)

        # Config file info
        config_info = QLabel(tr("me3_config_file_info", game_name=self.game_name))
        config_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        config_info.setWordWrap(True)
        config_layout.addWidget(config_info)

        layout.addWidget(config_group)

        # Game Options group
        options_group = QGroupBox(tr("game_options_title", game_name=self.game_name))
        options_group.setStyleSheet(self._get_group_style())
        options_layout = QFormLayout(options_group)
        options_layout.setSpacing(12)

        # Skip Logos checkbox
        self.skip_logos_cb = QCheckBox(tr("skip_logos_checkbox"))
        self.skip_logos_cb.setStyleSheet(self._get_checkbox_style())
        options_layout.addRow(tr("skip_logos_label"), self.skip_logos_cb)

        # Boot Boost checkbox
        self.boot_boost_cb = QCheckBox(tr("boot_boost_checkbox"))
        self.boot_boost_cb.setStyleSheet(self._get_checkbox_style())
        options_layout.addRow(tr("boot_boost_label"), self.boot_boost_cb)

        layout.addWidget(options_group)

        # Steam Directory group
        steam_group = QGroupBox(tr("steam_directory_title"))
        steam_group.setStyleSheet(self._get_group_style())
        steam_layout = QVBoxLayout(steam_group)
        steam_layout.setSpacing(12)

        # Steam Directory checkbox
        self.steam_dir_cb = QCheckBox(tr("steam_directory_checkbox"))
        self.steam_dir_cb.setStyleSheet(self._get_checkbox_style())
        self.steam_dir_cb.toggled.connect(self.on_steam_dir_toggled)
        steam_layout.addWidget(self.steam_dir_cb)

        # Steam directory path selection
        self.steam_dir_path_layout = QHBoxLayout()

        self.steam_dir_edit = NoEnterLineEdit()
        self.steam_dir_edit.setPlaceholderText(tr("steam_directory_placeholder"))
        self.steam_dir_edit.setStyleSheet(self._get_lineedit_style())
        self.steam_dir_edit.setEnabled(False)

        self.browse_steam_btn = QPushButton(tr("browse_button"))
        self.browse_steam_btn.setStyleSheet(self._get_button_style())
        self.browse_steam_btn.clicked.connect(self.browse_steam_directory)
        self.browse_steam_btn.setEnabled(False)

        self.clear_steam_btn = QPushButton(tr("clear_button"))
        self.clear_steam_btn.setStyleSheet(self._get_button_style())
        self.clear_steam_btn.clicked.connect(self.clear_steam_directory)
        self.clear_steam_btn.setEnabled(False)

        self.steam_dir_path_layout.addWidget(self.steam_dir_edit)
        self.steam_dir_path_layout.addWidget(self.browse_steam_btn)
        self.steam_dir_path_layout.addWidget(self.clear_steam_btn)

        # Use detected path button (from ME3 info)
        self.use_detected_btn = QPushButton(
            tr("use_detected") if hasattr(self, "tr") else "Use detected"
        )
        self.use_detected_btn.setStyleSheet(self._get_button_style())
        self.use_detected_btn.clicked.connect(self.on_use_detected_steam_dir)
        self.use_detected_btn.setEnabled(True)
        self.steam_dir_path_layout.addWidget(self.use_detected_btn)

        # Create a widget to contain the steam directory path layout so we can hide it
        self.steam_dir_widget = QWidget()
        self.steam_dir_widget.setLayout(self.steam_dir_path_layout)
        self.steam_dir_widget.setVisible(False)

        steam_layout.addWidget(self.steam_dir_widget)

        # Steam directory info
        steam_info = QLabel(tr("steam_directory_info"))
        steam_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        steam_info.setWordWrap(True)
        steam_layout.addWidget(steam_info)

        layout.addWidget(steam_group)

        # Executable path group
        exe_group = QGroupBox(tr("custom_executable_title"))
        exe_group.setStyleSheet(self._get_group_style())
        exe_layout = QVBoxLayout(exe_group)
        exe_layout.setSpacing(12)

        # Custom Executable checkbox
        self.exe_path_cb = QCheckBox(tr("custom_executable_checkbox"))
        self.exe_path_cb.setStyleSheet(self._get_checkbox_style())
        self.exe_path_cb.toggled.connect(self.on_exe_path_toggled)
        exe_layout.addWidget(self.exe_path_cb)

        # Executable path selection
        self.exe_path_layout = QHBoxLayout()

        self.exe_path_edit = NoEnterLineEdit()
        self.exe_path_edit.setPlaceholderText(tr("executable_path_placeholder"))
        self.exe_path_edit.setStyleSheet(self._get_lineedit_style())
        self.exe_path_edit.setEnabled(False)

        self.browse_exe_btn = QPushButton(tr("browse_button"))
        self.browse_exe_btn.setStyleSheet(self._get_button_style())
        self.browse_exe_btn.clicked.connect(self.browse_executable)
        self.browse_exe_btn.setEnabled(False)

        self.clear_exe_btn = QPushButton(tr("clear_button"))
        self.clear_exe_btn.setStyleSheet(self._get_button_style())
        self.clear_exe_btn.clicked.connect(self.clear_executable)
        self.clear_exe_btn.setEnabled(False)

        self.exe_path_layout.addWidget(self.exe_path_edit)
        self.exe_path_layout.addWidget(self.browse_exe_btn)
        self.exe_path_layout.addWidget(self.clear_exe_btn)

        # Create a widget to contain the exe path layout so we can hide it
        self.exe_path_widget = QWidget()
        self.exe_path_widget.setLayout(self.exe_path_layout)
        self.exe_path_widget.setVisible(False)

        exe_layout.addWidget(self.exe_path_widget)

        # Executable warning
        exe_warning = QLabel(tr("custom_executable_info", game_name=self.game_name))
        exe_warning.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        exe_warning.setWordWrap(True)
        exe_layout.addWidget(exe_warning)

        layout.addWidget(exe_group)

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
        """Load current settings from ME3 config"""
        try:
            self.current_settings = self.config_manager.get_me3_game_settings(
                self.game_name
            )

            # Update config file path display
            config_path = None
            if hasattr(self.config_manager, "get_me3_config_path"):
                config_path = self.config_manager.get_me3_config_path(self.game_name)

            if config_path:
                config_path_obj = Path(config_path)
                if config_path_obj.exists():
                    self.config_path_label.setText(str(config_path))
                    self.config_path_label.setStyleSheet(
                        "color: #81C784; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;"
                    )
                else:
                    self.config_path_label.setText(
                        tr("config_path_not_exist", config_path=config_path)
                    )
                    self.config_path_label.setStyleSheet(
                        "color: #FFB347; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;"
                    )
            else:
                self.config_path_label.setText("ME3 config file path not available")
                self.config_path_label.setStyleSheet(
                    "color: #FF6B6B; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;"
                )

            # Set checkbox states (convert None to False)
            skip_logos = self.current_settings.get("skip_logos")
            self.skip_logos_cb.setChecked(
                bool(skip_logos) if skip_logos is not None else False
            )

            boot_boost = self.current_settings.get("boot_boost")
            self.boot_boost_cb.setChecked(
                bool(boot_boost) if boot_boost is not None else False
            )

            # Load Steam directory from global settings (root level)
            steam_dir = self._load_steam_dir_globally()

            # Fallback: check if it's in the game settings (wrong location but handle it)
            if not steam_dir:
                steam_dir = self.current_settings.get("steam_dir")
                if steam_dir:
                    log.warning(
                        "Found steam_dir in game settings, should be at global level"
                    )

            if steam_dir:
                self.steam_dir_cb.setChecked(True)
                self.steam_dir_edit.setText(str(steam_dir))
                self.on_steam_dir_toggled(True)  # Show the steam dir controls
            else:
                self.steam_dir_cb.setChecked(False)
                self.on_steam_dir_toggled(False)  # Hide the steam dir controls

            # Set executable path and checkbox
            exe_path = self.current_settings.get("exe")
            if exe_path:
                self.exe_path_cb.setChecked(True)
                self.exe_path_edit.setText(str(exe_path))
                self.on_exe_path_toggled(True)  # Show the exe path controls
            else:
                self.exe_path_cb.setChecked(False)
                self.on_exe_path_toggled(False)  # Hide the exe path controls

        except Exception as e:
            QMessageBox.warning(
                self, tr("load_error"), tr("load_error_msg", path="ME3 config", error=e)
            )
            self.config_path_label.setText(
                tr("load_error_msg", path="ME3 config", error=e)
            )
            self.config_path_label.setStyleSheet("color: #FF6B6B; font-size: 12px;")

    def on_steam_dir_toggled(self, checked):
        """Handle steam directory checkbox toggle"""
        self.steam_dir_widget.setVisible(checked)
        self.steam_dir_edit.setEnabled(checked)
        self.browse_steam_btn.setEnabled(checked)
        self.clear_steam_btn.setEnabled(checked)
        if hasattr(self, "use_detected_btn"):
            self.use_detected_btn.setEnabled(checked)

        if not checked:
            self.steam_dir_edit.clear()
        else:
            self._resize_to_fit()

    def on_exe_path_toggled(self, checked):
        """Handle executable path checkbox toggle"""
        self.exe_path_widget.setVisible(checked)
        self.exe_path_edit.setEnabled(checked)
        self.browse_exe_btn.setEnabled(checked)
        self.clear_exe_btn.setEnabled(checked)

        if not checked:
            self.exe_path_edit.clear()
        else:
            self._resize_to_fit()

    def browse_steam_directory(self):
        """Browse for Steam installation directory (seeded from me3 info)."""
        # Prefer steam path reported by ME3
        start_dir = str(Path.home())
        try:
            if hasattr(self.config_manager, "get_steam_path"):
                me3_steam_path = self.config_manager.get_steam_path()
                if me3_steam_path:
                    # If ME3 returns a file path, use its parent; else use directory as is
                    start_dir = (
                        str(me3_steam_path.parent)
                        if me3_steam_path.is_file()
                        else str(me3_steam_path)
                    )
        except Exception:
            start_dir = str(Path.home())

        dir_name = QFileDialog.getExistingDirectory(
            self,
            tr("select_steam_dir_title")
            if hasattr(self, "tr")
            else "Select Steam Installation Directory",
            start_dir,
            QFileDialog.Option.ShowDirsOnly,
        )

        if dir_name:
            steam_path = Path(dir_name)

            # Validate that this looks like a Steam directory
            steam_exe_names = ["steam.exe", "steam", "Steam"]
            has_steam_exe = any((steam_path / exe).exists() for exe in steam_exe_names)
            has_steamapps = (steam_path / "steamapps").exists()

            if not (has_steam_exe or has_steamapps):
                reply = QMessageBox.question(
                    self,
                    tr("steam_validation_title"),
                    tr("steam_validation_message", steam_path=steam_path),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            self.steam_dir_edit.setText(dir_name)

    def clear_steam_directory(self):
        """Clear the Steam directory path"""
        self.steam_dir_edit.clear()

    def on_use_detected_steam_dir(self):
        """Quick-fill steam directory from ME3 info if available."""
        try:
            if hasattr(self.config_manager, "get_steam_path"):
                steam_path = self.config_manager.get_steam_path()
            else:
                steam_path = None
            if steam_path:
                # If file provided, use parent; else directory itself
                target = steam_path.parent if steam_path.is_file() else steam_path
                self.steam_dir_edit.setText(str(target))
                if not self.steam_dir_cb.isChecked():
                    self.steam_dir_cb.setChecked(True)
            else:
                QMessageBox.information(
                    self,
                    tr("steam_not_detected_title")
                    if hasattr(self, "tr")
                    else "Steam not detected",
                    tr("steam_not_detected_message")
                    if hasattr(self, "tr")
                    else "ME3 did not report a Steam path.",
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("steam_detection_error_title")
                if hasattr(self, "tr")
                else "Detection error",
                str(e),
            )

    def open_config_folder(self):
        """Open the folder containing the ME3 config file"""
        try:
            config_path = None
            if hasattr(self.config_manager, "get_me3_config_path"):
                config_path = self.config_manager.get_me3_config_path(self.game_name)

            if config_path:
                config_path_obj = Path(config_path)
                if config_path_obj.exists():
                    # Config file exists, open its folder
                    self._open_path(config_path_obj.parent)
                else:
                    # Config file doesn't exist but we know where it should be
                    reply = QMessageBox.question(
                        self,
                        tr("config_not_found_title"),
                        tr("config_not_found_message", config_path=config_path),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        # Try to create the config file using me3_info
                        if (
                            hasattr(self.config_manager, "me3_info")
                            and self.config_manager.me3_info
                        ):
                            if self.config_manager.me3_info.create_default_config():
                                self._open_path(config_path_obj.parent)
                                self.load_current_settings()  # Refresh the display
                            else:
                                QMessageBox.warning(
                                    self, tr("create_error"), tr("create_error_msg")
                                )
                        else:
                            # Fallback: create the directory and try to open it
                            config_path_obj.parent.mkdir(parents=True, exist_ok=True)
                            self._open_path(config_path_obj.parent)
            else:
                QMessageBox.warning(
                    self,
                    tr("config_not_found_title"),
                    tr("config_not_found_message"),
                )
        except Exception as e:
            QMessageBox.warning(
                self, tr("open_folder_error"), tr("open_folder_error_msg", e=str(e))
            )

    def browse_config_file(self):
        """Browse for ME3 config directory and let user choose or create config file location"""
        try:
            # Get available config paths from ME3
            available_paths = []
            if (
                hasattr(self.config_manager, "me3_info")
                and self.config_manager.me3_info
            ):
                available_paths = (
                    self.config_manager.me3_info.get_available_config_paths()
                )

            if not available_paths:
                # Fallback: allow manual selection when no candidates are returned
                import os as _os

                default_dir = (
                    Path(
                        _os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
                    )
                    / "me3"
                )
                try:
                    default_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                default_file = default_dir / "me3.toml"

                file_name, _ = QFileDialog.getSaveFileName(
                    self,
                    tr("choose_config_location"),
                    str(default_file),
                    "TOML Files (*.toml)",
                )
                if not file_name:
                    return

                selected_config_path = Path(file_name)

                try:
                    if (
                        hasattr(self.config_manager, "me3_info")
                        and self.config_manager.me3_info
                    ):
                        success = self.config_manager.me3_info.ensure_single_config(
                            selected_config_path
                        )

                        if success:
                            if hasattr(self.config_manager, "set_me3_config_path"):
                                self.config_manager.set_me3_config_path(
                                    self.game_name, str(selected_config_path)
                                )
                            self.load_current_settings()
                            QMessageBox.information(
                                self,
                                tr("config_updated_title"),
                                tr(
                                    "config_updated_message",
                                    selected_config_path=selected_config_path,
                                ),
                            )
                    return
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        tr("config_location_error_title"),
                        tr("config_location_error_message", error=str(e)),
                    )
                    return

            # Show dialog to let user choose from available paths
            from PySide6.QtWidgets import (
                QDialog,
                QHBoxLayout,
                QLabel,
                QListWidget,
                QPushButton,
                QVBoxLayout,
            )

            dialog = QDialog(self)
            dialog.setWindowTitle(tr("choose_config_location"))
            dialog.setModal(True)
            dialog.resize(600, 400)

            layout = QVBoxLayout(dialog)

            # Description
            desc = QLabel(tr("choose_config_location_desc"))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #cccccc; margin-bottom: 16px;")
            layout.addWidget(desc)

            # List of available paths
            path_list = QListWidget()
            path_list.setStyleSheet("""
                QListWidget {
                    background-color: #3d3d3d;
                    border: 2px solid #4d4d4d;
                    border-radius: 6px;
                    color: #ffffff;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 12px;
                }
                QListWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #4d4d4d;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #4d4d4d;
                }
            """)

            for config_path in available_paths:
                status = tr("exists") if config_path.exists() else tr("will_create")
                path_list.addItem(f"{status} - {config_path}")

            if path_list.count() > 0:
                path_list.setCurrentRow(0)

            layout.addWidget(path_list)

            # Info label
            info = QLabel(tr("choose_config_location_info"))
            info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 8px;")
            info.setWordWrap(True)
            layout.addWidget(info)

            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            cancel_btn = QPushButton(tr("cancel_button"))
            cancel_btn.setStyleSheet(self._get_cancel_button_style())
            cancel_btn.clicked.connect(dialog.reject)

            select_btn = QPushButton(tr("select_button"))
            select_btn.setStyleSheet(self._get_save_button_style())
            select_btn.clicked.connect(dialog.accept)

            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(select_btn)
            layout.addLayout(button_layout)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_index = path_list.currentRow()
                if selected_index >= 0:
                    selected_config_path = available_paths[selected_index]

                    try:
                        # Use the new ensure_single_config method to handle creation and cleanup
                        if (
                            hasattr(self.config_manager, "me3_info")
                            and self.config_manager.me3_info
                        ):
                            success = self.config_manager.me3_info.ensure_single_config(
                                selected_config_path
                            )

                            if success:
                                # Set the new config file path in the config manager
                                if hasattr(self.config_manager, "set_me3_config_path"):
                                    self.config_manager.set_me3_config_path(
                                        self.game_name, str(selected_config_path)
                                    )

                                # Reload settings with the new config file
                                self.load_current_settings()

                                QMessageBox.information(
                                    self,
                                    tr("config_updated_title"),
                                    tr(
                                        "config_updated_message",
                                        selected_config_path=selected_config_path,
                                    ),
                                )

                            else:
                                QMessageBox.warning(
                                    self,
                                    tr("config_setup_error_title"),
                                    tr("config_setup_error_message"),
                                )
                        else:
                            QMessageBox.warning(
                                self,
                                tr("feature_not_available_title"),
                                tr("feature_not_available_message"),
                            )

                    except Exception as e:
                        QMessageBox.warning(
                            self,
                            tr("config_location_error_title"),
                            tr("config_location_error_message", error=str(e)),
                        )

        except Exception as e:
            QMessageBox.warning(
                self,
                tr("browse_error_title"),
                tr("browse_error_message", error=str(e)),
            )

    def browse_executable(self):
        """Browse for game executable"""
        expected_exe_name = self.config_manager.get_game_executable_name(self.game_name)
        if not expected_exe_name:
            QMessageBox.critical(
                self,
                tr("configuration_error_title"),
                tr("configuration_error_message", game_name=self.game_name),
            )
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.game_name} Executable ({expected_exe_name})",
            str(Path.home()),
            "Executable Files (*.exe);;All Files (*)",
        )

        if file_name:
            selected_path = Path(file_name)
            if selected_path.name.lower() != expected_exe_name.lower():
                msg = QMessageBox(self)
                msg.setWindowTitle(tr("incorrect_executable_title"))
                msg.setTextFormat(Qt.TextFormat.RichText)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText(
                    f"<h3>{tr('executable_mismatch_title')}</h3>"
                    f"<p>{tr('executable_mismatch_message', game_name=self.game_name)}</p>"
                    f"<b>{tr('expected_executable')}</b>: {expected_exe_name}<br>"
                    f"<b>{tr('selected_executable')}</b>: {selected_path.name}<br>"
                    f"<p>{tr('executable_mismatch_suggestion', expected_exe_name=expected_exe_name)}</p>"
                )
                msg.exec()
                return

            self.exe_path_edit.setText(file_name)

    def clear_executable(self):
        """Clear the executable path"""
        self.exe_path_edit.clear()

    def save_settings(self):
        """Save the settings to ME3 config"""
        try:
            # Prepare game-specific settings dictionary (for [game.gamename] section)
            game_settings = {}

            # Get checkbox values (always set explicitly to true or false)
            game_settings["skip_logos"] = self.skip_logos_cb.isChecked()
            game_settings["boot_boost"] = self.boot_boost_cb.isChecked()

            # Handle Steam directory
            steam_dir = None
            if self.steam_dir_cb.isChecked():
                steam_dir = self.steam_dir_edit.text().strip()
                if not steam_dir:
                    # Checkbox is checked but no path provided
                    QMessageBox.warning(
                        self,
                        tr("steam_directory_required_title"),
                        tr("steam_directory_required_message"),
                    )
                    return

            # Get executable path
            exe_path = None
            if self.exe_path_cb.isChecked():
                exe_path = self.exe_path_edit.text().strip()
                if not exe_path:
                    # Checkbox is checked but no path provided
                    QMessageBox.warning(
                        self,
                        tr("executable_path_required_title"),
                        tr("executable_path_required_message"),
                    )
                    return

            if exe_path:
                game_settings["exe"] = exe_path
                # Automatically set skip_steam_init when custom exe is used
                game_settings["skip_steam_init"] = True
            else:
                game_settings["exe"] = None  # Remove from config
                game_settings["skip_steam_init"] = (
                    None  # Remove from config when no custom exe
                )

            log.debug("Game settings to save: %s", game_settings)
            log.debug("Steam directory to save: %s", steam_dir)

            # Save game-specific settings first
            game_save_success = self.config_manager.set_me3_game_settings(
                self.game_name, game_settings
            )

            # Handle steam_dir directly by modifying the TOML file
            steam_save_success, steam_error_msg = self._save_steam_dir_globally(
                steam_dir
            )

            # Check for errors and provide specific feedback
            if not game_save_success:
                QMessageBox.warning(
                    self,
                    tr("save_error"),
                    f"Failed to save game settings for {self.game_name}. Please check the ME3 config file permissions.",
                )
                return

            if not steam_save_success:
                QMessageBox.warning(
                    self,
                    tr("save_error"),
                    f"Failed to save Steam directory setting:\n\n{steam_error_msg}\n\nGame settings were saved successfully, but the Steam directory setting could not be updated.",
                )
                return

            # Both saves successful
            QMessageBox.information(
                self,
                tr("save_success"),
                tr("save_success_message", game_name=self.game_name),
            )

            # Refresh the config path display in case we switched to a different config file
            self.load_current_settings()
            self.accept()

        except Exception as e:
            QMessageBox.warning(
                self,
                tr("save_error"),
                tr("save_error_message", game_name=self.game_name, error=e),
            )

    def _save_steam_dir_globally(self, steam_dir):
        """Save steam_dir at the root level of me3.toml using TomlConfigWriter"""
        try:
            # Get the config file path
            config_path = None
            if hasattr(self.config_manager, "get_me3_config_path"):
                config_path = self.config_manager.get_me3_config_path(self.game_name)

            if not config_path:
                log.error("Could not get ME3 config path")
                return False, "Could not determine ME3 config file path"

            config_path_obj = Path(config_path)

            # First, validate write access to the original path
            can_write, error_msg = TomlConfigWriter.validate_write_access(
                config_path_obj
            )

            if not can_write:
                log.error("Cannot write to %s: %s", config_path_obj, error_msg)

                # Try to get a writable config path instead
                writable_path = self._get_writable_config_path()
                if writable_path:
                    config_path_obj = writable_path
                    log.debug("Using writable config path instead: %s", config_path_obj)

                    # Update the config manager to use the new path
                    if hasattr(self.config_manager, "set_me3_config_path"):
                        self.config_manager.set_me3_config_path(
                            self.game_name, str(config_path_obj)
                        )
                else:
                    return (
                        False,
                        f"No writable config path available. Original error: {error_msg}",
                    )

            # Use TomlConfigWriter to update the steam_dir value
            success, error_msg = TomlConfigWriter.update_config_value(
                config_path_obj, "steam_dir", steam_dir
            )

            if success:
                log.debug("Successfully saved steam_dir globally: %s", steam_dir)
                return True, ""
            else:
                log.error("Failed to save steam_dir: %s", error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error saving steam_dir: {str(e)}"
            log.error("%s", error_msg)
            return False, error_msg

    def _get_writable_config_path(self):
        """Get a writable config path, preferring user locations over system ones"""
        try:
            if (
                hasattr(self.config_manager, "me3_info")
                and self.config_manager.me3_info
            ):
                available_paths = (
                    self.config_manager.me3_info.get_available_config_paths()
                )

                for path in available_paths:
                    # Skip system paths
                    if self._is_system_path(path):
                        continue

                    # Check if path is writable or can be created
                    if path.exists():
                        try:
                            with open(path, "a", encoding="utf-8"):
                                pass
                            return path
                        except (PermissionError, OSError):
                            continue
                    else:
                        # Check if we can create the file
                        try:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            # Test by creating a temporary file
                            with open(path, "w", encoding="utf-8") as f:
                                f.write("")
                            return path
                        except (PermissionError, OSError):
                            continue

            return None

        except Exception as e:
            log.error("Failed to get writable config path: %s", e)
            return None

    def _is_system_path(self, file_path: Path) -> bool:
        """Check if a path is in a system directory that requires root privileges"""
        system_prefixes = ["/etc/", "/usr/", "/opt/", "/var/lib/", "/var/opt/"]
        str_path = str(file_path)
        return any(str_path.startswith(prefix) for prefix in system_prefixes)

    def _load_steam_dir_globally(self):
        """Load steam_dir from the root level of me3.toml (keeping TOML format)"""
        try:
            # Get the config file path
            config_path = None
            if hasattr(self.config_manager, "get_me3_config_path"):
                config_path = self.config_manager.get_me3_config_path(self.game_name)

            if not config_path:
                return None

            config_path_obj = Path(config_path)

            if config_path_obj.exists():
                try:
                    with open(config_path_obj, "rb") as f:
                        config_data = tomllib.load(f)
                    return config_data.get("steam_dir")
                except Exception as e:
                    log.error(
                        "Failed to read TOML config file %s: %s", config_path_obj, e
                    )
                    # If the system config is not readable, try to find a user config
                    user_steam_dir = self._find_user_config_with_steam_dir()
                    if user_steam_dir:
                        return user_steam_dir

            return None

        except Exception as e:
            log.error("Failed to load steam_dir globally: %s", e)
            return None

    def _find_user_config_with_steam_dir(self):
        """Find steam_dir setting in a user-accessible TOML config file"""
        try:
            if (
                hasattr(self.config_manager, "me3_info")
                and self.config_manager.me3_info
            ):
                available_paths = (
                    self.config_manager.me3_info.get_available_config_paths()
                )

                for path in available_paths:
                    # Skip system paths
                    if self._is_system_path(path):
                        continue

                    if path.exists() and path.suffix == ".toml":
                        try:
                            with open(path, "rb") as f:
                                config_data = tomllib.load(f)
                            steam_dir = config_data.get("steam_dir")
                            if steam_dir:
                                return steam_dir
                        except Exception:
                            continue

            return None

        except Exception as e:
            log.error("Failed to find user config with steam_dir: %s", e)
            return None

    def _get_dialog_style(self):
        """Get dialog stylesheet"""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """

    def _resize_to_fit(self):
        """Grow the dialog to fit newly-visible content without shrinking user size."""
        try:
            # Ensure layouts recalculate
            if self.layout() is not None:
                self.layout().activate()
            size_hint = self.sizeHint()
            current = self.size()
            # Only grow; never shrink to avoid surprising the user
            new_width = (
                current.width()
                if size_hint.width() <= current.width()
                else size_hint.width()
            )
            new_height = (
                current.height()
                if size_hint.height() <= current.height()
                else size_hint.height()
            )
            if new_width != current.width() or new_height != current.height():
                self.resize(new_width, new_height)
        except Exception:
            # Best-effort; avoid crashing UI if any platform-specific issue occurs
            pass

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
        """

    def _get_button_style(self):
        """Get regular button stylesheet"""
        return """
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
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
