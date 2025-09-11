from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QWidget

from me3_manager.core.mod_manager import ImprovedModManager
from me3_manager.ui.game_page_components.dialog_handler import DialogHandler
from me3_manager.ui.game_page_components.drag_drop_handler import DragDropHandler
from me3_manager.ui.game_page_components.game_launcher import GameLauncher
from me3_manager.ui.game_page_components.mod_action_handler import ModActionHandler
from me3_manager.ui.game_page_components.mod_installer import ModInstaller
from me3_manager.ui.game_page_components.mod_list_handler import ModListHandler
from me3_manager.ui.game_page_components.page_utils import PageUtils
from me3_manager.ui.game_page_components.pagination_handler import PaginationHandler
from me3_manager.ui.game_page_components.profile_handler import ProfileHandler
from me3_manager.ui.game_page_components.style import GamePageStyle
from me3_manager.ui.game_page_components.ui_builder import UiBuilder
from me3_manager.utils.translator import tr


class GamePage(QWidget):
    """
    Widget for managing mods for a specific game.
    Acts as a central controller, delegating tasks to specialized handlers.
    """

    def __init__(self, game_name: str, config_manager):
        super().__init__()

        self.game_name = game_name
        self.style = GamePageStyle()
        self.config_manager = config_manager
        self.mod_manager = ImprovedModManager(config_manager)
        self.mod_widgets: Dict[str, QWidget] = {}
        self.current_filter: str = "all"
        self.filter_buttons: Dict[str, QWidget] = {}
        self.mods_per_page: int = self.config_manager.get_mods_per_page()
        self.current_page: int = 1
        self.total_pages: int = 1
        self.filtered_mods: Dict[str, Any] = {}
        self.all_mods_data: Dict[str, Any] = {}
        self.mod_infos: Dict[str, Any] = {}
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

        self.builder = UiBuilder(self)
        self.drag_drop_handler = DragDropHandler(self)
        self.mod_installer = ModInstaller(self)
        self.pagination_handler = PaginationHandler(self)
        self.mod_action_handler = ModActionHandler(self)
        self.game_launcher = GameLauncher(self)
        self.profile_handler = ProfileHandler(self)
        self.dialog_handler = DialogHandler(self)
        self.utils = PageUtils(self)
        self.mod_list_handler = ModListHandler(self)

        self.builder.init_ui()
        self._setup_file_watcher()
        self.load_mods()

    # Delegated Drag & Drop Events
    def dragEnterEvent(self, event: QDragEnterEvent):
        self.drag_drop_handler.dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.drag_drop_handler.dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.drag_drop_handler.dropEvent(event)

    # Delegated Mod List & Filtering Actions

    def set_filter(self, filter_name: str):
        self.mod_list_handler.set_filter(filter_name)

    def load_mods(self, reset_page: bool = True):
        self.mod_list_handler.load_mods(reset_page)

    def apply_filters(
        self, reset_page: bool = True, source_mods: Optional[Dict[str, Any]] = None
    ):
        self.mod_list_handler.apply_filters(reset_page, source_mods)

    def update_filter_button_styles(self):
        self.mod_list_handler.update_filter_button_styles()

    def _group_mods_for_tree_display(self, mod_items):
        return self.mod_list_handler._group_mods_for_tree_display(mod_items)

    def _create_mod_widget(
        self, mod_path, info, is_nested=False, has_children=False, is_expanded=False
    ):
        return self.mod_list_handler._create_mod_widget(
            mod_path, info, is_nested, has_children, is_expanded
        )

    def _on_mod_expand_requested(self, mod_path: str, expanded: bool):
        self.mod_list_handler._on_mod_expand_requested(mod_path, expanded)

    # Delegated Pagination Actions

    def change_items_per_page(self, value: int):
        self.pagination_handler.change_items_per_page(value)

    def prev_page(self):
        self.pagination_handler.prev_page()

    def next_page(self):
        self.pagination_handler.next_page()

    def update_pagination(self):
        self.pagination_handler.update_pagination()

    # Delegated Mod Actions (Toggle, Delete, etc.)

    def toggle_mod(self, mod_path: str, enabled: bool):
        self.mod_action_handler.toggle_mod(mod_path, enabled)

    def delete_mod(self, mod_path: str):
        self.mod_action_handler.delete_mod(mod_path)

    def add_external_mod(self):
        self.mod_action_handler.add_external_mod()

    def activate_regulation_mod(self, mod_path: str):
        self.mod_action_handler.activate_regulation_mod(mod_path)

    # Delegated Installation Actions

    def install_linked_mods(self, items_to_install: List[Path]) -> bool:
        return self.mod_installer.install_linked_mods(items_to_install)

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        self.mod_installer.handle_profile_import(import_folder, profile_file)

    def install_root_mod_package(self, root_path: Path):
        self.mod_installer.install_root_mod_package(root_path)

    def install_loose_items(self, items_to_install: List[Path]):
        self.mod_installer.install_loose_items(items_to_install)

    # Delegated Profile Actions

    def update_profile_dropdown(self):
        self.profile_handler.update_profile_dropdown()

    def on_profile_selected_from_menu(self):
        self.profile_handler.on_profile_selected_from_menu()

    def open_profile_manager(self):
        self.profile_handler.open_profile_manager()

    # Delegated Dialog Openers

    def open_profile_editor(self):
        self.dialog_handler.open_profile_editor()

    def open_config_editor(self, mod_path: str):
        self.dialog_handler.open_config_editor(mod_path)

    def open_advanced_options(self, mod_path: str):
        self.dialog_handler.open_advanced_options(mod_path)

    def open_game_options(self):
        self.dialog_handler.open_game_options()

    def open_profile_settings(self):
        self.dialog_handler.open_profile_settings()

    # Delegated Utility & System Actions

    def launch_game(self):
        self.game_launcher.launch_game()

    def open_mods_folder(self):
        self.utils.open_mods_folder()

    def open_mod_folder(self, mod_path: str):
        self.utils.open_mod_folder(mod_path)

    def is_valid_drop(self, paths: List[Path]) -> bool:
        return self.utils.is_valid_drop(paths)

    # Core Page Logic & Helpers

    def _setup_file_watcher(self):
        """Setup file system monitoring for automatic reloading."""
        self.reload_timer = QTimer(self)
        self.reload_timer.setSingleShot(True)
        self.reload_timer.timeout.connect(lambda: self.load_mods(reset_page=False))

    def _get_filter_definitions(self) -> Dict[str, tuple]:
        """Provides filter button text and tooltips to the UI builder."""
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

    def _is_valid_mod_folder(self, folder: Path) -> bool:
        """
        Checks if a folder contains valid mod contents.
        Used by handlers before installation.
        """
        if folder.name in self.acceptable_folders:
            return True
        if any(
            sub.is_dir() and sub.name in self.acceptable_folders
            for sub in folder.iterdir()
        ):
            return True
        if (folder / "regulation.bin").exists() or (
            folder / "regulation.bin.disabled"
        ).exists():
            return True
        return False

    def _update_status(self, message: str):
        """Updates the status label with a message that fades after a delay."""
        self.status_label.setText(message)
        QTimer.singleShot(3000, lambda: self.status_label.setText(tr("status_ready")))
