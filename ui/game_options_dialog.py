from pathlib import Path
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QLineEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.resource_path import resource_path

class GameOptionsDialog(QDialog):
    """Dialog for configuring ME3 game options (skip_logos, boot_boost, skip_steam_init, exe)"""
    
    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.current_settings = {}
        
        self.setWindowTitle(f"Game Options - {game_name}")
        self.setModal(True)
        self.resize(500, 400)
        #self.setStyleSheet(self._get_dialog_style())
        
        self.init_ui()
        self.load_current_settings()
    
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
        desc = QLabel("Configure ME3 game options")
        desc.setStyleSheet("color: #cccccc; margin-bottom: 16px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Options group
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
        
        # Skip Steam Init is handled automatically - no UI needed
        
        layout.addWidget(options_group)
        
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
        
        # No need to connect textChanged since skip_steam_init is handled automatically in save
        
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
            
            # Set checkbox states (convert None to False)
            skip_logos = self.current_settings.get('skip_logos')
            self.skip_logos_cb.setChecked(bool(skip_logos) if skip_logos is not None else False)
            
            boot_boost = self.current_settings.get('boot_boost')
            self.boot_boost_cb.setChecked(bool(boot_boost) if boot_boost is not None else False)
            
            # Set executable path
            exe_path = self.current_settings.get('exe')
            if exe_path:
                self.exe_path_edit.setText(str(exe_path))
                
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load current settings: {str(e)}")
    
    
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
            # Prepare settings dictionary
            settings = {}
            
            # Get checkbox values (only set if different from default False)
            if self.skip_logos_cb.isChecked():
                settings['skip_logos'] = True
            else:
                settings['skip_logos'] = None  # Remove from config
            
            if self.boot_boost_cb.isChecked():
                settings['boot_boost'] = True
            else:
                settings['boot_boost'] = None  # Remove from config
            
            # Get executable path
            exe_path = self.exe_path_edit.text().strip()
            if exe_path:
                settings['exe'] = exe_path
                # Automatically set skip_steam_init when custom exe is used
                settings['skip_steam_init'] = True
            else:
                settings['exe'] = None  # Remove from config
                settings['skip_steam_init'] = None  # Remove from config when no custom exe
            
            # Save to ME3 config
            if self.config_manager.set_me3_game_settings(self.game_name, settings):
                QMessageBox.information(self, "Settings Saved", 
                                      f"Game options for {self.game_name} have been saved successfully.")
                self.accept()
            else:
                QMessageBox.warning(self, "Save Error", 
                                  "Failed to save settings. Please check that ME3 is properly installed.")
                
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save settings: {str(e)}")
    
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
