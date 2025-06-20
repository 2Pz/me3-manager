# ui/game_page.py

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QTimer

from core.config_manager import ConfigManager
from ui.mod_item import ModItem
from ui.config_editor import ConfigEditorDialog

class GamePage(QWidget):
    """Widget for managing mods for a specific game"""
    
    def __init__(self, game_name: str, config_manager):
        super().__init__()
        self.game_name = game_name
        self.config_manager = config_manager
        self.mod_widgets = {}
        
        self.setAcceptDrops(True)
        self.init_ui()
        self.load_mods()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel(f"{self.game_name} Mods")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 8px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Launch button
        self.launch_btn = QPushButton(f"Launch {self.game_name}")
        self.launch_btn.setFixedHeight(40)
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.launch_btn.clicked.connect(self.launch_game)
        header_layout.addWidget(self.launch_btn)

        # Open Mods Folder button
        self.open_mods_folder_btn = QPushButton("📂")
        self.open_mods_folder_btn.setFixedSize(40, 40)
        self.open_mods_folder_btn.setToolTip("Open this game's mods folder")
        self.open_mods_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        self.open_mods_folder_btn.clicked.connect(self.open_mods_folder)
        header_layout.addWidget(self.open_mods_folder_btn)

        # Add External Mod button
        self.add_external_mod_btn = QPushButton("➕")
        self.add_external_mod_btn.setFixedSize(40, 40)
        self.add_external_mod_btn.setToolTip("Add an external mod (.dll) from any location")
        self.add_external_mod_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        self.add_external_mod_btn.clicked.connect(self.add_external_mod)
        header_layout.addWidget(self.add_external_mod_btn)
        
        layout.addLayout(header_layout)
        
        layout.addLayout(header_layout)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search mods...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.search_bar.textChanged.connect(self.filter_mods)
        layout.addWidget(self.search_bar)
        
        # Drop zone
        self.drop_zone = QLabel("📁 Drag & Drop .dll files, mod folders, or regulation.bin here to install mods")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px dashed #3d3d3d;
                border-radius: 12px;
                padding: 20px;
                font-size: 14px;
                color: #888888;
                margin: 8px 0px;
            }
        """)
        self.drop_zone.setFixedHeight(80)
        layout.addWidget(self.drop_zone)
        
        # Mods list
        self.mods_scroll = QScrollArea()
        self.mods_scroll.setWidgetResizable(True)
        self.mods_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #4d4d4d;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5d5d5d;
            }
        """)
        
        self.mods_widget = QWidget()
        self.mods_layout = QVBoxLayout(self.mods_widget)
        self.mods_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mods_layout.setSpacing(4)
        
        self.mods_scroll.setWidget(self.mods_widget)
        layout.addWidget(self.mods_scroll)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)

    def is_valid_mod_folder(self, path: str) -> bool:
        """Check if a folder contains valid mod subfolders"""
        folder_path = Path(path)
        if not folder_path.is_dir():
            return False
        
        acceptable_folders = [
            '_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
            'parts', 'script', 'sd', 'sfx', 'shader', 'sound'
        ]
        
        # Check if folder itself is acceptable or contains acceptable subfolders
        if folder_path.name in acceptable_folders:
            return True
        
        for item in folder_path.iterdir():
            if item.is_dir() and item.name in acceptable_folders:
                return True
        
        return False
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files = [url.toLocalFile() for url in urls]
            has_dll = any(f.endswith('.dll') for f in files)
            has_valid_folder = any(self.is_valid_mod_folder(f) for f in files)
            has_regulation = any(f.endswith('regulation.bin') for f in files) 
            
            if has_dll or has_valid_folder or has_regulation: 
                event.acceptProposedAction()
                self.drop_zone.setStyleSheet("""
                    QLabel {
                        background-color: #0078d4;
                        border: 2px dashed #ffffff;
                        border-radius: 12px;
                        padding: 20px;
                        font-size: 14px;
                        color: #ffffff;
                        margin: 8px 0px;
                    }
            """)
        
    def dragLeaveEvent(self, event):
        self.drop_zone.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px dashed #3d3d3d;
                border-radius: 12px;
                padding: 20px;
                font-size: 14px;
                color: #888888;
                margin: 8px 0px;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(event)
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        dll_files = [f for f in files if f.endswith('.dll')]
        mod_folders = [f for f in files if self.is_valid_mod_folder(f)]
        regulation_files = [f for f in files if f.endswith('regulation.bin')] 
        
        if dll_files:
            self.install_mods(dll_files)
        if mod_folders:
            self.install_folder_mods(mod_folders)
        if regulation_files: 
            self.install_regulation_files(regulation_files)

    def install_regulation_files(self, regulation_files: List[str]):
        """Install dropped regulation.bin file"""
        from datetime import datetime
        
        for regulation_path in regulation_files:
            try:
                mods_dir = self.config_manager.get_mods_dir(self.game_name)
                dest_path = mods_dir / "regulation.bin"
                
                # Check if regulation.bin already exists
                if dest_path.exists():
                    reply = QMessageBox.question(self, "Regulation.bin Exists", 
                                            f"regulation.bin already exists for {self.game_name}.\n\n"
                                            "Do you want to replace it? The current file will be backed up.",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        continue
                    
                    # Create backup with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"regulation.bin.backup_{timestamp}"
                    backup_path = mods_dir / backup_name
                    shutil.copy2(dest_path, backup_path)
                    self.status_label.setText(f"Backed up existing regulation.bin to {backup_name}")
                
                # Copy new regulation.bin
                shutil.copy2(regulation_path, dest_path)
                self.status_label.setText(f"Installed regulation.bin for {self.game_name}")
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install regulation.bin: {str(e)}")


        self.load_mods()
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def install_folder_mods(self, folder_paths: List[str]):
        """Install dropped mod folders"""
        from PyQt6.QtWidgets import QInputDialog
        
        if not folder_paths:
            return
        
        # If multiple folders are dropped at once, treat them as one mod
        if len(folder_paths) > 1:
            # Ask for mod name once for all folders
            mod_name, ok = QInputDialog.getText(
                self, "Mod Name", 
                f"Enter name for mod containing {len(folder_paths)} folders:",
                text="new_mod"
            )
            if not ok or not mod_name.strip():
                return
            mod_name = mod_name.strip()
            
            # Create destination in mods folder
            mods_dir = self.config_manager.get_mods_dir(self.game_name)
            dest_path = mods_dir / mod_name
            
            if dest_path.exists():
                reply = QMessageBox.question(self, "Mod Exists", 
                                        f"Mod folder '{mod_name}' already exists. Replace it?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return
                shutil.rmtree(dest_path)
            
            # Create parent folder and copy all subfolders into it
            dest_path.mkdir(parents=True, exist_ok=True)
            for folder_path in folder_paths:
                try:
                    source_path = Path(folder_path)
                    shutil.copytree(source_path, dest_path / source_path.name)
                except Exception as e:
                    QMessageBox.warning(self, "Install Error", f"Failed to copy folder {source_path.name}: {str(e)}")
            
            # Add to config as folder mod
            self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))
            self.status_label.setText(f"Installed folder mod: {mod_name}")
            
        else:
            # Single folder - use existing logic
            folder_path = folder_paths[0]
            try:
                source_path = Path(folder_path)
                acceptable_folders = [
                    '_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
                    'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
                    'parts', 'script', 'sd', 'sfx', 'shader', 'sound'
                ]
                
                # Determine mod name and destination structure
                if source_path.name in acceptable_folders:
                    # It's a subfolder, ask user for parent folder name
                    default_name = f"mod_{source_path.name}"
                    mod_name, ok = QInputDialog.getText(
                        self, "Mod Folder Name", 
                        f"Enter name for mod containing '{source_path.name}':",
                        text=default_name
                    )
                    if not ok or not mod_name.strip():
                        return
                    mod_name = mod_name.strip()
                    
                    # Create destination in mods folder
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    dest_path = mods_dir / mod_name
                    
                    if dest_path.exists():
                        reply = QMessageBox.question(self, "Mod Exists", 
                                                f"Mod folder '{mod_name}' already exists. Replace it?",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No:
                            return
                        shutil.rmtree(dest_path)
                    
                    # Create parent folder and copy the subfolder into it
                    dest_path.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_path, dest_path / source_path.name)
                else:
                    # It's already a parent folder, copy directly
                    mod_name = source_path.name
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    dest_path = mods_dir / mod_name
                    
                    if dest_path.exists():
                        reply = QMessageBox.question(self, "Mod Exists", 
                                                f"Mod folder '{mod_name}' already exists. Replace it?",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No:
                            return
                        shutil.rmtree(dest_path)
                    
                    shutil.copytree(source_path, dest_path)
                
                # Add to config as folder mod
                self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))
                self.status_label.setText(f"Installed folder mod: {mod_name}")
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install folder mod: {str(e)}")
        
        # Reload mods and reset status
        self.load_mods()
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def install_mods(self, dll_files: List[str]):
        """Install dropped DLL files"""
        installed_count = 0
        for dll_path in dll_files:
            try:
                mod_name = Path(dll_path).name
                dest_path = self.config_manager.get_mods_dir(self.game_name) / mod_name
                
                if dest_path.exists():
                    reply = QMessageBox.question(self, "Mod Exists", 
                                               f"Mod '{mod_name}' already exists. Replace it?",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        continue
                
                shutil.copy2(dll_path, dest_path)
                installed_count += 1
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install {mod_name}: {str(e)}")
        
        if installed_count > 0:
            self.status_label.setText(f"Installed {installed_count} mod(s)")
            self.load_mods()
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def load_mods(self):
        """Load and display all mods for this game"""
        while self.mods_layout.count():
            child = self.mods_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.mod_widgets.clear()
        
        # Load mods from config
        mods_info = self.config_manager.get_mods_info(self.game_name)
        
        for mod_path, info in mods_info.items():
            # Determine mod type and icon
            mod_type = ""
            type_icon = ""
            type_color = ""
            
            if info['name'] == 'regulation.bin':
                mod_type = "REGULATION"
                type_icon = "📄"
                type_color = "#ff6b35"  # Orange
            elif info.get('is_folder_mod', False):
                mod_type = "FOLDER"
                type_icon = "📁"
                type_color = "#4CAF50"  # Green
            else:
                mod_type = "DLL"
                type_icon = "🔧"
                type_color = "#2196F3"  # Blue
            
            mod_widget = ModItem(
                mod_path, 
                info['name'], 
                info['enabled'], 
                info['external'],
                info.get('is_folder_mod', False),
                info['name'] == 'regulation.bin',
                mod_type=mod_type,
                type_icon=type_icon,
                type_color=type_color
            )
            mod_widget.toggled.connect(self.toggle_mod)
            mod_widget.delete_requested.connect(self.delete_mod)
            mod_widget.edit_config_requested.connect(self.open_config_editor)
            mod_widget.open_folder_requested.connect(self.open_mod_folder)
            
            self.mods_layout.addWidget(mod_widget)
            self.mod_widgets[mod_path] = mod_widget
        
        # Update status
        total_mods = len(mods_info)
        enabled_mods = sum(1 for info in mods_info.values() if info['enabled'])
        self.status_label.setText(f"{enabled_mods}/{total_mods} mods enabled")
    
    def filter_mods(self, text: str):
        """Filter mods based on search text"""
        text = text.lower()
        for mod_path, widget in self.mod_widgets.items():
            mod_name = Path(mod_path).stem.lower()
            widget.setVisible(text in mod_name)
    
    def toggle_mod(self, mod_path: str, enabled: bool):
        """Toggle mod on/off"""
        try:
            self.config_manager.set_mod_enabled(self.game_name, mod_path, enabled)
            self.status_label.setText(f"{'Enabled' if enabled else 'Disabled'} {Path(mod_path).name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        except Exception as e:
            QMessageBox.warning(self, "Toggle Error", f"Failed to toggle mod: {str(e)}")
    
    def delete_mod(self, mod_path: str):
        """Delete a mod"""
        mod_name = Path(mod_path).name
        reply = QMessageBox.question(self, "Delete Mod", 
                                   f"Are you sure you want to delete '{mod_name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.config_manager.delete_mod(self.game_name, mod_path)
                self.load_mods()
                self.status_label.setText(f"Deleted {mod_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            except Exception as e:
                QMessageBox.warning(self, "Delete Error", f"Failed to delete mod: {str(e)}")
    
    def add_external_mod(self):
        """Opens a file dialog to add an external mod by path."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select External Mod DLL",
            str(Path.home()),  # Start at user's home directory
            "DLL Files (*.dll)"
        )
        
        if file_name:
            try:
                mod_path = str(Path(file_name))
                mod_name = Path(mod_path).name
                
                # Prevent user from adding a mod that's already in the local mods folder
                mods_dir = self.config_manager.get_mods_dir(self.game_name)
                if Path(file_name).parent == mods_dir:
                    QMessageBox.information(self, "Mod Info", 
                                          f"The mod '{mod_name}' is located inside this game's mods folder.\n\n"
                                          "It should already be in the list. This feature is for adding mods from other locations.")
                    return

                # Enable the mod, which adds its absolute path to the config
                self.config_manager.set_mod_enabled(self.game_name, mod_path, True)
                
                self.status_label.setText(f"Added external mod: {mod_name}")
                self.load_mods()
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                
            except Exception as e:
                QMessageBox.warning(self, "Add Error", f"Failed to add external mod: {str(e)}")
    def open_mod_folder(self, mod_path: str):
        """Open mod folder in file explorer"""
        try:
            folder_path = Path(mod_path).parent
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", folder_path])
            else:
                subprocess.call(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open folder: {str(e)}")
    
    def get_default_config_path(self, mod_path_str: str) -> Path:
        """Determines the default path for a mod's config.ini file."""
        mod_path = Path(mod_path_str)
        # Convention: MyMod.dll -> .../MyMod/config.ini
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def open_config_editor(self, mod_path: str):
        """Opens the config editor for a given mod and saves a new path if selected."""
        mod_name = Path(mod_path).stem
        
        # Get the config path from the manager (custom or default)
        initial_config_path = self.config_manager.get_mod_config_path(self.game_name, mod_path)

        dialog = ConfigEditorDialog(mod_name, initial_config_path, self)
        dialog.exec()
        
        # After the dialog is closed, check if a new path was selected
        if dialog.new_path_selected and dialog.new_path_selected != initial_config_path:
            self.config_manager.set_mod_config_path(
                self.game_name,
                mod_path,
                str(dialog.new_path_selected)
            )
            self.status_label.setText(f"Saved new config path for {mod_name}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def open_mods_folder(self):
        """Opens the main mods directory for this game."""
        try:
            mods_dir = self.config_manager.get_mods_dir(self.game_name)
            if not mods_dir.exists():
                QMessageBox.warning(self, "Folder Not Found", f"The mods directory does not exist yet:\n{mods_dir}")
                return

            if sys.platform == "win32":
                os.startfile(str(mods_dir))
            elif sys.platform == "darwin":
                subprocess.call(["open", str(mods_dir)])
            else:
                subprocess.call(["xdg-open", str(mods_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open mods folder: {str(e)}")
    
    def launch_game(self):
        """Launch the game with Mod Engine 3"""
        try:
            profile_path = self.config_manager.get_profile_path(self.game_name)
            if not profile_path.exists():
                QMessageBox.warning(self, "Launch Error", f"Profile file not found: {profile_path}")
                return
            
            # Get the main window and its terminal
            main_window = self.window()
            if hasattr(main_window, "terminal"):
                # Use the embedded terminal to run the profile
                profile_path_str = str(profile_path.resolve())
                command = f"{profile_path_str}"
                main_window.terminal.run_command(command)
                self.status_label.setText(f"Launching {self.game_name}...")
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            else:
                # Fallback to original method if terminal not available
                if sys.platform == "win32":
                    os.startfile(str(profile_path))
                    self.status_label.setText(f"Launching {self.game_name}...")
                    QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                else:
                    subprocess.run([str(profile_path)], check=True)
                    self.status_label.setText(f"Launching {self.game_name}...")
                    QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                                
        except Exception as e:
            QMessageBox.warning(self, "Launch Error", f"Failed to launch game: {str(e)}")
