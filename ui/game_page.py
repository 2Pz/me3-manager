import shutil
import subprocess
from pathlib import Path
from typing import List
import math
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QMessageBox, QFileDialog, QDialog, QSpinBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QIcon, QDesktopServices
from utils.resource_path import resource_path
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
        
        self.acceptable_folders = [
            '_backup', '_unknown', 'action', 'asset', 'chr', 'cutscene', 'event',
            'font', 'map', 'material', 'menu', 'movie', 'msg', 'other', 'param',
            'parts', 'script', 'sd', 'sfx', 'shader', 'sound'
        ]
        
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
        
        pagination_layout = QHBoxLayout()
        
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

    def _open_path(self, path: Path):
        try:
            url = QUrl.fromLocalFile(str(path))
            if not QDesktopServices.openUrl(url):
                raise Exception("QDesktopServices failed to open URL.")
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", f"Failed to open folder:\n{path}\n\nError: {str(e)}")

    def set_filter(self, filter_name: str):
        self.current_filter = filter_name
        self.update_filter_button_styles()
        self.apply_filters()

    def update_filter_button_styles(self):
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
        editor_dialog = ProfileEditor(self.game_name, self.config_manager, self)
        if editor_dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_label.setText(f"Profile saved for {self.game_name}. Reloading mod list...")
            self.load_mods()
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def is_valid_drop(self, paths: List[Path]) -> bool:
        """
        Recursively checks if the dropped paths contain at least one valid mod file.
        A valid mod file is a .dll, regulation.bin, or an acceptable folder name.
        """
        paths_to_check = deque(paths)
        
        while paths_to_check:
            path = paths_to_check.popleft()
            if not path.exists():
                continue

            # Check for valid file types
            if path.is_file():
                if path.suffix.lower() == '.dll' or path.name.lower() == 'regulation.bin':
                    return True
            
            # Check for valid folder names and queue contents for checking
            elif path.is_dir():
                if path.name in self.acceptable_folders:
                    return True
                try:
                    # If it's a folder, check its contents
                    for item in path.iterdir():
                        paths_to_check.append(item)
                except OSError:
                    # Ignore directories we can't read
                    continue
        
        return False

    def dragEnterEvent(self, event: QDragEnterEvent):
        if not event.mimeData().hasUrls():
            return
        
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        
        if self.is_valid_drop(paths):
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
        
        dropped_paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if Path(url.toLocalFile()).exists()]
        if not dropped_paths:
            return

        # The drop has already been validated by dragEnterEvent, so we can proceed.
        root_packages = []
        loose_items = []

        if len(dropped_paths) == 1 and dropped_paths[0].is_dir():
            root_packages.append(dropped_paths[0])
        else:
            loose_items.extend(dropped_paths)

        installed_something = False
        if root_packages:
            for pkg_path in root_packages:
                self.install_root_mod_package(pkg_path)
            installed_something = True

        if loose_items:
            self.install_loose_items(loose_items)
            installed_something = True
        
        if installed_something:
            self.load_mods(reset_page=False)
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def install_root_mod_package(self, root_path: Path):
        default_name = root_path.name
        mod_name, ok = QInputDialog.getText(self, "Name Mod Package",
                                            "Enter a name for this mod package.\n"
                                            "DLLs will be installed as separate mods.\n"
                                            "All other content will be grouped under this name.",
                                            text=default_name)
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()

        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        dest_folder_path = mods_dir / mod_name
        
        all_content = list(root_path.iterdir())
        dlls_to_install = [p for p in all_content if p.suffix.lower() == '.dll']
        other_content_to_install = [p for p in all_content if p.suffix.lower() != '.dll']
        
        existing_dll_paths = [mods_dir / dll.name for dll in dlls_to_install if (mods_dir / dll.name).exists()]
        folder_mod_exists = dest_folder_path.exists() and other_content_to_install

        if existing_dll_paths or folder_mod_exists:
            conflict_msg = f"The mod package '{mod_name}' conflicts with existing mods. Overwrite?\n\n"
            if folder_mod_exists:
                conflict_msg += f"- Folder Mod: {mod_name}\n"
            for path in existing_dll_paths:
                conflict_msg += f"- DLL Mod: {path.name}\n"
            
            reply = QMessageBox.question(self, "Confirm Overwrite", conflict_msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

            if folder_mod_exists and dest_folder_path.exists():
                shutil.rmtree(dest_folder_path)
            for path in existing_dll_paths:
                if path.exists():
                    path.unlink()

        installed_dlls = False
        installed_folder_mod = False

        for dll_path in dlls_to_install:
            try:
                shutil.copy2(dll_path, mods_dir / dll_path.name)
                installed_dlls = True
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to copy DLL {dll_path.name}: {e}")

        if other_content_to_install:
            try:
                dest_folder_path.mkdir(parents=True, exist_ok=True)
                for item in other_content_to_install:
                    dest_item_path = dest_folder_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest_item_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest_item_path)
                
                self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_folder_path))
                self.config_manager.set_mod_enabled(self.game_name, str(dest_folder_path), True)
                installed_folder_mod = True
            except Exception as e:
                QMessageBox.warning(self, "Install Error", f"Failed to create folder mod '{mod_name}': {e}")
                if dest_folder_path.exists():
                    shutil.rmtree(dest_folder_path)

        if installed_dlls or installed_folder_mod:
            self.status_label.setText(f"Successfully installed components from '{root_path.name}'.")
        else:
            QMessageBox.information(self, "Installation Info", f"No content found to install in '{root_path.name}'.")

    def install_loose_items(self, items_to_install: List[Path]):
        if not items_to_install:
            return

        item_count = len(items_to_install)
        item_desc = f"{item_count} item{'s' if item_count > 1 else ''}"
        
        mod_name, ok = QInputDialog.getText(self, "New Mod Name", f"Enter a name for the new mod containing these {item_desc}:", text="new_bundled_mod")
        if not ok or not mod_name.strip():
            return
        
        mod_name = mod_name.strip()
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        dest_path = mods_dir / mod_name

        if dest_path.exists():
            reply = QMessageBox.question(self, "Mod Exists", f"Mod folder '{mod_name}' already exists. Replace it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
            shutil.rmtree(dest_path)
        
        dest_path.mkdir(parents=True, exist_ok=True)

        try:
            for item in items_to_install:
                dest_item_path = dest_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item_path)
            
            self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))
            self.config_manager.set_mod_enabled(self.game_name, str(dest_path), True)
            self.status_label.setText(f"Installed bundled mod: {mod_name}")
        except Exception as e:
            QMessageBox.warning(self, "Install Error", f"Failed to bundle items into mod '{mod_name}': {e}")
            if dest_path.exists():
                shutil.rmtree(dest_path)
    
    def change_items_per_page(self, value):
        self.mods_per_page = value
        self.config_manager.set_mods_per_page(value)
        self.current_page = 1
        self.update_pagination()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_pagination()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_pagination()

    def update_pagination(self):
        total_mods = len(self.filtered_mods)
        self.total_pages = max(1, math.ceil(total_mods / self.mods_per_page))
        
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
        
        while self.mods_layout.count():
            child = self.mods_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        start_idx = (self.current_page - 1) * self.mods_per_page
        end_idx = start_idx + self.mods_per_page
        
        mod_items = list(self.filtered_mods.items())[start_idx:end_idx]
        
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
                text_color = "#81C784"
                if regulation_active:
                    text_color = "#FFB347"
            
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
            
            mod_widget.toggled.connect(self.toggle_mod)
            mod_widget.delete_requested.connect(self.delete_mod)
            mod_widget.edit_config_requested.connect(self.open_config_editor)
            mod_widget.open_folder_requested.connect(self.open_mod_folder)
            
            if has_regulation:
                mod_widget.regulation_activate_requested.connect(self.activate_regulation_mod)
            
            self.mods_layout.addWidget(mod_widget)
        
        total_mods_filtered = len(self.filtered_mods)
        enabled_mods_filtered = sum(1 for info in self.filtered_mods.values() if info['enabled'])
        showing_start = start_idx + 1 if total_mods_filtered > 0 else 0
        showing_end = min(end_idx, total_mods_filtered)
        
        self.status_label.setText(f"Showing {showing_start}-{showing_end} of {total_mods_filtered} mods ({enabled_mods_filtered} enabled)")

    def load_mods(self, reset_page: bool = True):
        self.config_manager.sync_profile_with_filesystem(self.game_name)
        self.apply_filters(reset_page=reset_page)
    
    def activate_regulation_mod(self, mod_path: str):
        mod_name = Path(mod_path).name
        try:
            self.config_manager.set_regulation_active(self.game_name, mod_name)
            self.load_mods(reset_page=False)
            self.status_label.setText(f"Set {mod_name} as active regulation")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        except Exception as e:
            QMessageBox.warning(self, "Regulation Error", f"Failed to set regulation active: {str(e)}")

    def apply_filters(self, reset_page: bool = True):
        search_text = self.search_bar.text().lower()
        all_mods = self.config_manager.get_mods_info(self.game_name)
        self.filtered_mods = {}
        
        for mod_path, info in all_mods.items():
            name_match = search_text in info['name'].lower()
            
            is_enabled = info['enabled']
            is_folder_mod = info.get('is_folder_mod', False)
            has_regulation = info.get('has_regulation', False)
            
            category_match = False
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
        
        if reset_page:
            self.current_page = 1
        self.update_pagination()
    
    def toggle_mod(self, mod_path: str, enabled: bool):
        try:
            self.config_manager.set_mod_enabled(self.game_name, mod_path, enabled)
            self.load_mods(reset_page=False)
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
                self.load_mods(reset_page=False)
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
                    QMessageBox.information(self, "Mod Info", f"The mod '{mod_name}' is inside this game's mods folder and should already be listed.")
                    return

                # First, track it so we remember it even when disabled.
                self.config_manager.track_external_mod(self.game_name, mod_path)
                
                self.config_manager.set_mod_enabled(self.game_name, mod_path, True)
                
                self.status_label.setText(f"Added external mod: {mod_name}")
                self.load_mods(reset_page=False)
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                
            except Exception as e:
                QMessageBox.warning(self, "Add Error", f"Failed to add external mod: {str(e)}")
                
    def open_mod_folder(self, mod_path: str):
        folder_path = Path(mod_path).parent
        self._open_path(folder_path)
    
    def get_default_config_path(self, mod_path_str: str) -> Path:
        mod_path = Path(mod_path_str)
        config_dir = mod_path.parent / mod_path.stem
        return config_dir / "config.ini"

    def open_config_editor(self, mod_path: str):
        mod_name = Path(mod_path).stem
        initial_config_path = self.config_manager.get_mod_config_path(self.game_name, mod_path)
        dialog = ConfigEditorDialog(mod_name, initial_config_path, self)
        
        if dialog.exec() and dialog.new_path_selected and dialog.new_path_selected != initial_config_path:
            self.config_manager.set_mod_config_path(self.game_name, mod_path, str(dialog.new_path_selected))
            self.status_label.setText(f"Saved new config path for {mod_name}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def open_mods_folder(self):
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        if not mods_dir.exists():
            QMessageBox.warning(self, "Folder Not Found", f"The mods directory does not exist yet:\n{mods_dir}")
            return
        self._open_path(mods_dir)
    
    def set_custom_exe_path(self):
        QMessageBox.warning(
            self,
            "Non-Recommended Action",
            "It is recommended to avoid setting a custom game executable path unless ME3 cannot detect your game installation automatically.\n\n"
            "Only use this option if your game is installed in a non-standard location."
        )

        current_path = self.config_manager.get_game_exe_path(self.game_name)
        
        if current_path:
            reply = QMessageBox.question(self, "Custom Executable Path",
                f"Current custom executable path:\n{current_path}\n\nDo you want to change it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Reset)
            
            if reply == QMessageBox.StandardButton.No: return
            if reply == QMessageBox.StandardButton.Reset:
                self.config_manager.set_game_exe_path(self.game_name, None)
                self.status_label.setText(f"Cleared custom executable path for {self.game_name}")
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                return
        
        expected_exe_name = self.config_manager.get_game_executable_name(self.game_name)
        if not expected_exe_name:
            QMessageBox.critical(self, "Configuration Error", f"Expected executable name for '{self.game_name}' is not defined.")
            return

        file_name, _ = QFileDialog.getOpenFileName(self, f"Select {self.game_name} Executable ({expected_exe_name})",
            str(Path.home()), "Executable Files (*.exe);;All Files (*)")
        
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
                QMessageBox.warning(self, "Launch Error", f"Profile file not found:\n{profile_path}")
                return
            
            cli_id = self.config_manager.get_game_cli_id(self.game_name)
            if not cli_id:
                QMessageBox.warning(self, "Launch Error", f"Could not determine CLI ID for {self.game_name}")
                return

            main_window = self.window()
            custom_exe_path = self.config_manager.get_game_exe_path(self.game_name)

            if custom_exe_path:
                if hasattr(main_window, "terminal"):
                    self.run_me3_with_custom_exe(custom_exe_path, cli_id, profile_path.stem, main_window.terminal)
                    self.status_label.setText(f"Launching {self.game_name} with custom executable...")
                    QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                    return
                else:
                    QMessageBox.information(self, "Launch Info", "Custom executable launch requires the terminal. This setting will be ignored.")
            
            command_args_list = ["me3", "launch", "--game", cli_id, "-p", profile_path.stem]
            
            if hasattr(main_window, "terminal"):
                main_window.terminal.run_command(" ".join(command_args_list))
            else:
                subprocess.Popen(command_args_list)
            
            self.status_label.setText(f"Launching {self.game_name}...")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                                
        except Exception as e:
            QMessageBox.warning(self, "Launch Error", f"Failed to launch game: {e}")