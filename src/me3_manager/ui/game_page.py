from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QWidget

from me3_manager.core.mod_manager import ImprovedModManager
from me3_manager.services.export_service import ExportService
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
from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
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
        self.mod_widgets: dict[str, QWidget] = {}
        self.current_filter: str = "all"
        self.filter_buttons: dict[str, QWidget] = {}
        self.mods_per_page: int = self.config_manager.get_mods_per_page()
        self.current_page: int = 1
        self.total_pages: int = 1
        self.filtered_mods: dict[str, Any] = {}
        self.all_mods_data: dict[str, Any] = {}
        self.mod_infos: dict[str, Any] = {}
        self.acceptable_folders = ACCEPTABLE_FOLDERS
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
        # Update banner after mods load to reflect current active profile settings
        try:
            self.update_custom_savefile_warning()
        except Exception:
            pass

    def apply_filters(
        self, reset_page: bool = True, source_mods: dict[str, Any] | None = None
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

    def add_external_package_mod(self):
        self.mod_action_handler.add_external_package_mod()

    def activate_regulation_mod(self, mod_path: str):
        self.mod_action_handler.activate_regulation_mod(mod_path)

    # Delegated Installation Actions

    def install_linked_mods(self, items_to_install: list[Path]) -> bool:
        return self.mod_installer.install_linked_mods(items_to_install)

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        self.mod_installer.handle_profile_import(import_folder, profile_file)

    def install_root_mod_package(self, root_path: Path):
        self.mod_installer.install_root_mod_package(root_path)

    def install_loose_items(self, items_to_install: list[Path]):
        self.mod_installer.install_loose_items(items_to_install)

    def install_mods_folder_root(self, root_dir: Path):
        self.mod_installer.install_mods_folder_root(root_dir)

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

    def is_valid_drop(self, paths: list[Path]) -> bool:
        return self.utils.is_valid_drop(paths)

    def export_mods_setup(self):
        """Export current game's referenced mods and profile to a zip."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        default_name = f"{self.game_name}_mods_setup.zip"
        target_path, _ = QFileDialog.getSaveFileName(
            self, tr("export_dialog_title"), default_name, "Zip (*.zip)"
        )
        if not target_path:
            return

        ok, err = ExportService.export_profile_and_mods(
            game_name=self.game_name,
            config_manager=self.config_manager,
            destination_zip=Path(target_path),
        )
        if ok:
            QMessageBox.information(
                self, tr("export_done_title"), tr("export_done_msg")
            )
        else:
            QMessageBox.warning(self, tr("ERROR"), tr("export_failed_msg", error=err))

    # Core Page Logic & Helpers

    def _setup_file_watcher(self):
        """Setup file system monitoring for automatic reloading."""
        self.reload_timer = QTimer(self)
        self.reload_timer.setSingleShot(True)
        self.reload_timer.timeout.connect(lambda: self.load_mods(reset_page=False))

    def update_custom_savefile_warning(self):
        """Show banner if active profile does not have a custom savefile set."""
        banner = getattr(self, "custom_savefile_banner", None)
        if banner is None:
            return
        try:
            profile_path = self.config_manager.get_profile_path(self.game_name)
        except Exception:
            banner.setVisible(False)
            return
        try:
            if not profile_path or not profile_path.exists():
                banner.setVisible(False)
                return
            config = self.config_manager._parse_toml_config(profile_path)
        except Exception:
            banner.setVisible(False)
            return

        # Check both legacy (v1) and v2 style locations for savefile
        savefile_value = config.get("savefile")
        if not savefile_value:
            game_section = config.get("game")
            if isinstance(game_section, dict):
                savefile_value = game_section.get("savefile")

        # If Seamless Co-op is enabled (ersc.dll or nrsc.dll), do not show the banner
        try:
            mods_data = getattr(self, "all_mods_data", {}) or {}
            seamless_enabled = False
            for mod_path, info in mods_data.items():
                if not info.get("enabled", False):
                    continue
                path_lower = str(mod_path).lower()
                name_lower = str(info.get("name", "")).lower()
                if path_lower.endswith(("/ersc.dll", "\\ersc.dll")):
                    seamless_enabled = True
                    break
                if path_lower.endswith(("/nrsc.dll", "\\nrsc.dll")):
                    seamless_enabled = True
                    break
                # Also check by stem/name for safety (e.g., external path missing extension in name)
                if name_lower.endswith(("/ersc", "/nrsc")) or name_lower in (
                    "ersc",
                    "nrsc",
                ):
                    seamless_enabled = True
                    break
        except Exception:
            seamless_enabled = False

        # Show banner only when no custom savefile AND seamless co-op not enabled
        banner.setVisible((not bool(savefile_value)) and (not seamless_enabled))

    def _get_filter_definitions(self) -> dict[str, tuple]:
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
