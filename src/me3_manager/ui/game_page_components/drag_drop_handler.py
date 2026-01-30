"""
Drag and Drop Event Handler for GamePage.

Simplified handler that delegates all mod installation to ModInstaller.install_mod().
"""

import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QInputDialog

from me3_manager.utils.archive_utils import ARCHIVE_EXTENSIONS
from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
from me3_manager.utils.nexus_filename_parser import parse_nexus_filename
from me3_manager.utils.translator import tr

log = logging.getLogger(__name__)

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
        if path.is_dir() and path.name.lower() in ACCEPTABLE_FOLDERS:
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
                elif path.suffix.lower() in ARCHIVE_EXTENSIONS:
                    # Archive dropped - parse filename for Nexus metadata
                    nexus_info = parse_nexus_filename(path.name)
                    mod_name_hint = nexus_info.mod_name if nexus_info else None

                    # Extract and install
                    result = self.game_page.mod_installer.install_mod(
                        path, mod_name_hint=mod_name_hint
                    )
                    if result:
                        installed_any = True
                        # Try to save Nexus metadata if we parsed the filename
                        if nexus_info:
                            self._save_nexus_metadata_for_installed(
                                result, nexus_info, path.name
                            )
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

    def _save_nexus_metadata_for_installed(
        self,
        installed_result: list,
        nexus_info,
        archive_filename: str,
    ) -> None:
        """
        Save Nexus metadata after installing a mod from a Nexus archive.

        This is called when user drags a Nexus archive into the manager.
        We parse the filename to get mod_id/version/timestamp, then optionally
        fetch additional details from the Nexus API if an API key is configured.
        """
        try:
            gp = self.game_page

            # Get game's Nexus domain (e.g., "eldenringnightreign")
            game_domain = gp.config_manager.get_game_nexus_domain(gp.game_name)
            if not game_domain:
                return

            # Get the installed mod folder path
            if not installed_result:
                return
            mods_dir = gp.config_manager.get_mods_dir(gp.game_name)
            installed_name = (
                installed_result[0]
                if isinstance(installed_result[0], str)
                else installed_result[0].name
            )
            folder_path = mods_dir / installed_name
            if not folder_path.exists():
                return

            local_path = gp._determine_metadata_local_path(folder_path)
            log.info(
                "Saving Nexus metadata for %s (mod_id=%d)",
                local_path,
                nexus_info.mod_id,
            )

            # Start with parsed filename info, fetch more from API if available
            mod_name = nexus_info.mod_name
            file_name = archive_filename
            mod_author = mod_endorsements = mod_unique_downloads = None
            mod_total_downloads = mod_picture_url = mod_summary = None
            file_id = file_size_kb = file_category = None

            # Fetch mod details from Nexus API (if API key is set)
            if gp.nexus_service.has_api_key:
                try:
                    mod = gp.nexus_service.get_mod(game_domain, nexus_info.mod_id)
                    if mod:
                        mod_name = mod.name or nexus_info.mod_name
                        mod_author = mod.author
                        mod_endorsements = mod.endorsement_count
                        mod_unique_downloads = mod.unique_downloads
                        mod_total_downloads = mod.total_downloads
                        mod_picture_url = mod.picture_url
                        mod_summary = mod.summary
                except Exception as e:
                    log.debug("API fetch mod failed: %s", e)

                # Match file by timestamp to get file_id/size/name
                try:
                    for f in gp.nexus_service.get_mod_files(
                        game_domain, nexus_info.mod_id
                    ):
                        if f.uploaded_timestamp == nexus_info.uploaded_timestamp:
                            file_id = f.file_id
                            file_size_kb = f.size_kb
                            file_category = f.category_name
                            if f.name:
                                file_name = f.name  # Use cleaner API name
                            break
                except Exception as e:
                    log.debug("API fetch files failed: %s", e)

            # Save to metadata cache
            gp.nexus_metadata.upsert_cache_for_mod(
                game_domain=game_domain,
                mod_id=nexus_info.mod_id,
                local_mod_path=local_path,
                mod_name=mod_name,
                mod_version=nexus_info.version or None,
                mod_author=mod_author,
                mod_endorsements=mod_endorsements,
                mod_unique_downloads=mod_unique_downloads,
                mod_total_downloads=mod_total_downloads,
                mod_picture_url=mod_picture_url,
                mod_summary=mod_summary,
                file_id=file_id,
                file_name=file_name,
                file_version=nexus_info.version or None,
                file_size_kb=file_size_kb,
                file_category=file_category,
                file_uploaded_timestamp=nexus_info.uploaded_timestamp,
                nexus_url=f"https://www.nexusmods.com/{game_domain}/mods/{nexus_info.mod_id}",
            )
            log.info("Nexus metadata saved for mod_id=%d", nexus_info.mod_id)

        except Exception as e:
            log.warning("Failed to save Nexus metadata: %s", e)
