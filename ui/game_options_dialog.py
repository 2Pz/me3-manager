import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QLineEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout, QWidget
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
from utils.resource_path import resource_path

class GameOptionsDialog(QDialog):
    """Dialog for configuring ME3 game options (skip_logos, boot_boost, skip_steam_init, exe, steam_dir)"""
    
    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.current_settings = {}
        
        self.setWindowTitle(f"Game Options - {game_name}")
        self.setModal(True)
        self.resize(850, 700)
        
        self.init_ui()
        self.load_current_settings()
    
    def _open_path(self, path: Path):
        """Open a file or folder path using the system default application"""
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                env = os.environ.copy()
                env.pop('LD_LIBRARY_PATH', None)
                env.pop('PYTHONPATH', None)
                env.pop('PYTHONHOME', None)
                
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", str(path)], shell=True, env=env)
                else:
                    subprocess.run(["xdg-open", str(path)], env=env)
            else:
                url = QUrl.fromLocalFile(str(path))
                if not QDesktopServices.openUrl(url):
                    raise Exception("QDesktopServices failed to open URL.")
        except Exception as e:
            QMessageBox.warning(self, "Open Path Error", f"Failed to open path:\n{path}\n\nError: {str(e)}")
    
    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title = QLabel(f"{self.game_name} Options")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Configure ME3 game options. These settings will be saved to the ME3 configuration file.")
        desc.setStyleSheet("color: #cccccc; margin-bottom: 16px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # ME3 Config File group
        config_group = QGroupBox("ME3 Configuration File")
        config_group.setStyleSheet(self._get_group_style())
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(12)
        
        # Config file path display and browse
        config_path_layout = QHBoxLayout()
        self.config_path_label = QLabel("Loading...")
        self.config_path_label.setStyleSheet("color: #cccccc; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;")
        self.config_path_label.setWordWrap(True)
        
        self.open_config_btn = QPushButton("Open Folder")
        self.open_config_btn.setStyleSheet(self._get_button_style())
        self.open_config_btn.clicked.connect(self.open_config_folder)
        
        self.browse_config_btn = QPushButton("Change Location...")
        self.browse_config_btn.setStyleSheet(self._get_button_style())
        self.browse_config_btn.clicked.connect(self.browse_config_file)
        self.browse_config_btn.setToolTip("Choose from available ME3 config locations to prevent multiple config files")
        
        config_path_layout.addWidget(self.config_path_label, 1)
        config_path_layout.addWidget(self.open_config_btn)
        config_path_layout.addWidget(self.browse_config_btn)
        
        config_layout.addLayout(config_path_layout)
        
        # Config file info
        config_info = QLabel("💡 The app searches all ME3 config paths and uses the first found config file. "
                            "Use 'Change Location...' to choose from available writable locations.")
        config_info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 4px;")
        config_info.setWordWrap(True)
        config_layout.addWidget(config_info)
        
        layout.addWidget(config_group)
        
        # Game Options group
        options_group = QGroupBox("Game Options")
        options_group.setStyleSheet(self._get_group_style())
        options_layout = QFormLayout(options_group)
        options_layout.setSpacing(12)
        
        # Skip Logos checkbox
        self.skip_logos_cb = QCheckBox("Skip game logos on startup")
        self.skip_logos_cb.setStyleSheet(self._get_checkbox_style())
        options_layout.addRow("Skip Logos:", self.skip_logos_cb)
        
        # Boot Boost checkbox
        self.boot_boost_cb = QCheckBox("Enable boot boost for faster startup")
        self.boot_boost_cb.setStyleSheet(self._get_checkbox_style())
        options_layout.addRow("Boot Boost:", self.boot_boost_cb)
        
        layout.addWidget(options_group)
        
        # Steam Directory group
        steam_group = QGroupBox("Steam Directory")
        steam_group.setStyleSheet(self._get_group_style())
        steam_layout = QVBoxLayout(steam_group)
        steam_layout.setSpacing(12)
        
        # Steam Directory checkbox
        self.steam_dir_cb = QCheckBox("Use custom Steam directory")
        self.steam_dir_cb.setStyleSheet(self._get_checkbox_style())
        self.steam_dir_cb.toggled.connect(self.on_steam_dir_toggled)
        steam_layout.addWidget(self.steam_dir_cb)
        
        # Steam directory path selection
        self.steam_dir_path_layout = QHBoxLayout()
        
        self.steam_dir_edit = QLineEdit()
        self.steam_dir_edit.setPlaceholderText("Path to Steam installation directory")
        self.steam_dir_edit.setStyleSheet(self._get_lineedit_style())
        self.steam_dir_edit.setEnabled(False)
        
        self.browse_steam_btn = QPushButton("Browse...")
        self.browse_steam_btn.setStyleSheet(self._get_button_style())
        self.browse_steam_btn.clicked.connect(self.browse_steam_directory)
        self.browse_steam_btn.setEnabled(False)
        
        self.clear_steam_btn = QPushButton("Clear")
        self.clear_steam_btn.setStyleSheet(self._get_button_style())
        self.clear_steam_btn.clicked.connect(self.clear_steam_directory)
        self.clear_steam_btn.setEnabled(False)
        
        self.steam_dir_path_layout.addWidget(self.steam_dir_edit)
        self.steam_dir_path_layout.addWidget(self.browse_steam_btn)
        self.steam_dir_path_layout.addWidget(self.clear_steam_btn)
        
        # Create a widget to contain the steam directory path layout so we can hide it
        self.steam_dir_widget = QWidget()
        self.steam_dir_widget.setLayout(self.steam_dir_path_layout)
        self.steam_dir_widget.setVisible(False)
        
        steam_layout.addWidget(self.steam_dir_widget)
        
        # Steam directory info
        steam_info = QLabel("💡 Specify a custom Steam installation directory if ME3 cannot auto-detect it. "
                           "This setting applies globally to all games.")
        steam_info.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        steam_info.setWordWrap(True)
        steam_layout.addWidget(steam_info)
        
        layout.addWidget(steam_group)
        
        # Executable path group
        exe_group = QGroupBox("Custom Executable")
        exe_group.setStyleSheet(self._get_group_style())
        exe_layout = QVBoxLayout(exe_group)
        exe_layout.setSpacing(12)
        
        # Executable path
        exe_path_layout = QHBoxLayout()
        self.exe_path_edit = QLineEdit()
        self.exe_path_edit.setPlaceholderText("Path to game executable (optional)")
        self.exe_path_edit.setStyleSheet(self._get_lineedit_style())
        
        self.browse_exe_btn = QPushButton("Browse...")
        self.browse_exe_btn.setStyleSheet(self._get_button_style())
        self.browse_exe_btn.clicked.connect(self.browse_executable)
        
        self.clear_exe_btn = QPushButton("Clear")
        self.clear_exe_btn.setStyleSheet(self._get_button_style())
        self.clear_exe_btn.clicked.connect(self.clear_executable)
        
        exe_path_layout.addWidget(self.exe_path_edit)
        exe_path_layout.addWidget(self.browse_exe_btn)
        exe_path_layout.addWidget(self.clear_exe_btn)
        
        exe_layout.addLayout(exe_path_layout)
        
        # Executable warning
        exe_warning = QLabel("⚠️ Only set a custom executable if ME3 cannot detect your game installation automatically.")
        exe_warning.setStyleSheet("color: #ffaa00; font-size: 11px; margin-top: 8px;")
        exe_warning.setWordWrap(True)
        exe_layout.addWidget(exe_warning)
        
        layout.addWidget(exe_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(self._get_cancel_button_style())
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(self._get_save_button_style())
        self.save_btn.clicked.connect(self.save_settings)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
    def load_current_settings(self):
        """Load current settings from ME3 config"""
        try:
            self.current_settings = self.config_manager.get_me3_game_settings(self.game_name)
            
            # Update config file path display
            config_path = None
            if hasattr(self.config_manager, 'get_me3_config_path'):
                config_path = self.config_manager.get_me3_config_path(self.game_name)
            
            if config_path:
                config_path_obj = Path(config_path)
                if config_path_obj.exists():
                    self.config_path_label.setText(str(config_path))
                    self.config_path_label.setStyleSheet("color: #81C784; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;")
                else:
                    self.config_path_label.setText(f"{config_path} (will be created)")
                    self.config_path_label.setStyleSheet("color: #FFB347; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;")
            else:
                self.config_path_label.setText("ME3 config file path not available")
                self.config_path_label.setStyleSheet("color: #FF6B6B; font-size: 12px; font-family: 'Consolas', 'Monaco', monospace;")
            
            # Set checkbox states (convert None to False)
            skip_logos = self.current_settings.get('skip_logos')
            self.skip_logos_cb.setChecked(bool(skip_logos) if skip_logos is not None else False)
            
            boot_boost = self.current_settings.get('boot_boost')
            self.boot_boost_cb.setChecked(bool(boot_boost) if boot_boost is not None else False)
            
            # Set executable path
            exe_path = self.current_settings.get('exe')
            if exe_path:
                self.exe_path_edit.setText(str(exe_path))
            
            # Load Steam directory from global settings (root level)
            steam_dir = self._load_steam_dir_globally()
            
            # Fallback: check if it's in the game settings (wrong location but handle it)
            if not steam_dir:
                steam_dir = self.current_settings.get('steam_dir')
                if steam_dir:
                    print("WARNING: Found steam_dir in game settings, should be at global level")
            
            if steam_dir:
                self.steam_dir_cb.setChecked(True)
                self.steam_dir_edit.setText(str(steam_dir))
                self.on_steam_dir_toggled(True)  # Show the steam dir controls
            else:
                self.steam_dir_cb.setChecked(False)
                self.on_steam_dir_toggled(False)  # Hide the steam dir controls
                
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load current settings: {str(e)}")
            self.config_path_label.setText(f"Error loading config: {str(e)}")
            self.config_path_label.setStyleSheet("color: #FF6B6B; font-size: 12px;")
    
    def on_steam_dir_toggled(self, checked):
        """Handle steam directory checkbox toggle"""
        self.steam_dir_widget.setVisible(checked)
        self.steam_dir_edit.setEnabled(checked)
        self.browse_steam_btn.setEnabled(checked)
        self.clear_steam_btn.setEnabled(checked)
        
        if not checked:
            self.steam_dir_edit.clear()

    def browse_steam_directory(self):
        """Browse for Steam installation directory"""
        # Try to find Steam's default installation path as starting point
        import platform
        system = platform.system()
        
        default_steam_paths = []
        if system == "Windows":
            default_steam_paths = [
                Path("C:/Program Files (x86)/Steam"),
                Path("C:/Program Files/Steam"),
                Path("D:/Steam"),
                Path("E:/Steam")
            ]
        elif system == "Linux":
            home = Path.home()
            default_steam_paths = [
                home / ".steam" / "steam",
                home / ".local" / "share" / "Steam"
            ]
        
        # Find first existing default path
        start_dir = str(Path.home())
        for path in default_steam_paths:
            if path.exists():
                start_dir = str(path.parent)
                break
        
        dir_name = QFileDialog.getExistingDirectory(
            self,
            "Select Steam Installation Directory",
            start_dir,
            QFileDialog.Option.ShowDirsOnly
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
                    "Steam Directory Validation",
                    f"The selected directory doesn't appear to contain Steam:\n{steam_path}\n\n"
                    f"Expected to find 'steam.exe' (or 'steam') and/or 'steamapps' folder.\n\n"
                    f"Do you want to use this directory anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return
            
            self.steam_dir_edit.setText(dir_name)

    def clear_steam_directory(self):
        """Clear the Steam directory path"""
        self.steam_dir_edit.clear()
    
    def open_config_folder(self):
        """Open the folder containing the ME3 config file"""
        try:
            config_path = None
            if hasattr(self.config_manager, 'get_me3_config_path'):
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
                        "Config File Not Found", 
                        f"ME3 configuration file doesn't exist yet:\n{config_path}\n\n"
                        f"Would you like to create it and open the folder?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        # Try to create the config file using me3_info
                        if hasattr(self.config_manager, 'me3_info') and self.config_manager.me3_info:
                            if self.config_manager.me3_info.create_default_config():
                                self._open_path(config_path_obj.parent)
                                self.load_current_settings()  # Refresh the display
                            else:
                                QMessageBox.warning(self, "Create Error", "Failed to create default config file.")
                        else:
                            # Fallback: create the directory and try to open it
                            config_path_obj.parent.mkdir(parents=True, exist_ok=True)
                            self._open_path(config_path_obj.parent)
            else:
                QMessageBox.warning(self, "Config Not Found", 
                                  "ME3 configuration file location not available. Use 'Browse...' to locate it manually.")
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open config folder: {str(e)}")
    
    def browse_config_file(self):
        """Browse for ME3 config directory and let user choose or create config file location"""
        try:
            # Get available config paths from ME3
            available_paths = []
            if hasattr(self.config_manager, 'me3_info') and self.config_manager.me3_info:
                available_paths = self.config_manager.me3_info.get_available_config_paths()
            
            if not available_paths:
                QMessageBox.warning(self, "No Available Paths", 
                                  "No writable ME3 configuration paths are available.")
                return
            
            # Show dialog to let user choose from available paths
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Choose ME3 Config Location")
            dialog.setModal(True)
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Description
            desc = QLabel("Choose where to create or use the ME3 configuration file (me3.toml):")
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
            
            for i, config_path in enumerate(available_paths):
                status = "✓ Exists" if config_path.exists() else "○ Will be created"
                path_list.addItem(f"{status} - {config_path}")
            
            if path_list.count() > 0:
                path_list.setCurrentRow(0)
            
            layout.addWidget(path_list)
            
            # Info label
            info = QLabel("💡 Select a location where the me3.toml file exists or can be created. "
                         "This prevents having multiple config files in different locations.")
            info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 8px;")
            info.setWordWrap(True)
            layout.addWidget(info)
            
            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet(self._get_cancel_button_style())
            cancel_btn.clicked.connect(dialog.reject)
            
            select_btn = QPushButton("Select")
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
                        if hasattr(self.config_manager, 'me3_info') and self.config_manager.me3_info:
                            success = self.config_manager.me3_info.ensure_single_config(selected_config_path)
                            
                            if success:
                                # Set the new config file path in the config manager
                                if hasattr(self.config_manager, 'set_me3_config_path'):
                                    self.config_manager.set_me3_config_path(self.game_name, str(selected_config_path))
                                
                                # Reload settings with the new config file
                                self.load_current_settings()
                                
                                QMessageBox.information(self, "Config Location Updated", 
                                                      f"ME3 configuration location updated to:\n{selected_config_path}\n\n"
                                                      f"Any duplicate config files in other locations have been removed.")
                            else:
                                QMessageBox.warning(self, "Config Setup Error", 
                                                  "Failed to set up the config file at the selected location.")
                        else:
                            QMessageBox.warning(self, "Feature Not Available", 
                                              "ME3 info manager is not available.")
                        
                    except Exception as e:
                        QMessageBox.warning(self, "Config Location Error", 
                                          f"Failed to set config location: {str(e)}")
                        
        except Exception as e:
            QMessageBox.warning(self, "Browse Error", f"Failed to browse for config location: {str(e)}")
    
    
    def browse_executable(self):
        """Browse for game executable"""
        expected_exe_name = self.config_manager.get_game_executable_name(self.game_name)
        if not expected_exe_name:
            QMessageBox.critical(self, "Configuration Error", 
                               f"Expected executable name for '{self.game_name}' is not defined.")
            return
        
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            f"Select {self.game_name} Executable ({expected_exe_name})", 
            str(Path.home()), 
            "Executable Files (*.exe);;All Files (*)"
        )
        
        if file_name:
            selected_path = Path(file_name)
            if selected_path.name.lower() != expected_exe_name.lower():
                msg = QMessageBox(self)
                msg.setWindowTitle("Incorrect Executable Selected")
                msg.setTextFormat(Qt.TextFormat.RichText)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText(
                    f"<h3>Executable Mismatch</h3>"
                    f"<p>The selected file does not match the required executable for <b>{self.game_name}</b>.</p>"
                    f"<b>Expected:</b> {expected_exe_name}<br>"
                    f"<b>Selected:</b> {selected_path.name}<br>"
                    f"<p>Please choose the correct file named <b>{expected_exe_name}</b>.</p>"
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
            game_settings['skip_logos'] = self.skip_logos_cb.isChecked()
            game_settings['boot_boost'] = self.boot_boost_cb.isChecked()
            
            # Get executable path
            exe_path = self.exe_path_edit.text().strip()
            if exe_path:
                game_settings['exe'] = exe_path
                # Automatically set skip_steam_init when custom exe is used
                game_settings['skip_steam_init'] = True
            else:
                game_settings['exe'] = None  # Remove from config
                game_settings['skip_steam_init'] = None  # Remove from config when no custom exe
            
            # Handle Steam directory
            steam_dir = None
            if self.steam_dir_cb.isChecked():
                steam_dir = self.steam_dir_edit.text().strip()
                if not steam_dir:
                    # Checkbox is checked but no path provided
                    QMessageBox.warning(self, "Steam Directory Required", 
                                      "Please provide a Steam directory path or uncheck the option.")
                    return
            
            print(f"DEBUG: Game settings to save: {game_settings}")
            print(f"DEBUG: Steam directory to save: {steam_dir}")
            
            # Save game-specific settings first
            game_save_success = self.config_manager.set_me3_game_settings(self.game_name, game_settings)
            
            # Handle steam_dir directly by modifying the TOML file
            steam_save_success = self._save_steam_dir_globally(steam_dir)
            
            if game_save_success and steam_save_success:
                QMessageBox.information(self, "Settings Saved", 
                                      f"Game options for {self.game_name} have been saved successfully.")
                self.accept()
            else:
                QMessageBox.warning(self, "Save Error", 
                                  "Failed to save some settings. Please check that ME3 is properly installed.")
                
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save settings: {str(e)}")
    
    def _save_steam_dir_globally(self, steam_dir):
        """Save steam_dir at the root level of me3.toml"""
        try:
            import toml
            
            # Get the config file path
            config_path = None
            if hasattr(self.config_manager, 'get_me3_config_path'):
                config_path = self.config_manager.get_me3_config_path(self.game_name)
            
            if not config_path:
                print("ERROR: Could not get ME3 config path")
                return False
            
            config_path_obj = Path(config_path)
            
            # Load existing config or create empty one
            if config_path_obj.exists():
                with open(config_path_obj, 'r', encoding='utf-8') as f:
                    config = toml.load(f)
            else:
                config = {}
            
            # Set or remove steam_dir at root level
            if steam_dir:
                config['steam_dir'] = steam_dir
                print(f"DEBUG: Setting steam_dir globally to: {steam_dir}")
            else:
                # Remove steam_dir if it exists
                config.pop('steam_dir', None)
                print("DEBUG: Removing steam_dir from global config")
            
            # Save back to file
            with open(config_path_obj, 'w', encoding='utf-8') as f:
                toml.dump(config, f)
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to save steam_dir globally: {e}")
            return False
    
    def _load_steam_dir_globally(self):
        """Load steam_dir from the root level of me3.toml"""
        try:
            import toml
            
            # Get the config file path
            config_path = None
            if hasattr(self.config_manager, 'get_me3_config_path'):
                config_path = self.config_manager.get_me3_config_path(self.game_name)
            
            if not config_path:
                return None
            
            config_path_obj = Path(config_path)
            
            if config_path_obj.exists():
                with open(config_path_obj, 'r', encoding='utf-8') as f:
                    config = toml.load(f)
                return config.get('steam_dir')
            
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to load steam_dir globally: {e}")
            return None
    
    def _get_dialog_style(self):
        """Get dialog stylesheet"""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """
    
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