"""
Drag and Drop Event Handler for GamePage.

Simplified handler that delegates all mod installation to ModInstaller.install_mod().
"""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QInputDialog

from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class DragDropHandler:
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

    def _is_game_asset_item(self, path: Path) -> bool:
        """Check if path is a game asset folder or regulation.bin file."""
        if path.is_dir() and path.name in ACCEPTABLE_FOLDERS:
            return True
        if path.is_file() and path.name.lower() in (
            "regulation.bin",
            "regulation.bin.disabled",
        ):
            return True
        return False

    def _install_loose_game_assets(self, asset_paths: list[Path]) -> bool:
        """
        Bundle loose game asset folders/files into a mod and install.

        Args:
            asset_paths: List of game asset folders (action, event, etc.) or regulation.bin

        Returns:
            True if installation succeeded
        """
        # Build list of items for display
        item_names = [p.name for p in asset_paths]

        # Ask user for mod name
        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("name_loose_assets_title"),
            tr("name_loose_assets_desc", items=", ".join(item_names)),
        )

        if not ok or not mod_name.strip():
            return False

        mod_name = mod_name.strip()

        # Create a temporary folder with the mod name and copy all assets into it
        with TemporaryDirectory() as tmp:
            staged_mod = Path(tmp) / mod_name
            staged_mod.mkdir(parents=True, exist_ok=True)

            for asset in asset_paths:
                dest = staged_mod / asset.name
                if asset.is_dir():
                    shutil.copytree(
                        asset, dest, symlinks=False, ignore_dangling_symlinks=True
                    )
                else:
                    shutil.copy2(asset, dest, follow_symlinks=False)

            # Install the staged mod folder
            result = self.game_page.mod_installer.install_mod(
                staged_mod, mod_name_hint=mod_name
            )
            return bool(result)

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

        installed_any = False

        # Check if ALL dropped items are game asset folders or regulation.bin
        # This handles the case where user drags multiple loose game folders
        game_assets = [p for p in dropped_paths if self._is_game_asset_item(p)]

        if game_assets and len(game_assets) == len(dropped_paths):
            # All dropped items are game assets - bundle them together
            if self._install_loose_game_assets(game_assets):
                installed_any = True
        else:
            # Regular installation flow for non-asset drops
            for path in dropped_paths:
                if path.suffix.lower() == ".me3":
                    # .me3 file dropped - install from parent folder using this profile
                    result = self.game_page.mod_installer.install_mod(path.parent)
                    if result:
                        installed_any = True
                elif path.suffix.lower() == ".zip":
                    # Archive dropped - extract and install
                    result = self.game_page.mod_installer.install_mod(path)
                    if result:
                        installed_any = True
                elif path.is_dir():
                    # Check if it's a single game asset folder (e.g., just "action" folder)
                    if self._is_game_asset_item(path):
                        # Single game asset folder - prompt for mod name
                        if self._install_loose_game_assets([path]):
                            installed_any = True
                    else:
                        # Regular folder dropped - install directly
                        result = self.game_page.mod_installer.install_mod(path)
                        if result:
                            installed_any = True
                elif path.is_file() and path.suffix.lower() == ".dll":
                    # Single DLL dropped - install directly
                    result = self.game_page.mod_installer.install_mod(path.parent)
                    if result:
                        installed_any = True
                elif path.is_file() and path.name.lower() in (
                    "regulation.bin",
                    "regulation.bin.disabled",
                ):
                    # Single regulation.bin dropped - prompt for mod name
                    if self._install_loose_game_assets([path]):
                        installed_any = True

        if installed_any:
            self.game_page.load_mods(reset_page=False)
            QTimer.singleShot(
                3000, lambda: self.game_page.status_label.setText(tr("status_ready"))
            )
