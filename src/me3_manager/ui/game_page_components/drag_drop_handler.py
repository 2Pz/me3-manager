"""
Drag and Drop Event Handler for GamePage.

This module is responsible for processing Qt's dragEnter, dragLeave, and dropEvents,
validating dropped content, and initiating the mod installation process.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QMessageBox

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class DragDropHandler:
    # Use a string literal 'GamePage' for the type hint.
    # This avoids needing the import at runtime.
    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle the drag enter event, accepting it if valid files are dragged."""
        if event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
            if self.game_page.is_valid_drop(paths):
                event.acceptProposedAction()
                self.game_page.drop_zone.setStyleSheet(
                    """
                    QLabel {
                        background-color: #0078d4; border: 2px dashed #ffffff;
                        border-radius: 12px; padding: 20px; font-size: 14px;
                        color: #ffffff; margin: 8px 0px;
                    }
                """
                )

    def dragLeaveEvent(self, event):
        """Reset the drop zone style when the drag leaves the widget."""
        self.game_page.drop_zone.setStyleSheet(
            """
            QLabel {
                background-color: #1e1e1e; border: 2px dashed #3d3d3d;
                border-radius: 12px; padding: 20px; font-size: 14px;
                color: #888888; margin: 8px 0px;
            }
        """
        )

    def dropEvent(self, event: QDropEvent):
        """Handle the drop event to process and install dropped files."""
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
                    self.game_page,
                    tr("import_error"),
                    tr("import_one_profile_warning"),
                )
                return
            profile_to_import = me3_files[0]
            import_folder = profile_to_import.parent
            self.game_page.handle_profile_import(import_folder, profile_to_import)
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

        # First pass: identify and collect all linked items (DLLs and config folders)
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
            if self.game_page.install_linked_mods(list(linked_items_to_install)):
                installed_something = True

        # Handle the remaining loose items, which may be a mod package.
        if items_for_bundling:
            # A single directory that is not a config folder. Treat as a mod package.
            if len(items_for_bundling) == 1 and items_for_bundling[0].is_dir():
                self.game_page.install_root_mod_package(items_for_bundling[0])
            else:
                # Multiple files/folders, or a single file. Bundle them.
                self.game_page.install_loose_items(items_for_bundling)
            installed_something = True

        if installed_something:
            self.game_page.load_mods(reset_page=False)
            QTimer.singleShot(
                3000, lambda: self.game_page.status_label.setText(tr("status_ready"))
            )
