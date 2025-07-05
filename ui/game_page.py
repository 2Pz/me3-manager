import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Dict
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QMessageBox, QFileDialog, QDialog, QSpinBox
)
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtCore import Qt, QTimer, QSize
from utils.resource_path import resource_path
from core.config_manager import ConfigManager
from ui.mod_item import ModItem
from ui.config_editor import ConfigEditorDialog
from ui.profile_editor import ProfileEditor

class GamePage(QWidget):
    """Widget for managing mods for a specific game"""
    
    def __init__(self, game_name: str, config_manager):
        super().__init__()
        self.game_name = game_name
        self.config_manager = config_manager
        self.mod_widgets = {}
        self.current_filter = "all"
        self.filter_buttons = {}
        
        # Pagination settings
        self.mods_per_page = self.config_manager.get_mods_per_page()
        self.current_page = 1
        self.total_pages = 1
        self.filtered_mods = {}
        
        self.setAcceptDrops(True)
        self.init_ui()
        self.load_mods()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel(f"{self.game_name} Mods")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 8px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.launch_btn = QPushButton(f"Launch {self.game_name}")
        self.launch_btn.setFixedHeight(40)
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; border: none; border-radius: 8px;
                font-size: 14px; font-weight: bold; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        self.launch_btn.clicked.connect(self.launch_game)
        header_layout.addWidget(self.launch_btn)

        self.custom_exe_btn = QPushButton(QIcon(resource_path("resources/icon/exe.png")), "")
        self.custom_exe_btn.setIconSize(QSize(40, 40))
        self.custom_exe_btn.setFixedSize(60, 60) 
        self.custom_exe_btn.setToolTip("Set custom game executable path")
        self.custom_exe_btn.setStyleSheet("""
            QPushButton { background-color: #4d4d4d; color: white; border: none; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QPushButton:pressed { background-color: #3d3d3d; }
        """)
        self.custom_exe_btn.clicked.connect(self.set_custom_exe_path)
        header_layout.addWidget(self.custom_exe_btn)

        self.open_mods_folder_btn = QPushButton(QIcon(resource_path("resources/icon/folder.png")), "")
        self.open_mods_folder_btn.setIconSize(QSize(40, 40))
        self.open_mods_folder_btn.setFixedSize(60, 60) 
        self.open_mods_folder_btn.setToolTip("Open game's mods folder")
        self.open_mods_folder_btn.setStyleSheet("""
            QPushButton { background-color: #4d4d4d; color: white; border: none; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QPushButton:pressed { background-color: #3d3d3d; }
        """)
        self.open_mods_folder_btn.clicked.connect(self.open_mods_folder)
        header_layout.addWidget(self.open_mods_folder_btn)

        self.add_external_mod_btn = QPushButton(QIcon(resource_path("resources/icon/dll.png")), "")
        self.add_external_mod_btn.setIconSize(QSize(40, 40))
        self.add_external_mod_btn.setFixedSize(60, 60) 
        self.add_external_mod_btn.setToolTip("Add an external mod (.dll) from any location")
        self.add_external_mod_btn.setStyleSheet("""
            QPushButton { background-color: #4d4d4d; color: white; border: none; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QPushButton:pressed { background-color: #3d3d3d; }
        """)
        self.add_external_mod_btn.clicked.connect(self.add_external_mod)
        header_layout.addWidget(self.add_external_mod_btn)
        
        self.edit_profile_btn = QPushButton(QIcon(resource_path("resources/icon/note.png")), "")
        self.edit_profile_btn.setIconSize(QSize(40, 40))
        self.edit_profile_btn.setFixedSize(60, 60)
        self.edit_profile_btn.setToolTip("Edit game's profile (.me3) file")
        self.edit_profile_btn.setStyleSheet("""
            QPushButton { background-color: #4d4d4d; color: white; border: none; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QPushButton:pressed { background-color: #3d3d3d; }
        """)
        self.edit_profile_btn.clicked.connect(self.open_profile_editor)
        header_layout.addWidget(self.edit_profile_btn)
        
        layout.addLayout(header_layout)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search mods...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d; border: 2px solid #3d3d3d; border-radius: 8px;
                padding: 8px 12px; font-size: 12px; color: #ffffff;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        self.search_bar.textChanged.connect(self.apply_filters)
        layout.addWidget(self.search_bar)

        # Filter buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 4, 0, 0)

        filter_defs = {
            "all": ("All", "Show all mods"),
            "enabled": ("Enabled", "Show all enabled mods (DLLs and Folders)"),
            "disabled": ("Disabled", "Show all disabled mods"),
            "with_regulation": ("Enabled with Regulation", "Show enabled FOLDER mods with regulation.bin"),
            "without_regulation": ("Enabled without Regulation", "Show enabled FOLDER mods without regulation.bin")
        }

        for name, (text, tooltip) in filter_defs.items():
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, b_name=name: self.set_filter(b_name))
            self.filter_buttons[name] = btn
            buttons_layout.addWidget(btn)

        buttons_layout.addStretch() 
        layout.addLayout(buttons_layout)
        
        self.update_filter_button_styles()
        
        self.drop_zone = QLabel("📁 Drag & Drop .dll files, mod folders, or regulation.bin here to install mods")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e; border: 2px dashed #3d3d3d; border-radius: 12px;
                padding: 20px; font-size: 14px; color: #888888; margin: 8px 0px;
            }
        """)
        self.drop_zone.setFixedHeight(80)
        layout.addWidget(self.drop_zone)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        # Items per page selector
        items_per_page_layout = QHBoxLayout()
        items_per_page_layout.addWidget(QLabel("Items per page:"))
        self.items_per_page_spinbox = QSpinBox()
        self.items_per_page_spinbox.setRange(5, 50)
        self.items_per_page_spinbox.setValue(self.mods_per_page)
        self.items_per_page_spinbox.valueChanged.connect(self.change_items_per_page)
        self.items_per_page_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 4px; color: #ffffff; min-width: 60px;
            }
        """)
        items_per_page_layout.addWidget(self.items_per_page_spinbox)
        items_per_page_layout.addStretch()
        
        pagination_layout.addLayout(items_per_page_layout)
        pagination_layout.addStretch()
        
        # Page navigation
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d; color: white; border: none; border-radius: 4px;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666666; }
        """)
        pagination_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setStyleSheet("color: #ffffff; padding: 0px 12px;")
        pagination_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d; color: white; border: none; border-radius: 4px;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666666; }
        """)
        pagination_layout.addWidget(self.next_btn)
        
        layout.addLayout(pagination_layout)
        
        # Mods container (no scroll area needed)
        self.mods_widget = QWidget()
        self.mods_layout = QVBoxLayout(self.mods_widget)
        self.mods_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mods_layout.setSpacing(4)
        self.mods_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e; border: 1px solid #3d3d3d; border-radius: 8px;
                padding: 8px;
            }
        """)
        
        layout.addWidget(self.mods_widget)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)

    def set_filter(self, filter_name: str):
        """Sets the current mod filter and updates the UI."""
        self.current_filter = filter_name
        self.update_filter_button_styles()
        self.apply_filters()

    def update_filter_button_styles(self):
        """Updates the visual style of filter buttons to show the active filter."""
        base_style = """
            QPushButton {{
                background-color: {bg_color}; border: 1px solid {border_color};
                color: {text_color}; border-radius: 6px; padding: 0px 12px;
                font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_bg_color}; border-color: {hover_border_color};
            }}
        """
        
        selected_style = base_style.format(
            bg_color="#0078d4", border_color="#0078d4", text_color="white",
            hover_bg_color="#106ebe", hover_border_color="#106ebe"
        )
        
        default_style = base_style.format(
            bg_color="#3d3d3d", border_color="#4d4d4d", text_color="#cccccc",
            hover_bg_color="#4d4d4d", hover_border_color="#5d5d5d"
        )
        
        for name, button in self.filter_buttons.items():
            if name == self.current_filter:
                button.setStyleSheet(selected_style)
            else:
                button.setStyleSheet(default_style)

    def open_profile_editor(self):
        """Opens the raw .me3 profile editor dialog."""
        editor_dialog = ProfileEditor(self.game_name, self.config_manager, self)
        
        result = editor_dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            self.status_label.setText(f"Profile saved for {self.game_name}. Reloading mod list...")
            self.load_mods()
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def is_valid_mod_folder(self, path: str) -> bool:
        folder_path = Path(path)
        if not folder_path.is_dir():
            return False
        
        acceptable_folders = [
            '_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
            'parts', 'script', 'sd', 'sfx', 'shader', 'sound'
        ]
        
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
                        background-color: #0078d4; border: 2px dashed #ffffff; border-radius: 12px;
                        padding: 20px; font-size: 14px; color: #ffffff; margin: 8px 0px;
                    }
            """)
        
    def dragLeaveEvent(self, event):
        self.drop_zone.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e; border: 2px dashed #3d3d3d; border-radius: 12px;
                padding: 20px; font-size: 14px; color: #888888; margin: 8px 0px;
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
            self.install_folder_mods(mod_folders, regulation_files)
        elif regulation_files:
            self.install_regulation_files(regulation_files)

    def install_regulation_files(self, regulation_files: List[str]):
        from PyQt6.QtWidgets import QInputDialog
        
        for regulation_path in regulation_files:
            try:
                mod_name, ok = QInputDialog.getText(
                    self, "Regulation Mod Name", 
                    "Enter name for this regulation mod:",
                    text="regulation_mod"
                )
                if not ok or not mod_name.strip():
                    continue
                mod_name = mod_name.strip()
                
                mods_dir = self.config_manager.get_mods_dir(self.game_name)
                dest_folder = mods_dir / mod_name
                
                if dest_folder.exists():
                    reply = QMessageBox.question(self, "Mod Exists", 
                                            f"Mod folder '{mod_name}' already exists. Replace it?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        continue
                    shutil.rmtree(dest_folder)
                
                dest_folder.mkdir(parents=True, exist_ok=True)
                dest_path = dest_folder / "regulation.bin"
                shutil.copy2(regulation_path, dest_path)
                
                self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_folder))
                # Ensure the mod is enabled after installation
                self.config_manager.set_mod_enabled(self.game_name, str(dest_folder), True)
                self.status_label.setText(f"Installed regulation mod: {mod_name}")
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install regulation.bin: {str(e)}")

        self.load_mods()
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def install_folder_mods(self, folder_paths: List[str], regulation_files: List[str] = None):
        from PyQt6.QtWidgets import QInputDialog
        
        if not folder_paths: return
        if regulation_files is None: regulation_files = []
        
        if len(folder_paths) > 1:
            mod_name, ok = QInputDialog.getText(self, "Mod Name", f"Enter name for mod containing {len(folder_paths)} folders:", text="new_mod")
            if not ok or not mod_name.strip(): return
            mod_name = mod_name.strip()
            
            mods_dir = self.config_manager.get_mods_dir(self.game_name)
            dest_path = mods_dir / mod_name
            
            if dest_path.exists():
                reply = QMessageBox.question(self, "Mod Exists", f"Mod folder '{mod_name}' already exists. Replace it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return
                shutil.rmtree(dest_path)
            
            dest_path.mkdir(parents=True, exist_ok=True)
            for folder_path in folder_paths:
                try:
                    source_path = Path(folder_path)
                    shutil.copytree(source_path, dest_path / source_path.name)
                except Exception as e:
                    QMessageBox.warning(self, "Install Error", f"Failed to copy folder {source_path.name}: {str(e)}")
            
            for regulation_file in regulation_files:
                try:
                    shutil.copy2(regulation_file, dest_path / "regulation.bin")
                    self.status_label.setText(f"Added regulation.bin to {mod_name}")
                except Exception as e:
                    QMessageBox.warning(self, "Install Error", f"Failed to copy regulation.bin: {str(e)}")
            
            self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))

            # Ensure the mod is enabled after installation
            self.config_manager.set_mod_enabled(self.game_name, str(dest_path), True)
            self.status_label.setText(f"Installed folder mod: {mod_name}")
            
        else:
            folder_path = folder_paths[0]
            try:
                source_path = Path(folder_path)
                acceptable_folders = ['_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event', 'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param', 'parts', 'script', 'sd', 'sfx', 'shader', 'sound']
                
                if source_path.name in acceptable_folders:
                    default_name = f"mod_{source_path.name}"
                    mod_name, ok = QInputDialog.getText(self, "Mod Folder Name", f"Enter name for mod containing '{source_path.name}':", text=default_name)
                    if not ok or not mod_name.strip(): return
                    mod_name = mod_name.strip()
                    
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    dest_path = mods_dir / mod_name
                    
                    if dest_path.exists():
                        reply = QMessageBox.question(self, "Mod Exists", f"Mod folder '{mod_name}' already exists. Replace it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No: return
                        shutil.rmtree(dest_path)
                    
                    dest_path.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_path, dest_path / source_path.name)
                else:
                    mod_name = source_path.name
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    dest_path = mods_dir / mod_name
                    
                    if dest_path.exists():
                        reply = QMessageBox.question(self, "Mod Exists", f"Mod folder '{mod_name}' already exists. Replace it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No: return
                        shutil.rmtree(dest_path)
                    
                    shutil.copytree(source_path, dest_path)
                
                for regulation_file in regulation_files:
                    try:
                        shutil.copy2(regulation_file, dest_path / "regulation.bin")
                        self.status_label.setText(f"Added regulation.bin to {mod_name}")
                    except Exception as e:
                        QMessageBox.warning(self, "Install Error", f"Failed to copy regulation.bin: {str(e)}")
                
                self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))
                
                # Ensure the mod is enabled after installation
                self.config_manager.set_mod_enabled(self.game_name, str(dest_path), True)
                self.status_label.setText(f"Installed folder mod: {mod_name}")
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install folder mod: {str(e)}")
        
        self.load_mods()
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def install_mods(self, dll_files: List[str]):
        installed_count = 0
        for dll_path in dll_files:
            try:
                mod_name = Path(dll_path).name
                dest_path = self.config_manager.get_mods_dir(self.game_name) / mod_name
                
                if dest_path.exists():
                    reply = QMessageBox.question(self, "Mod Exists", f"Mod '{mod_name}' already exists. Replace it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No: continue
                
                shutil.copy2(dll_path, dest_path)
                installed_count += 1
                
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to install {mod_name}: {str(e)}")
        
        if installed_count > 0:
            self.status_label.setText(f"Installed {installed_count} mod(s)")
            self.load_mods()
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def change_items_per_page(self, value):
        """Change the number of items displayed per page"""
        self.mods_per_page = value
        self.config_manager.set_mods_per_page(value)
        self.current_page = 1  # Reset to first page
        self.update_pagination()

    def prev_page(self):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_pagination()

    def next_page(self):
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_pagination()

    def update_pagination(self):
        """Update the pagination display and mod widgets"""
        # Calculate total pages
        total_mods = len(self.filtered_mods)
        self.total_pages = max(1, math.ceil(total_mods / self.mods_per_page))
        
        # Ensure current page is valid
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        
        # Update page label
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        
        # Update button states
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
        
        # Clear current mod widgets
        while self.mods_layout.count():
            child = self.mods_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Calculate which mods to show
        start_idx = (self.current_page - 1) * self.mods_per_page
        end_idx = start_idx + self.mods_per_page
        
        # Get the mods for current page
        mod_items = list(self.filtered_mods.items())[start_idx:end_idx]
        
        # Create widgets for current page mods
        for mod_path, info in mod_items:
            is_enabled = info['enabled']
            is_folder_mod = info.get('is_folder_mod', False)
            has_regulation = info.get('has_regulation', False)
            regulation_active = info.get('regulation_active', False)

            text_color = "#9E9E9E"
            item_bg_color = "transparent"
            mod_type = ""
            type_icon = None

            if is_enabled:
                if regulation_active:
                    text_color = "#FFB347"
                    item_bg_color = "transparent"
                else:
                    text_color = "#81C784"
                    item_bg_color = "transparent"
            
            if regulation_active:
                mod_type = "MOD FOLDER (ACTIVE REGULATION)"
                type_icon = QIcon(resource_path("resources/icon/regulation_active.png"))
            elif has_regulation:
                mod_type = "MOD FOLDER WITH REGULATION"
                type_icon = QIcon(resource_path("resources/icon/folder.png"))
            elif is_folder_mod:
                mod_type = "MOD FOLDER"
                type_icon = QIcon(resource_path("resources/icon/folder.png"))
            else:
                mod_type = "DLL"
                type_icon = QIcon(resource_path("resources/icon/dll.png"))
            
            mod_widget = ModItem(mod_path, info['name'], is_enabled, info['external'], 
                               is_folder_mod, has_regulation, mod_type, type_icon, 
                               item_bg_color, text_color, regulation_active)
            
            # Connect signals
            mod_widget.toggled.connect(self.toggle_mod)
            mod_widget.delete_requested.connect(self.delete_mod)
            mod_widget.edit_config_requested.connect(self.open_config_editor)
            mod_widget.open_folder_requested.connect(self.open_mod_folder)
            
            if has_regulation:
                mod_widget.regulation_activate_requested.connect(self.activate_regulation_mod)
            
            self.mods_layout.addWidget(mod_widget)
        
        # Update status
        total_mods = len(self.filtered_mods)
        enabled_mods = sum(1 for info in self.filtered_mods.values() if info['enabled'])
        showing_start = start_idx + 1 if total_mods > 0 else 0
        showing_end = min(end_idx, total_mods)
        
        self.status_label.setText(f"Showing {showing_start}-{showing_end} of {total_mods} mods ({enabled_mods} enabled)")

    def load_mods(self):
        """Load mods and refresh the display"""
        self.apply_filters()
    
    def activate_regulation_mod(self, mod_path: str):
        mod_name = Path(mod_path).name
        try:
            self.config_manager.set_regulation_active(self.game_name, mod_name)
            self.load_mods()
            self.status_label.setText(f"Set {mod_name} as active regulation")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        except Exception as e:
            QMessageBox.warning(self, "Regulation Error", f"Failed to set regulation active: {str(e)}")

    def apply_filters(self):
        """Apply search and category filters, then update pagination"""
        search_text = self.search_bar.text().lower()
        
        # Get all mods info
        all_mods = self.config_manager.get_mods_info(self.game_name)
        self.filtered_mods = {}
        
        for mod_path, info in all_mods.items():
            # Check search filter
            name_match = search_text in info['name'].lower()
            
            # Check category filter
            category_match = False
            is_enabled = info['enabled']
            is_folder_mod = info.get('is_folder_mod', False)
            has_regulation = info.get('has_regulation', False)
            
            if self.current_filter == "all":
                category_match = True
            elif self.current_filter == "enabled":
                category_match = is_enabled
            elif self.current_filter == "disabled":
                category_match = not is_enabled
            elif self.current_filter == "with_regulation":
                category_match = is_folder_mod and is_enabled and has_regulation
            elif self.current_filter == "without_regulation":
                category_match = is_folder_mod and is_enabled and not has_regulation
            
            if name_match and category_match:
                self.filtered_mods[mod_path] = info
        
        # Reset to first page when filters change
        self.current_page = 1
        self.update_pagination()
    
    def toggle_mod(self, mod_path: str, enabled: bool):
        try:
            self.config_manager.set_mod_enabled(self.game_name, mod_path, enabled)
            self.load_mods()
            self.status_label.setText(f"{'Enabled' if enabled else 'Disabled'} {Path(mod_path).name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        except Exception as e:
            QMessageBox.warning(self, "Toggle Error", f"Failed to toggle mod: {str(e)}")
    
    def delete_mod(self, mod_path: str):
        mod_name = Path(mod_path).name
        reply = QMessageBox.question(self, "Delete Mod", f"Are you sure you want to delete '{mod_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.config_manager.delete_mod(self.game_name, mod_path)
                self.load_mods()
                self.status_label.setText(f"Deleted {mod_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            except Exception as e:
                QMessageBox.warning(self, "Delete Error", f"Failed to delete mod: {str(e)}")
    
    def add_external_mod(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select External Mod DLL", str(Path.home()), "DLL Files (*.dll)")
        
        if file_name:
            try:
                mod_path = str(Path(file_name))
                mod_name = Path(mod_path).name
                
                mods_dir = self.config_manager.get_mods_dir(self.game_name)
                if Path(file_name).parent == mods_dir:
                    QMessageBox.information(self, "Mod Info", f"The mod '{mod_name}' is located inside this game's mods folder.\n\nIt should already be in the list. This feature is for adding mods from other locations.")
                    return

                self.config_manager.set_mod_enabled(self.game_name, mod_path, True)
                
                self.status_label.setText(f"Added external mod: {mod_name}")
                self.load_mods()
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                
            except Exception as e:
                QMessageBox.warning(self, "Add Error", f"Failed to add external mod: {str(e)}")
                
    def open_mod_folder(self, mod_path: str):
        try:
            folder_path = Path(mod_path).parent
            if sys.platform == "win32": os.startfile(folder_path)
            elif sys.platform == "darwin": subprocess.call(["open", folder_path])
            else: subprocess.call(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open folder: {str(e)}")
    
    def get_default_config_path(self, mod_path_str: str) -> Path:
        mod_path = Path(mod_path_str)
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def open_config_editor(self, mod_path: str):
        mod_name = Path(mod_path).stem
        initial_config_path = self.config_manager.get_mod_config_path(self.game_name, mod_path)
        dialog = ConfigEditorDialog(mod_name, initial_config_path, self)
        dialog.exec()
        
        if dialog.new_path_selected and dialog.new_path_selected != initial_config_path:
            self.config_manager.set_mod_config_path(self.game_name, mod_path, str(dialog.new_path_selected))
            self.status_label.setText(f"Saved new config path for {mod_name}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def open_mods_folder(self):
        try:
            mods_dir = self.config_manager.get_mods_dir(self.game_name)
            if not mods_dir.exists():
                QMessageBox.warning(self, "Folder Not Found", f"The mods directory does not exist yet:\n{mods_dir}")
                return

            if sys.platform == "win32": os.startfile(str(mods_dir))
            elif sys.platform == "darwin": subprocess.call(["open", str(mods_dir)])
            else: subprocess.call(["xdg-open", str(mods_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open mods folder: {str(e)}")
    
    def set_custom_exe_path(self):
        current_path = self.config_manager.get_game_exe_path(self.game_name)
        
        if current_path:
            reply = QMessageBox.question(self, "Custom Executable Path", f"Current custom executable path:\n{current_path}\n\nDo you want to change it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Reset)
            
            if reply == QMessageBox.StandardButton.No: return
            elif reply == QMessageBox.StandardButton.Reset:
                self.config_manager.set_game_exe_path(self.game_name, None)
                self.status_label.setText(f"Cleared custom executable path for {self.game_name}")
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                return
        
        file_name, _ = QFileDialog.getOpenFileName(self, f"Select {self.game_name} Executable", str(Path.home()), "Executable Files (*.exe);;All Files (*)")
        
        if file_name:
            try:
                self.config_manager.set_game_exe_path(self.game_name, file_name)
                self.status_label.setText(f"Set custom executable path for {self.game_name}")
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                
            except Exception as e:
                QMessageBox.warning(self, "Set Path Error", f"Failed to set custom executable path: {str(e)}")
    
    def run_me3_with_custom_exe(self, exe_path: str, cli_id: str, profile_name: str, terminal):
        from PyQt6.QtCore import QProcess
        
        display_command = f'me3 launch --exe "{exe_path}" --skip-steam-init --game {cli_id} -p {profile_name}'
        terminal.output.append(f"$ {display_command}")
        
        if terminal.process is not None:
            terminal.process.kill()
            terminal.process.waitForFinished(1000)
        
        terminal.process = QProcess(terminal)
        terminal.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        terminal.process.readyReadStandardOutput.connect(terminal.handle_stdout)
        terminal.process.finished.connect(terminal.process_finished)
        
        args = ["launch", "--exe", exe_path, "--skip-steam-init", "--game", cli_id, "-p", profile_name]
        terminal.process.start("me3", args)
    
    def launch_game(self):
        try:
            profile_path = self.config_manager.get_profile_path(self.game_name)
            if not profile_path.exists():
                QMessageBox.warning(self, "Launch Error", f"Profile file not found: {profile_path}")
                return
            
            custom_exe_path = self.config_manager.get_game_exe_path(self.game_name)
            
            main_window = self.window()
            if hasattr(main_window, "terminal"):
                if custom_exe_path:
                    cli_id = self.config_manager.get_game_cli_id(self.game_name)
                    profile_name = profile_path.stem
                    
                    if cli_id and profile_name:
                        self.run_me3_with_custom_exe(custom_exe_path, cli_id, profile_name, main_window.terminal)
                        self.status_label.setText(f"Launching {self.game_name} with custom executable...")
                    else:
                        QMessageBox.warning(self, "Launch Error", f"Could not determine CLI ID for {self.game_name}")
                        return
                else:
                    profile_path_str = str(profile_path.resolve())
                    main_window.terminal.run_command(profile_path_str)
                    self.status_label.setText(f"Launching {self.game_name}...")
                
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            else:
                if custom_exe_path:
                    QMessageBox.information(self, "Custom Executable", "Custom executable paths require the terminal feature. Launching with default method instead.")
                
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
