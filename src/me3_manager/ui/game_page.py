import math
import os
import shlex
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QProcess, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QAction,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
)
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from me3_manager.core.mod_manager import ImprovedModManager, ModStatus, ModType
from me3_manager.ui.advanced_mod_options import AdvancedModOptionsDialog
from me3_manager.ui.config_editor import ConfigEditorDialog
from me3_manager.ui.game_options_dialog import GameOptionsDialog
from me3_manager.ui.mod_item import ModItem
from me3_manager.ui.profile_editor import ProfileEditor
from me3_manager.ui.profile_settings_dialog import ProfileSettingsDialog
from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr


class GamePage(QWidget):
    """Widget for managing mods for a specific game"""

    def __init__(self, game_name: str, config_manager):
        super().__init__()
        self.game_name = game_name
        self.config_manager = config_manager
        self.mod_manager = ImprovedModManager(config_manager)
        self.mod_widgets = {}
        self.current_filter = "all"
        self.filter_buttons = {}

        # Pagination settings
        self.mods_per_page = self.config_manager.get_mods_per_page()
        self.current_page = 1
        self.total_pages = 1
        self.filtered_mods = {}

        self.acceptable_folders = [
            "_backup",
            "_unknown",
            "action",
            "asset",
            "chr",
            "cutscene",
            "event",
            "font",
            "map",
            "material",
            "menu",
            "movie",
            "msg",
            "other",
            "param",
            "parts",
            "script",
            "sd",
            "sfx",
            "shader",
            "sound",
        ]

        self.setAcceptDrops(True)
        self.init_ui()
        self.load_mods()

    def init_ui(self):
        """Initialize the main UI components."""
        self.main_layout = QVBoxLayout()
        self._setup_layout_properties()

        # Build UI sections in logical order
        self._create_header_section()
        self._create_search_section()
        self._create_filter_section()
        self._create_drop_zone()
        self._create_pagination_section()
        self._create_mods_section()
        self._create_status_section()

        self.setLayout(self.main_layout)
        self._setup_file_watcher()

    def _setup_layout_properties(self):
        """Configure main layout properties."""
        self.main_layout.setSpacing(12)
        self.main_layout.setContentsMargins(24, 24, 24, 24)

    def _create_header_section(self):
        """Create the header with title and action buttons."""
        header_layout = QHBoxLayout()

        # Title
        title = self._create_title_label()
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Profile selector
        profile_widget = self._create_profile_selector()
        header_layout.addLayout(profile_widget)

        # Action buttons
        action_buttons = self._create_action_buttons()
        for button in action_buttons:
            header_layout.addWidget(button)

        self.main_layout.addLayout(header_layout)

    def _create_title_label(self):
        """Create and style the main title label."""
        title = QLabel(tr("game_mods_title", game_name=self.game_name))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 8px;")
        return title

    def _create_profile_selector(self):
        """Create an enhanced profile selector with modern styling."""
        # Create container widget for better control
        profile_container = QWidget()
        profile_container.setFixedHeight(44)
        profile_container.setMinimumWidth(220)

        # Main layout
        container_layout = QHBoxLayout(profile_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Enhanced profile label with icon
        profile_label = QLabel(tr("profile_label"))
        profile_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        profile_label.setFixedWidth(90)
        profile_label.setStyleSheet(self._get_enhanced_profile_label_style())

        # Enhanced dropdown button
        self.profile_menu_button = QPushButton(tr("select_profile_button"))
        self.profile_menu_button.setFixedHeight(44)
        self.profile_menu_button.setMinimumWidth(130)
        self.profile_menu_button.setStyleSheet(
            self._get_enhanced_profile_button_style()
        )

        # Enhanced menu
        self.profile_menu = QMenu(self)
        self.profile_menu.setStyleSheet(self._get_enhanced_profile_menu_style())
        self.profile_menu_button.setMenu(self.profile_menu)

        container_layout.addWidget(profile_label)
        container_layout.addWidget(self.profile_menu_button)

        # Wrap in layout to return
        wrapper_layout = QHBoxLayout()
        wrapper_layout.addWidget(profile_container)

        return wrapper_layout

    def _create_action_buttons(self):
        """Create all header action buttons."""
        buttons = []

        # Launch button
        self.launch_btn = QPushButton(
            tr("launch_game_button", game_name=self.game_name)
        )
        self.launch_btn.setFixedHeight(40)
        self.launch_btn.setStyleSheet(self._get_launch_button_style())
        self.launch_btn.clicked.connect(self.launch_game)
        buttons.append(self.launch_btn)

        # Icon buttons configuration
        icon_buttons_config = [
            {
                "attr": "game_options_btn",
                "icon": "game_options.svg",
                "tooltip": tr("configure_game_options_tooltip"),
                "callback": self.open_game_options,
            },
            {
                "attr": "profile_settings_btn",
                "icon": "profiles.svg",
                "tooltip": tr("profile_settings_tooltip"),
                "callback": self.open_profile_settings,
            },
            {
                "attr": "open_mods_folder_btn",
                "icon": "folder.svg",
                "tooltip": tr("open_mods_folder_tooltip"),
                "callback": self.open_mods_folder,
            },
            {
                "attr": "add_external_mod_btn",
                "icon": "dll.svg",
                "tooltip": tr("add_external_mod_tooltip"),
                "callback": self.add_external_mod,
            },
            {
                "attr": "edit_profile_btn",
                "icon": "note.svg",
                "tooltip": tr("edit_profile_tooltip"),
                "callback": self.open_profile_editor,
            },
        ]

        for config in icon_buttons_config:
            button = self._create_icon_button(config)
            setattr(self, config["attr"], button)
            buttons.append(button)

        return buttons

    def _create_icon_button(self, config):
        """Create a standardized icon button."""
        button = QPushButton(
            QIcon(resource_path(f"resources/icon/{config['icon']}")), ""
        )
        button.setIconSize(QSize(40, 40))
        button.setFixedSize(60, 60)
        button.setToolTip(config["tooltip"])
        button.setStyleSheet(self._get_icon_button_style())
        button.clicked.connect(config["callback"])
        return button

    def _create_search_section(self):
        """Create the search bar."""
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(tr("search_mods_placeholder"))
        self.search_bar.setStyleSheet(self._get_search_bar_style())
        self.search_bar.textChanged.connect(self.apply_filters)
        self.main_layout.addWidget(self.search_bar)

    def _create_filter_section(self):
        """Create the filter buttons section."""
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 4, 0, 0)

        filter_definitions = self._get_filter_definitions()

        for filter_name, (text, tooltip) in filter_definitions.items():
            button = self._create_filter_button(filter_name, text, tooltip)
            self.filter_buttons[filter_name] = button
            buttons_layout.addWidget(button)

        buttons_layout.addStretch()
        self.main_layout.addLayout(buttons_layout)
        self.update_filter_button_styles()

    def _create_filter_button(self, filter_name, text, tooltip):
        """Create a single filter button."""
        button = QPushButton(text)
        button.setFixedHeight(32)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.clicked.connect(lambda checked, name=filter_name: self.set_filter(name))
        return button

    def _create_drop_zone(self):
        """Create the drag and drop zone."""
        self.drop_zone = QLabel(tr("drag_drop_zone_text"))
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setStyleSheet(self._get_drop_zone_style())
        self.drop_zone.setFixedHeight(80)
        self.main_layout.addWidget(self.drop_zone)

    def _create_pagination_section(self):
        """Create the pagination controls."""
        pagination_layout = QHBoxLayout()

        # Items per page controls
        items_per_page_layout = self._create_items_per_page_controls()
        pagination_layout.addLayout(items_per_page_layout)
        pagination_layout.addStretch()

        # Navigation buttons
        nav_buttons = self._create_pagination_buttons()
        for widget in nav_buttons:
            pagination_layout.addWidget(widget)

        self.main_layout.addLayout(pagination_layout)

    def _create_items_per_page_controls(self):
        """Create the items per page selector."""
        layout = QHBoxLayout()

        label = QLabel(tr("items_per_page_label"))
        layout.addWidget(label)

        self.items_per_page_spinbox = QSpinBox()
        self.items_per_page_spinbox.setRange(1, 50)
        self.items_per_page_spinbox.setValue(self.mods_per_page)
        self.items_per_page_spinbox.setStyleSheet(self._get_spinbox_style())
        self.items_per_page_spinbox.valueChanged.connect(self.change_items_per_page)
        layout.addWidget(self.items_per_page_spinbox)

        layout.addStretch()
        return layout

    def _create_pagination_buttons(self):
        """Create pagination navigation buttons."""
        widgets = []

        # Previous button
        self.prev_btn = QPushButton(tr("previous_page_button"))
        self.prev_btn.setStyleSheet(self._get_pagination_button_style())
        self.prev_btn.clicked.connect(self.prev_page)
        widgets.append(self.prev_btn)

        # Page label
        self.page_label = QLabel(tr("page_label_text", current_page=1, total_pages=1))
        self.page_label.setStyleSheet("color: #ffffff; padding: 0px 12px;")
        widgets.append(self.page_label)

        # Next button
        self.next_btn = QPushButton(tr("next_page_button"))
        self.next_btn.setStyleSheet(self._get_pagination_button_style())
        self.next_btn.clicked.connect(self.next_page)
        widgets.append(self.next_btn)

        return widgets

    def _create_mods_section(self):
        """Create the main mods display area."""
        self.mods_widget = QWidget()
        self.mods_layout = QVBoxLayout(self.mods_widget)
        self.mods_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.mods_layout.setSpacing(4)
        self.mods_widget.setStyleSheet(self._get_mods_widget_style())
        self.main_layout.addWidget(self.mods_widget)

    def _create_status_section(self):
        """Create the status bar."""
        self.status_label = QLabel(tr("status_ready"))
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.main_layout.addWidget(self.status_label)

    def _setup_file_watcher(self):
        """Setup file system monitoring."""
        self.reload_timer = QTimer(self)
        self.reload_timer.setSingleShot(True)
        self.reload_timer.timeout.connect(lambda: self.load_mods(reset_page=False))

    # profile dropdown
    def _get_enhanced_profile_label_style(self):
        """Return modern, simple CSS style for profile label."""
        return """
            QLabel {
                background-color: #2c2c2c;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                padding: 12px 16px;
                border: none;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                min-height: 20px;
            }
        """

    def _get_enhanced_profile_button_style(self):
        """Return modern, simple CSS style for profile button."""
        return """
            QPushButton {
                background-color: #404040;
                border: none;
                color: #ffffff;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 12px 16px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #106ebe;
            }
            QPushButton::menu-indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
        """

    def _get_enhanced_profile_menu_style(self):
        """Return modern, simple CSS style for profile menu."""
        return """
            QMenu {
                background-color: #2c2c2c;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                color: #ffffff;
                padding: 10px 16px;
                border-radius: 4px;
                margin: 1px;
                font-size: 14px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QMenu::item:pressed {
                background-color: #106ebe;
            }
            QMenu::separator {
                height: 1px;
                background-color: #404040;
                margin: 4px 8px;
            }
        """

    def _get_launch_button_style(self):
        """Return CSS style for launch button."""
        return """
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
        """

    def _get_icon_button_style(self):
        """Return CSS style for icon buttons."""
        return """
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
        """

    def _get_search_bar_style(self):
        """Return CSS style for search bar."""
        return """
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
        """

    def _get_drop_zone_style(self):
        """Return CSS style for drop zone."""
        return """
            QLabel {
                background-color: #1e1e1e;
                border: 2px dashed #3d3d3d;
                border-radius: 12px;
                padding: 20px;
                font-size: 14px;
                color: #888888;
                margin: 8px 0px;
            }
        """

    def _get_spinbox_style(self):
        """Return CSS style for spinbox."""
        return """
            QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
                min-width: 60px;
            }
        """

    def _get_pagination_button_style(self):
        """Return CSS style for pagination buttons."""
        return """
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_mods_widget_style(self):
        """Return CSS style for mods widget."""
        return """
            QWidget {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
            }
        """

    def _get_filter_definitions(self):
        """Return filter button definitions."""
        return {
            "all": (tr("filter_all"), tr("filter_all_tooltip")),
            "enabled": (tr("filter_enabled"), tr("filter_enabled_tooltip")),
            "disabled": (tr("filter_disabled"), tr("filter_disabled_tooltip")),
            "with_regulation": (
                tr("filter_with_regulation"),
                tr("filter_with_regulation_tooltip"),
            ),
            "without_regulation": (
                tr("filter_without_regulation"),
                tr("filter_without_regulation_tooltip"),
            ),
        }

    def update_profile_dropdown(self):
        """Updates the profile dropdown button text and its menu items."""
        active_profile = self.config_manager.get_active_profile(self.game_name)
        if not active_profile:
            return

        self.profile_menu_button.setText(active_profile["name"])

        # Rebuild the menu
        self.profile_menu.clear()

        all_profiles = self.config_manager.get_profiles_for_game(self.game_name)
        active_profile_id = active_profile["id"]

        for profile in all_profiles:
            action = QAction(profile["name"], self)
            action.setData(profile["id"])
            action.setCheckable(True)
            action.setChecked(profile["id"] == active_profile_id)
            action.triggered.connect(self.on_profile_selected_from_menu)
            self.profile_menu.addAction(action)

        self.profile_menu.addSeparator()

        manage_action = QAction(
            QIcon(resource_path("resources/icon/profiles.svg")),
            tr("manage_profiles"),
            self,
        )
        manage_action.triggered.connect(self.open_profile_manager)
        self.profile_menu.addAction(manage_action)

    def on_profile_selected_from_menu(self):
        """Handles when a profile is chosen from the dropdown menu."""
        action = self.sender()
        if isinstance(action, QAction) and action.isChecked():
            profile_id = action.data()
            self.config_manager.set_active_profile(self.game_name, profile_id)
            self.load_mods()

    def is_frozen(self):
        """Check if running as a PyInstaller frozen executable"""
        return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

    def _open_path(self, path: Path):
        try:
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                env = os.environ.copy()
                env.pop("LD_LIBRARY_PATH", None)
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)

                if sys.platform == "win32":
                    subprocess.Popen(["explorer", str(path)], shell=True, env=env)
                else:
                    subprocess.run(["xdg-open", str(path)], env=env)
            else:
                url = QUrl.fromLocalFile(str(path))
                if not QDesktopServices.openUrl(url):
                    raise Exception("QDesktopServices failed to open URL.")
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("open_folder_error"),
                tr("open_folder_error_msg", path=path, e=str(e)),
            )

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
            bg_color="#0078d4",
            border_color="#0078d4",
            text_color="white",
            hover_bg_color="#106ebe",
            hover_border_color="#106ebe",
        )
        default_style = base_style.format(
            bg_color="#3d3d3d",
            border_color="#4d4d4d",
            text_color="#cccccc",
            hover_bg_color="#4d4d4d",
            hover_border_color="#5d5d5d",
        )
        for name, button in self.filter_buttons.items():
            if name == self.current_filter:
                button.setStyleSheet(selected_style)
            else:
                button.setStyleSheet(default_style)

    def open_profile_editor(self):
        editor_dialog = ProfileEditor(self.game_name, self.config_manager, self)
        if editor_dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_label.setText(
                tr("profile_saved_status", game_name=self.game_name)
            )
            self.load_mods()
            QTimer.singleShot(
                2000, lambda: self.status_label.setText(tr("status_ready"))
            )

    def is_valid_drop(self, paths: List[Path]) -> bool:
        paths_to_check = deque(paths)
        while paths_to_check:
            path = paths_to_check.popleft()
            if not path.exists():
                continue
            if path.is_file():
                if (
                    path.suffix.lower() in [".dll", ".me3"]
                    or path.name.lower() == "regulation.bin"
                ):
                    return True
            elif path.is_dir():
                if path.name in self.acceptable_folders:
                    return True
                try:
                    for item in path.iterdir():
                        paths_to_check.append(item)
                except OSError:
                    continue
        return False

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
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
        dropped_paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).exists()
        ]
        if not dropped_paths:
            return

        # Handle .me3 profile imports first, as they are a special case.
        me3_files = [p for p in dropped_paths if p.suffix.lower() == ".me3"]
        if me3_files:
            if len(me3_files) > 1:
                QMessageBox.warning(
                    self,
                    tr("import_error"),
                    tr("import_one_profile_warning"),
                )
                return
            profile_to_import = me3_files[0]
            import_folder = profile_to_import.parent
            self.handle_profile_import(import_folder, profile_to_import)
            return

        # Identify DLLs and their potential config folders.
        dll_paths = {
            p for p in dropped_paths if p.is_file() and p.suffix.lower() == ".dll"
        }
        dll_stems = {dll.stem for dll in dll_paths}

        # Items to be installed directly (DLLs and their config folders)
        linked_items_to_install = set()
        # Items that might be part of a mod package
        items_for_bundling = []

        # First pass: identify and collect all linked items (DLLs and their config folders)
        for path in dropped_paths:
            if path in dll_paths:
                linked_items_to_install.add(path)
            elif path.is_dir() and path.name in dll_stems:
                linked_items_to_install.add(path)

        # Second pass: collect everything else for bundling
        for path in dropped_paths:
            if path not in linked_items_to_install and path.suffix.lower() != ".me3":
                items_for_bundling.append(path)

        installed_something = False

        # Install the DLLs and their config folders without prompting for a name.
        if linked_items_to_install:
            if self.install_linked_mods(list(linked_items_to_install)):
                installed_something = True

        # Handle the remaining loose items, which may be a mod package.
        if items_for_bundling:
            # A single directory that is not a config folder. Treat as a mod package.
            if len(items_for_bundling) == 1 and items_for_bundling[0].is_dir():
                self.install_root_mod_package(items_for_bundling[0])
            else:
                # Multiple files/folders, or a single file. Bundle them.
                self.install_loose_items(items_for_bundling)
            installed_something = True

        if installed_something:
            self.load_mods(reset_page=False)
            QTimer.singleShot(
                3000, lambda: self.status_label.setText(tr("status_ready"))
            )

    def install_linked_mods(self, items_to_install: List[Path]) -> bool:
        """
        Installs a list of items (DLLs and their associated config folders) directly
        into the mods directory without bundling them.
        """
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        conflicts = [p for p in items_to_install if (mods_dir / p.name).exists()]

        if conflicts:
            conflict_msg = tr("overwrite_confirm_text") + "\n".join(
                f"- {p.name}" for p in conflicts
            )
            reply = QMessageBox.question(
                self,
                tr("confirm_overwrite_title"),
                conflict_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                conflict_names = {p.name for p in conflicts}
                items_to_install = [
                    p for p in items_to_install if p.name not in conflict_names
                ]

        if not items_to_install:
            self.status_label.setText(tr("install_cancelled_status"))
            return False

        installed_count = 0
        errors = []
        for item_path in items_to_install:
            try:
                dest_path = mods_dir / item_path.name
                if item_path.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item_path, dest_path)
                else:  # is_file
                    shutil.copy2(item_path, dest_path)
                installed_count += 1
            except Exception as e:
                errors.append(f"Failed to copy {item_path.name}: {e}")

        if errors:
            QMessageBox.warning(self, tr("install_error_title"), "\n".join(errors))

        if installed_count > 0:
            self.status_label.setText(
                tr("install_success_status", count=installed_count)
            )
            return True
        return False

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(
            tr("import_profile_mods_title", game_name=self.game_name)
        )
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(
            f"""{tr("import_profile_mods_desc")}<br><br>
            <b>{tr("profile_label")}:</b> {profile_file.name}<br>
            <b>{tr("from_folder_label")}:</b> {import_folder}<br><br>
            {tr("import_merge_or_replace_question")}"""
        )
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        merge_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        merge_btn.setText(tr("merge_button_recommended"))
        replace_btn = msg_box.button(QMessageBox.StandardButton.No)
        replace_btn.setText(tr("replace_button"))

        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Cancel:
            return
        merge = reply == QMessageBox.StandardButton.Yes

        default_name = import_folder.name
        mod_name, ok = QInputDialog.getText(
            self,
            tr("name_imported_package_title"),
            tr("name_imported_package_desc")
            + tr("importing_from_label", folder=import_folder.name),
            text=default_name,
        )
        if not ok or not mod_name.strip():
            self.status_label.setText(tr("import_cancelled_status"))
            QTimer.singleShot(
                2000, lambda: self.status_label.setText(tr("status_ready"))
            )
            return
        mod_name = mod_name.strip()

        try:
            self.status_label.setText(
                tr("importing_from_status", folder=import_folder.name)
            )

            # Parse the profile to understand the structure
            config_data = self.config_manager._parse_toml_config(profile_file)
            packages = config_data.get("packages", [])

            results = {
                "success": True,
                "profile_imported": False,
                "package_mods_imported": 0,
                "dll_mods_imported": 0,
                "mods_skipped": 0,
                "skipped_details": [],
                "errors": [],
            }

            mods_dir = self.config_manager.get_mods_dir(self.game_name)

            # Import each package from the profile
            for package in packages:
                package_id = package.get("id", "")
                package_path = package.get("path", "")
                package_source = package.get("source", "")

                search_name = package_path or package_source or package_id
                if not package_id or not search_name:
                    continue

                mod_source_path = None
                possible_paths = [
                    import_folder / search_name,
                    import_folder / package_id,
                    import_folder / "Mod",
                    import_folder / "mod",
                ]
                for possible_path in possible_paths:
                    if possible_path.exists() and possible_path.is_dir():
                        mod_source_path = possible_path
                        break

                if not mod_source_path:
                    for item in import_folder.iterdir():
                        if (
                            item.is_dir()
                            and item.name != profile_file.stem
                            and self._is_valid_mod_folder(item)
                        ):
                            mod_source_path = item
                            break

                if not mod_source_path:
                    results["errors"].append(
                        f"Could not find mod folder for package '{package_id}' (searched for: {search_name})"
                    )
                    continue

                dest_mod_path = mods_dir / mod_name

                if dest_mod_path.exists():
                    if not merge:
                        reply = QMessageBox.question(
                            self,
                            tr("mod_exists_title"),
                            tr("mod_folder_exists_replace_question", mod_name=mod_name),
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if reply == QMessageBox.StandardButton.No:
                            results["mods_skipped"] += 1
                            results["skipped_details"].append(
                                tr("skipped_reason_exists", name=mod_name)
                            )
                            continue
                        else:
                            shutil.rmtree(dest_mod_path)

                try:
                    if dest_mod_path.exists():
                        for item in mod_source_path.iterdir():
                            dest_item = dest_mod_path / item.name
                            if item.is_dir():
                                if dest_item.exists():
                                    shutil.rmtree(dest_item)
                                shutil.copytree(item, dest_item)
                            else:
                                shutil.copy2(item, dest_item)
                    else:
                        shutil.copytree(mod_source_path, dest_mod_path)

                    self.config_manager.add_folder_mod(
                        self.game_name, mod_name, str(dest_mod_path)
                    )
                    self.config_manager.set_mod_enabled(
                        self.game_name, str(dest_mod_path), True
                    )
                    results["package_mods_imported"] += 1
                except Exception as e:
                    results["errors"].append(
                        f"Failed to copy mod '{mod_name}': {str(e)}"
                    )

            # Import native DLL mods
            natives = config_data.get("natives", [])
            for native in natives:
                native_path = native.get("path", "")
                if not native_path:
                    continue

                native_path_obj = Path(native_path)
                possible_dll_paths = []

                if mod_source_path:
                    for search_pattern in [native_path, native_path_obj.name]:
                        potential_dll = mod_source_path / search_pattern
                        if potential_dll.exists():
                            possible_dll_paths.append(potential_dll)
                            break

                    dll_name = native_path_obj.name
                    for dll_file in mod_source_path.rglob(dll_name):
                        if dll_file.is_file():
                            possible_dll_paths.append(dll_file)
                            break

                if possible_dll_paths:
                    results["dll_mods_imported"] += 1

            # Import the profile settings (ignoring supports completely)
            try:
                profile_path = self.config_manager.get_profile_path(self.game_name)
                imported_config = self.config_manager._parse_toml_config(profile_file)

                if not merge:
                    updated_packages = []
                    main_mods_dir = self.config_manager.games[self.game_name][
                        "mods_dir"
                    ]
                    updated_packages.append(
                        {
                            "id": main_mods_dir,
                            "path": main_mods_dir,
                            "load_after": [],
                            "load_before": [],
                        }
                    )

                    if results["package_mods_imported"] > 0:
                        updated_packages.append(
                            {
                                "id": mod_name,
                                "path": f"{main_mods_dir}/{mod_name}",
                                "load_after": [],
                                "load_before": [],
                            }
                        )

                    updated_natives = []
                    natives = imported_config.get("natives", [])
                    for native in natives:
                        native_path = native.get("path", "")
                        if not native_path:
                            continue

                        if results["package_mods_imported"] > 0:
                            new_native_path = (
                                f"{main_mods_dir}/{mod_name}/{native_path}"
                            )
                            new_native = native.copy()
                            new_native["path"] = new_native_path
                            updated_natives.append(new_native)

                    imported_config["natives"] = updated_natives
                    self.mod_manager._write_improved_config(
                        profile_path, imported_config, self.game_name
                    )

                results["profile_imported"] = True

            except Exception as e:
                results["errors"].append(f"Failed to import profile: {str(e)}")

            # Show results
            if results["success"] and (
                results["profile_imported"] or results["package_mods_imported"] > 0
            ):
                message_parts = [f"<b>{tr('import_complete_success_header')}</b>"]
                if results["profile_imported"]:
                    message_parts.append(tr("import_profile_success"))
                if results["package_mods_imported"] > 0:
                    message_parts.append(
                        tr(
                            "import_package_mods_success",
                            count=results["package_mods_imported"],
                        )
                    )
                if results["dll_mods_imported"] > 0:
                    message_parts.append(
                        tr(
                            "import_dll_mods_success",
                            count=results["dll_mods_imported"],
                        )
                    )
                if results["mods_skipped"] > 0:
                    skipped_header = f"<b>{tr('import_mods_skipped_header', count=results['mods_skipped'])}</b>"
                    skipped_details = [
                        f"• <i>{detail}</i>"
                        for detail in results.get("skipped_details", [])
                    ]
                    message_parts.append(
                        f"{skipped_header}<br>" + "<br>".join(skipped_details)
                    )
                if results["errors"]:
                    error_header = f"<b>{tr('import_errors_header')}</b>"
                    error_details = [
                        f"• {error}" for error in results.get("errors", [])
                    ]
                    message_parts.append(
                        f"{error_header}<br>" + "<br>".join(error_details)
                    )

                message = "<br>".join(message_parts)
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(tr("import_complete_title"))
                msg_box.setTextFormat(Qt.TextFormat.RichText)
                msg_box.setText(message)
                msg_box.exec()
                self.load_mods()
            else:
                error_msg = f"<b>{tr('import_failed_header')}</b><br>".join(
                    f"• {error}" for error in results["errors"]
                )
                QMessageBox.warning(self, tr("import_failed_title"), error_msg)

        except Exception as e:
            QMessageBox.warning(
                self, tr("import_error_title"), tr("import_error_msg", error=str(e))
            )
        finally:
            self.status_label.setText(tr("status_ready"))

    def _is_valid_mod_folder(self, folder: Path) -> bool:
        """Check if a folder is a valid mod folder"""
        # Check if folder name is in acceptable folders
        if folder.name in self.acceptable_folders:
            return True

        # Check if it contains acceptable subfolders
        if any(
            sub.is_dir() and sub.name in self.acceptable_folders
            for sub in folder.iterdir()
        ):
            return True

        # Check if it has regulation files
        if (folder / "regulation.bin").exists() or (
            folder / "regulation.bin.disabled"
        ).exists():
            return True

        return False

    def install_dll_mods(self, dll_paths: List[Path]) -> bool:
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        conflicts = [p for p in dll_paths if (mods_dir / p.name).exists()]
        if conflicts:
            conflict_msg = tr("overwrite_dll_confirm_text") + "\n".join(
                f"- {p.name}" for p in conflicts
            )
            reply = QMessageBox.question(
                self,
                tr("confirm_overwrite_title"),
                conflict_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                conflict_names = {p.name for p in conflicts}
                dll_paths = [p for p in dll_paths if p.name not in conflict_names]

        if not dll_paths:
            self.status_label.setText(tr("dll_install_cancelled_status"))
            return False

        installed_count = 0
        for dll_path in dll_paths:
            try:
                shutil.copy2(dll_path, mods_dir / dll_path.name)
                installed_count += 1
            except Exception as e:
                QMessageBox.warning(
                    self,
                    tr("install_error_title"),
                    tr("dll_copy_failed_msg", name=dll_path.name, error=e),
                )

        if installed_count > 0:
            self.status_label.setText(
                tr("dll_install_success_status", count=installed_count)
            )
            return True
        return False

    def install_root_mod_package(self, root_path: Path):
        mod_name, ok = QInputDialog.getText(
            self,
            tr("name_mod_package_title"),
            tr("name_mod_package_desc"),
            text=root_path.name,
        )
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        dest_folder_path = mods_dir / mod_name

        if dest_folder_path.exists():
            reply = QMessageBox.question(
                self,
                tr("confirm_overwrite_title"),
                tr("mod_folder_exists_overwrite_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            shutil.rmtree(dest_folder_path)

        try:
            shutil.copytree(root_path, dest_folder_path)
            self.config_manager.add_folder_mod(
                self.game_name, mod_name, str(dest_folder_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_name, str(dest_folder_path), True
            )
            self.status_label.setText(
                tr("install_package_success_status", mod_name=mod_name)
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("install_error_title"),
                tr("create_folder_mod_failed_msg", mod_name=mod_name, error=e),
            )
            if dest_folder_path.exists():
                shutil.rmtree(dest_folder_path)

    def install_loose_items(self, items_to_install: List[Path]):
        if not items_to_install:
            return
        mod_name, ok = QInputDialog.getText(
            self,
            tr("new_mod_name_title"),
            tr("new_mod_name_desc", count=len(items_to_install)),
            text="new_bundled_mod",
        )
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        dest_path = mods_dir / mod_name

        if dest_path.exists():
            reply = QMessageBox.question(
                self,
                tr("mod_exists_title"),
                tr("mod_folder_exists_replace_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            shutil.rmtree(dest_path)

        dest_path.mkdir(parents=True, exist_ok=True)
        try:
            for item in items_to_install:
                if item.is_dir():
                    shutil.copytree(item, dest_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_path / item.name)
            self.config_manager.add_folder_mod(self.game_name, mod_name, str(dest_path))
            self.config_manager.set_mod_enabled(self.game_name, str(dest_path), True)
            self.status_label.setText(
                tr("install_bundled_mod_success_status", mod_name=mod_name)
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("install_error_title"),
                tr("bundle_items_failed_msg", mod_name=mod_name, error=e),
            )
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
        """Update pagination with expandable tree structure"""
        total_mods = len(self.filtered_mods)
        self.total_pages = max(1, math.ceil(total_mods / self.mods_per_page))
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        self.page_label.setText(
            tr(
                "page_label_text",
                current_page=self.current_page,
                total_pages=self.total_pages,
            )
        )
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

        # Clear existing widgets
        while self.mods_layout.count():
            child = self.mods_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        start_idx = (self.current_page - 1) * self.mods_per_page
        end_idx = start_idx + self.mods_per_page
        mod_items = list(self.filtered_mods.items())[start_idx:end_idx]

        # Group mods for tree display
        grouped_mods = self._group_mods_for_tree_display(mod_items)

        # Create widgets with tree structure
        for group_key, group_data in grouped_mods.items():
            if group_data["type"] == "parent_with_children":
                # Create parent mod widget
                parent_info = group_data["parent"]
                parent_widget = self._create_mod_widget(
                    group_key,
                    parent_info,
                    has_children=True,
                    is_expanded=group_data.get("expanded", False),
                )
                parent_widget.expand_requested.connect(self._on_mod_expand_requested)
                self.mods_layout.addWidget(parent_widget)

                # Create nested children (only if expanded)
                if group_data.get("expanded", False):
                    for child_path, child_info in group_data["children"].items():
                        child_widget = self._create_mod_widget(
                            child_path, child_info, is_nested=True
                        )
                        self.mods_layout.addWidget(child_widget)
            else:
                # Regular standalone mod
                mod_widget = self._create_mod_widget(group_key, group_data["info"])
                self.mods_layout.addWidget(mod_widget)

        # Update status
        total_mods_filtered = len(self.filtered_mods)
        enabled_mods_filtered = sum(
            1 for info in self.filtered_mods.values() if info["enabled"]
        )
        showing_start = start_idx + 1 if total_mods_filtered > 0 else 0
        showing_end = min(end_idx, total_mods_filtered)
        self.status_label.setText(
            tr(
                "showing_mods_status",
                start=showing_start,
                end=showing_end,
                total=total_mods_filtered,
                enabled=enabled_mods_filtered,
            )
        )

    def _group_mods_for_tree_display(self, mod_items):
        """Group mods to create expandable tree structure"""
        if not hasattr(self, "expanded_states"):
            self.expanded_states = {}  # Track expanded state per parent

        grouped = {}
        parent_packages = {}
        nested_mods = {}

        # First pass: identify parent packages and nested mods
        for mod_path, info in mod_items:
            if hasattr(self, "mod_infos") and mod_path in self.mod_infos:
                mod_info = self.mod_infos[mod_path]
                if mod_info.mod_type.value == "nested" and mod_info.parent_package:
                    # This is a nested mod
                    parent_name = mod_info.parent_package
                    if parent_name not in nested_mods:
                        nested_mods[parent_name] = []
                    # Use clean name without parent prefix
                    clean_info = info.copy()
                    clean_info["name"] = Path(mod_path).name  # Just the filename
                    nested_mods[parent_name].append((mod_path, clean_info))
                elif mod_info.mod_type.value == "package":
                    # This is a potential parent package
                    parent_packages[mod_info.name] = (mod_path, info)
                else:
                    # Regular standalone mod
                    grouped[mod_path] = {"type": "standalone", "info": info}
            else:
                # Fallback for when mod_infos is not available
                grouped[mod_path] = {"type": "standalone", "info": info}

        # Second pass: create grouped structure
        for parent_name, children_list in nested_mods.items():
            if parent_name in parent_packages:
                parent_path, parent_info = parent_packages[parent_name]
                grouped[parent_path] = {
                    "type": "parent_with_children",
                    "parent": parent_info,
                    "children": {
                        child_path: child_info
                        for child_path, child_info in children_list
                    },
                    "expanded": self.expanded_states.get(parent_path, False),
                }
                # Remove from standalone packages
                parent_packages.pop(parent_name, None)

        # Add remaining parent packages without nested children
        for parent_path, parent_info in parent_packages.values():
            if parent_path not in grouped:
                grouped[parent_path] = {"type": "standalone", "info": parent_info}

        return grouped

    def _create_mod_widget(
        self, mod_path, info, is_nested=False, has_children=False, is_expanded=False
    ):
        """Create a mod widget with tree styling"""
        is_enabled = info["enabled"]
        is_folder_mod = info.get("is_folder_mod", False)
        has_regulation = info.get("has_regulation", False)
        regulation_active = info.get("regulation_active", False)

        # Determine text color
        if is_nested:
            text_color = "#b0b0b0" if not is_enabled else "#90EE90"
        else:
            text_color = "#cccccc" if not is_enabled else "#90EE90"
            if regulation_active:
                text_color = "#FFD700"

        # Determine mod type and icon
        if hasattr(self, "mod_infos") and mod_path in self.mod_infos:
            mod_info = self.mod_infos[mod_path]
            if mod_info.mod_type.value == "nested":
                mod_type = tr("mod_type_nested_dll")
                type_icon = QIcon(resource_path("resources/icon/dll.svg"))
            elif regulation_active:
                mod_type = tr("mod_type_active_regulation")
                type_icon = QIcon(resource_path("resources/icon/regulation_active.svg"))
            elif has_regulation:
                mod_type = tr("mod_type_package_with_regulation")
                type_icon = QIcon(resource_path("resources/icon/folder.svg"))
            elif is_folder_mod:
                mod_type = tr("mod_type_package")
                type_icon = QIcon(resource_path("resources/icon/folder.svg"))
            else:
                mod_type = tr("mod_type_dll")
                type_icon = QIcon(resource_path("resources/icon/dll.svg"))
        else:
            # Fallback
            if regulation_active:
                mod_type = tr("mod_type_active_regulation")
                type_icon = QIcon(resource_path("resources/icon/regulation_active.svg"))
            elif has_regulation:
                mod_type = tr("mod_type_package_with_regulation")
                type_icon = QIcon(resource_path("resources/icon/folder.svg"))
            elif is_folder_mod:
                mod_type = tr("mod_type_package")
                type_icon = QIcon(resource_path("resources/icon/folder.svg"))
            else:
                mod_type = tr("mod_type_dll")
                type_icon = QIcon(resource_path("resources/icon/dll.svg"))

        # Check advanced options
        mod_info = self.mod_infos.get(mod_path) if hasattr(self, "mod_infos") else None
        has_advanced_options = (
            self.mod_manager.has_advanced_options(mod_info) if mod_info else False
        )

        # Create the widget
        mod_widget = ModItem(
            mod_path=mod_path,
            mod_name=info["name"],
            is_enabled=is_enabled,
            is_external=info["external"],
            is_folder_mod=is_folder_mod,
            is_regulation=has_regulation,
            mod_type=mod_type,
            type_icon=type_icon,
            item_bg_color="transparent",
            text_color=text_color,
            is_regulation_active=regulation_active,
            has_advanced_options=has_advanced_options,
            is_nested=is_nested,
            has_children=has_children,
            is_expanded=is_expanded,
        )

        # Connect signals
        mod_widget.toggled.connect(self.toggle_mod)
        if not is_nested:  # Nested mods cannot be deleted individually
            mod_widget.delete_requested.connect(self.delete_mod)
        mod_widget.edit_config_requested.connect(self.open_config_editor)
        mod_widget.open_folder_requested.connect(self.open_mod_folder)
        mod_widget.advanced_options_requested.connect(self.open_advanced_options)
        if has_regulation:
            mod_widget.regulation_activate_requested.connect(
                self.activate_regulation_mod
            )

        return mod_widget

    def _on_mod_expand_requested(self, mod_path: str, expanded: bool):
        """Handle mod expand/collapse request"""
        if not hasattr(self, "expanded_states"):
            self.expanded_states = {}

        self.expanded_states[mod_path] = expanded
        # Refresh the current page to show/hide nested mods
        self.update_pagination()

    def load_mods(self, reset_page: bool = True):
        """
        Reloads and displays mods using the new ModManager.
        """
        # 1. Pre-flight check: If the main mods directory is gone, show an empty state.
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        if not mods_dir or not mods_dir.is_dir():
            self.apply_filters(reset_page=True, source_mods={})
            self.update_profile_dropdown()
            self.status_label.setText(tr("mods_dir_not_found_warning"))
            return

        # 2. Get mods using the new ModManager
        self.mod_infos = self.mod_manager.get_all_mods(self.game_name)

        # 3. Convert ModInfo objects to the format expected by the UI
        final_mods = {}
        for mod_path, mod_info in self.mod_infos.items():
            final_mods[mod_path] = {
                "name": mod_info.name,
                "enabled": mod_info.status == ModStatus.ENABLED,
                "external": mod_info.is_external,
                "is_folder_mod": mod_info.mod_type == ModType.PACKAGE,
                "has_regulation": mod_info.has_regulation,
                "regulation_active": mod_info.regulation_active,
                "advanced_options": mod_info.advanced_options,
            }

        self.apply_filters(reset_page=reset_page, source_mods=final_mods)
        self.update_profile_dropdown()

    def activate_regulation_mod(self, mod_path: str):
        mod_name = Path(mod_path).name
        success, message = self.mod_manager.set_regulation_active(
            self.game_name, mod_name
        )

        if success:
            self.load_mods(reset_page=False)
            self.status_label.setText(message)
            QTimer.singleShot(
                3000, lambda: self.status_label.setText(tr("status_ready"))
            )
        else:
            QMessageBox.warning(self, tr("regulation_error_title"), message)

    def apply_filters(
        self, reset_page: bool = True, source_mods: Optional[Dict[str, Any]] = None
    ):
        """
        Filters the mod list based on search text and category.
        Can now accept a source_mods dictionary to bypass fetching from config_manager.
        """
        search_text = self.search_bar.text().lower()
        all_mods = (
            source_mods
            if source_mods is not None
            else self.config_manager.get_mods_info(self.game_name, skip_sync=True)
        )

        self.filtered_mods = {}

        for mod_path, info in all_mods.items():
            if search_text not in info["name"].lower():
                continue

            is_enabled = info["enabled"]
            is_folder_mod = info.get("is_folder_mod", False)
            has_regulation = info.get("has_regulation", False)

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

            if category_match:
                self.filtered_mods[mod_path] = info

        if reset_page:
            self.current_page = 1
        self.update_pagination()

    def toggle_mod(self, mod_path: str, enabled: bool):
        success, message = self.mod_manager.set_mod_enabled(
            self.game_name, mod_path, enabled
        )

        if success:
            self.load_mods(reset_page=False)
            self.status_label.setText(message)
            QTimer.singleShot(
                2000, lambda: self.status_label.setText(tr("status_ready"))
            )
        else:
            QMessageBox.warning(self, tr("toggle_mod_error_title"), message)

    def delete_mod(self, mod_path: str):
        mod_name = Path(mod_path).name
        reply = QMessageBox.question(
            self,
            tr("delete_mod_title"),
            tr("delete_mod_confirm_question", mod_name=mod_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.mod_manager.remove_mod(self.game_name, mod_path)

            if success:
                self.load_mods(reset_page=False)
                self.status_label.setText(message)
                QTimer.singleShot(
                    2000, lambda: self.status_label.setText(tr("status_ready"))
                )
            else:
                QMessageBox.warning(self, tr("delete_error_title"), message)

    def add_external_mod(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            tr("select_external_mod_title"),
            str(Path.home()),
            tr("dll_files_filter"),
        )
        if file_name:
            success, message = self.mod_manager.add_external_mod(
                self.game_name, file_name
            )

            if success:
                self.status_label.setText(message)
                self.load_mods(reset_page=False)
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )
            else:
                QMessageBox.warning(self, tr("add_external_mod_error_title"), message)

    def open_mod_folder(self, mod_path: str):
        folder_path = Path(mod_path).parent
        self._open_path(folder_path)

    def open_config_editor(self, mod_path: str):
        mod_name = Path(mod_path).stem
        initial_config_path = self.config_manager.get_mod_config_path(
            self.game_name, mod_path
        )

        dialog = ConfigEditorDialog(mod_name, initial_config_path, self)

        # dialog.exec() returns True if the dialog was "Accepted".
        # Our logic in the dialog calls self.accept() only when the path has changed.
        if dialog.exec():
            final_path = dialog.current_path

            # This check is technically redundant now because dialog.exec() would have been
            # false, but it's good defensive programming to keep it.
            if final_path and final_path != initial_config_path:
                self.config_manager.set_mod_config_path(
                    self.game_name, mod_path, str(final_path)
                )
                self.status_label.setText(
                    tr("config_path_saved_status", mod_name=mod_name)
                )
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )

    def open_advanced_options(self, mod_path: str):
        """Open the advanced options dialog for a mod"""
        try:
            mod_name = Path(mod_path).name
            mod_info = self.mod_infos.get(mod_path)
            if not mod_info:
                raise ValueError(tr("mod_info_not_found_error"))

            is_folder_mod = mod_info.mod_type == ModType.PACKAGE

            available_mod_names = [
                info.name
                for path, info in self.mod_infos.items()
                if (info.mod_type == mod_info.mod_type) and (path != mod_path)
            ]

            dialog = AdvancedModOptionsDialog(
                mod_path=mod_path,
                mod_name=mod_name,
                is_folder_mod=is_folder_mod,
                current_options=mod_info.advanced_options,
                available_mods=available_mod_names,
                parent=self,
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_options = dialog.get_options()

                # 1. Read the current, full configuration from disk
                profile_path = self.config_manager.get_profile_path(self.game_name)
                config_data = self.config_manager._parse_toml_config(profile_path)

                # 2. Find the specific mod entry in the config data
                target_entry = None
                if is_folder_mod:
                    packages = config_data.get("packages", [])
                    for pkg in packages:
                        if pkg.get("id") == mod_name:
                            target_entry = pkg
                            break
                else:  # Native DLL mod
                    mod_path_obj = Path(mod_path)
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    config_key = ""
                    try:
                        relative_path = mod_path_obj.relative_to(mods_dir)
                        mods_dir_name = self.config_manager.games[self.game_name][
                            "mods_dir"
                        ]
                        config_key = self.mod_manager._normalize_path(
                            f"{mods_dir_name}/{relative_path}"
                        )
                    except ValueError:  # External mod
                        config_key = self.mod_manager._normalize_path(
                            str(mod_path_obj.resolve())
                        )

                    natives = config_data.get("natives", [])
                    for native in natives:
                        if (
                            self.mod_manager._normalize_path(native.get("path", ""))
                            == config_key
                        ):
                            target_entry = native
                            break

                if target_entry is not None:
                    # 3. Purge all old advanced option keys from the entry
                    keys_to_purge = [
                        "load_before",
                        "load_after",
                        "optional",
                        "initializer",
                        "finalizer",
                    ]
                    for key in keys_to_purge:
                        if key in target_entry:
                            del target_entry[key]

                    # 4. Add the new options back, but ONLY if they are not the default value.
                    for key, value in new_options.items():
                        # Rule for 'optional': Only save if it's explicitly true.
                        if key == "optional" and value is True:
                            target_entry[key] = True

                        # Rule for dependency lists: Only save if the list is not empty.
                        elif key in ["load_before", "load_after"] and value:
                            target_entry[key] = value

                        # Rule for other text/dict settings: Only save if they have a value.
                        elif (
                            key not in ["optional", "load_before", "load_after"]
                            and value is not None
                        ):
                            target_entry[key] = value

                    # 5. Write the entire modified configuration back to disk
                    self.mod_manager._write_improved_config(
                        profile_path, config_data, self.game_name
                    )

                self.load_mods(reset_page=False)

                self.status_label.setText(
                    tr("advanced_options_updated_status", mod_name=mod_name)
                )
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )

        except Exception as e:
            QMessageBox.warning(
                self,
                tr("advanced_options_error_title"),
                tr("advanced_options_open_failed_msg", error=str(e)),
            )

    def open_game_options(self):
        """Open the game options dialog"""
        try:
            dialog = GameOptionsDialog(self.game_name, self.config_manager, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("game_options_error_title"),
                tr("game_options_open_failed_msg", error=str(e)),
            )

    def open_profile_settings(self):
        """Open the profile settings dialog"""
        try:
            dialog = ProfileSettingsDialog(self.game_name, self.config_manager, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.status_label.setText(
                    tr("profile_settings_saved_status", game_name=self.game_name)
                )
                self.load_mods(reset_page=False)
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("profile_settings_error_title"),
                tr("profile_settings_open_failed_msg", error=str(e)),
            )

    def open_mods_folder(self):
        mods_dir = self.config_manager.get_mods_dir(self.game_name)
        if not mods_dir.exists():
            QMessageBox.warning(
                self,
                tr("folder_not_found_title"),
                tr("mods_dir_not_exist_msg", mods_dir=mods_dir),
            )
            return
        self._open_path(mods_dir)

    def set_custom_exe_path(self):
        QMessageBox.warning(
            self,
            "Non-Recommended Action",
            "It is recommended to avoid setting a custom game executable path unless ME3 cannot detect your game installation automatically.\n\nOnly use this option if your game is installed in a non-standard location.",
        )
        current_path = self.config_manager.get_game_exe_path(self.game_name)
        if current_path:
            reply = QMessageBox.question(
                self,
                "Custom Executable Path",
                f"Current custom executable path:\n{current_path}\n\nDo you want to change it?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Reset,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            if reply == QMessageBox.StandardButton.Reset:
                self.config_manager.set_game_exe_path(self.game_name, None)
                self.status_label.setText(
                    f"Cleared custom executable path for {self.game_name}"
                )
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )
                return

        expected_exe_name = self.config_manager.get_game_executable_name(self.game_name)
        if not expected_exe_name:
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Expected executable name for '{self.game_name}' is not defined.",
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
                msg.setWindowTitle("Incorrect Executable Selected")
                msg.setTextFormat(Qt.TextFormat.RichText)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText(
                    f"<h3>Executable Mismatch</h3><p>The selected file does not match the required executable for <b>{self.game_name}</b>.</p><b>Expected:</b> {expected_exe_name}<br><b>Selected:</b> {selected_path.name}<br><p>Please choose the correct file named <b>{expected_exe_name}</b>.</p>"
                )
                msg.exec()
                return
            try:
                self.config_manager.set_game_exe_path(self.game_name, file_name)
                self.status_label.setText(
                    f"Set custom executable path for {self.game_name}"
                )
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText(tr("status_ready"))
                )
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Set Path Error",
                    f"Failed to set custom executable path: {str(e)}",
                )

    def run_me3_with_custom_exe(
        self, exe_path: str, cli_id: str, profile_path: str, terminal
    ):
        args = [
            "launch",
            "--exe",
            exe_path,
            "--skip-steam-init",
            "--game",
            cli_id,
            "-p",
            profile_path,
        ]
        # Display the command nicely in terminal
        display_command = f"me3 launch --exe {shlex.quote(exe_path)} --skip-steam-init --game {cli_id} -p {shlex.quote(profile_path)}"
        terminal.output.append(f"$ {display_command}")
        if terminal.process is not None:
            terminal.process.kill()
            terminal.process.waitForFinished(1000)
        terminal.process = QProcess(terminal)
        terminal.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        terminal.process.readyReadStandardOutput.connect(terminal.handle_stdout)
        terminal.process.finished.connect(terminal.process_finished)
        terminal.process.start("me3", args)

    def launch_game(self):
        """Launch the game with the configured profile and settings."""
        try:
            # Check if ME3 is installed before attempting to launch
            if self.window().me3_version == tr("not_installed"):
                reply = QMessageBox.question(
                    self,
                    tr("me3_not_installed_title"),
                    tr("me3_required_for_launch_msg"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    # Open the installation dialog
                    from ui.main_window import HelpAboutDialog

                    dialog = HelpAboutDialog(self.window(), initial_setup=True)
                    dialog.exec()
                    # After dialog closes, check if ME3 was installed
                    self.window().refresh_me3_status()
                    if self.window().me3_version == tr("not_installed"):
                        return  # Still not installed, abort launch
                else:
                    return  # User chose not to install, abort launch

            # Validate profile and CLI ID
            profile_path = self.config_manager.get_profile_path(self.game_name)
            if not profile_path.exists():
                QMessageBox.warning(
                    self,
                    tr("launch_error_title"),
                    tr("profile_not_found_msg", path=profile_path),
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

            main_window = self.window()
            custom_exe_path = self.config_manager.get_game_exe_path(self.game_name)

            # Handle custom executable launch
            if custom_exe_path:
                if hasattr(main_window, "terminal"):
                    self.run_me3_with_custom_exe(
                        custom_exe_path,
                        cli_id,
                        str(profile_path),
                        main_window.terminal,
                    )
                    self._update_status(
                        tr(
                            "launching_with_custom_exe_status",
                            game_name=self.game_name,
                        )
                    )
                    return
                else:
                    QMessageBox.information(
                        self,
                        tr("launch_error_title"),
                        tr("custom_exe_requires_terminal_info"),
                    )

            # Prepare base command
            command_args = ["me3", "launch", "--game", cli_id, "-p", str(profile_path)]

            # Execute command based on platform and terminal availability
            if hasattr(main_window, "terminal"):
                self._launch_in_terminal(command_args, main_window.terminal)
            else:
                self._launch_direct(command_args)

            self._update_status(tr("launching_game_status", game_name=self.game_name))

        except Exception as e:
            QMessageBox.warning(
                self,
                tr("launch_error_title"),
                tr("launch_game_failed_msg", error=str(e)),
            )

    def _launch_in_terminal(self, command_args, terminal):
        """Launch the game command in the terminal."""
        # Display the command nicely in terminal
        display_command = " ".join(shlex.quote(arg) for arg in command_args)
        terminal.output.append(f"$ {display_command}")

        if terminal.process is not None:
            terminal.process.kill()
            terminal.process.waitForFinished(1000)

        terminal.process = QProcess(terminal)
        terminal.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        terminal.process.readyReadStandardOutput.connect(terminal.handle_stdout)
        terminal.process.finished.connect(terminal.process_finished)

        # Use argument list for terminal execution (skip display since we already showed it)
        terminal.run_command(command_args, skip_display=True)

    def _launch_direct(self, command_args):
        """Launch the game command directly via subprocess."""
        import os

        if sys.platform != "win32":
            # Check if we're running in Flatpak
            is_flatpak = os.path.exists("/.flatpak-info") or "/app/" in os.environ.get(
                "PATH", ""
            )

            if is_flatpak and command_args[0] == "me3":
                # Use flatpak-spawn for me3 commands
                user_home = os.path.expanduser("~")
                me3_path = f"{user_home}/.local/bin/me3"
                flatpak_args = ["flatpak-spawn", "--host", me3_path] + command_args[1:]
                subprocess.Popen(flatpak_args)
            else:
                # Regular Linux execution with shell environment
                user_shell = os.environ.get("SHELL", "/bin/bash")
                if not Path(user_shell).exists():
                    user_shell = "/bin/bash"

                # Create shell-safe command string
                try:
                    me3_command_str = shlex.join(command_args)
                except AttributeError:
                    me3_command_str = " ".join(shlex.quote(arg) for arg in command_args)

                final_command_list = [user_shell, "-l", "-c", me3_command_str]
                subprocess.Popen(final_command_list)
        else:
            # Windows: use command args directly
            subprocess.Popen(command_args)

    def _update_status(self, message):
        """Update status label with automatic reset."""
        self.status_label.setText(message)
        QTimer.singleShot(3000, lambda: self.status_label.setText(tr("status_ready")))

    def open_profile_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("manage_profiles_title", game_name=self.game_name))
        dialog.setModal(True)
        dialog.resize(600, 400)
        # dialog.setStyleSheet("QDialog { background-color: #2d2d2d; }")

        layout = QHBoxLayout(dialog)
        layout.setSpacing(15)

        left_layout = QVBoxLayout()
        search_bar = QLineEdit()
        search_bar.setPlaceholderText(tr("search_profiles_placeholder"))
        search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #252525; border: 1px solid #3d3d3d; border-radius: 6px;
                padding: 8px; font-size: 13px; color: #ffffff;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        left_layout.addWidget(search_bar)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #252525; border: 1px solid #3d3d3d; border-radius: 6px;
                font-size: 14px; outline: 0;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #333333; }
            QListWidget::item:selected { background-color: #0078d4; color: white; border-bottom: 1px solid #005a9e; }
            QListWidget::item:hover { background-color: #3d3d3d; }
        """)
        left_layout.addWidget(list_widget)
        layout.addLayout(left_layout, 2)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        button_style = """
            QPushButton {
                background-color: #3d3d3d; color: white; border: none; border-radius: 6px;
                padding: 10px; text-align: left; font-size: 13px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QPushButton:disabled { background-color: #252525; color: #666; }
        """

        activate_btn = QPushButton(
            QIcon(resource_path("resources/icon/activate.svg")), tr("activate_button")
        )
        add_btn = QPushButton(
            QIcon(resource_path("resources/icon/add.svg")), tr("add_new_button")
        )
        rename_btn = QPushButton(
            QIcon(resource_path("resources/icon/edit.svg")), tr("rename_button")
        )
        delete_btn = QPushButton(
            QIcon(resource_path("resources/icon/delete.svg")), tr("delete_button")
        )

        for btn in [activate_btn, add_btn, rename_btn, delete_btn]:
            btn.setStyleSheet(button_style)
            btn.setIconSize(QSize(20, 20))

        button_layout.addWidget(activate_btn)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(rename_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout, 1)

        def refresh_list():
            list_widget.clear()
            search_text = search_bar.text().lower()
            active_id = self.config_manager.active_profiles.get(self.game_name)
            profiles = self.config_manager.get_profiles_for_game(self.game_name)

            for profile in profiles:
                if search_text not in profile["name"].lower():
                    continue
                item = QListWidgetItem()
                item.setText(profile["name"])
                item.setData(Qt.ItemDataRole.UserRole, profile["id"])
                if profile["id"] == active_id:
                    item.setIcon(QIcon(resource_path("resources/icon/active.png")))
                list_widget.addItem(item)
            update_button_states()

        def update_button_states():
            selected_item = list_widget.currentItem()
            has_selection = selected_item is not None
            activate_btn.setEnabled(has_selection)
            rename_btn.setEnabled(has_selection)
            delete_btn.setEnabled(has_selection)
            if has_selection:
                profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
                is_active = profile_id == self.config_manager.active_profiles.get(
                    self.game_name
                )
                is_default = profile_id == "default"
                activate_btn.setEnabled(not is_active)
                rename_btn.setEnabled(not is_default)
                delete_btn.setEnabled(not is_default)

        def on_activate():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.config_manager.set_active_profile(self.game_name, profile_id)
            refresh_list()
            self.load_mods()

        def on_add():
            name, ok = QInputDialog.getText(
                dialog, tr("new_profile_name_title"), tr("new_profile_name_desc")
            )
            if ok and name.strip():
                # Get the default profiles directory from an existing profile path
                default_profiles_dir = (
                    Path(self.config_manager.get_profile_path(self.game_name))
                    .expanduser()
                    .parent
                )
                default_profiles_dir.mkdir(parents=True, exist_ok=True)

                # Updated hint text to match actual behavior
                profile_dir = QFileDialog.getExistingDirectory(
                    dialog,
                    tr("select_folder_for_profile_title"),
                    str(default_profiles_dir),
                )

                if profile_dir:
                    # Ensure .me3 file is created outside its mods folder
                    profile_path = Path(profile_dir)
                    if profile_path == default_profiles_dir:
                        mods_dir = default_profiles_dir / f"{name.strip()}-mods"
                        mods_dir.mkdir(exist_ok=True)
                        self.config_manager.add_profile(
                            self.game_name, name.strip(), str(mods_dir)
                        )
                    else:
                        # Fallback: keep current behavior if user selects another folder
                        self.config_manager.add_profile(
                            self.game_name, name.strip(), profile_dir
                        )

                    refresh_list()

        def on_rename():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            profile = next(
                p
                for p in self.config_manager.get_profiles_for_game(self.game_name)
                if p["id"] == selected_item.data(Qt.ItemDataRole.UserRole)
            )
            new_name, ok = QInputDialog.getText(
                dialog,
                tr("rename_profile_title"),
                tr("enter_new_name_desc"),
                text=profile["name"],
            )
            if ok and new_name.strip():
                self.config_manager.update_profile(
                    self.game_name, profile["id"], new_name.strip()
                )
                refresh_list()
                self.update_profile_dropdown()

        def on_delete():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            reply = QMessageBox.question(
                dialog,
                tr("confirm_delete_title"),
                tr(
                    "delete_profile_confirm_question",
                    profile_name=selected_item.text(),
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
                self.config_manager.delete_profile(self.game_name, profile_id)
                refresh_list()
                self.load_mods()

        search_bar.textChanged.connect(refresh_list)
        list_widget.currentItemChanged.connect(update_button_states)
        activate_btn.clicked.connect(on_activate)
        add_btn.clicked.connect(on_add)
        rename_btn.clicked.connect(on_rename)
        delete_btn.clicked.connect(on_delete)

        refresh_list()
        dialog.exec()
        self.update_profile_dropdown()
