import zipfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QProgressDialog, QWidget

from me3_manager.core.mod_manager import ImprovedModManager
from me3_manager.core.nexus_metadata import NexusMetadataManager
from me3_manager.services.export_service import ExportService
from me3_manager.services.nexus_service import (
    NexusError,
    NexusMod,
    NexusModFile,
    NexusService,
)
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


class NexusDownloadWorker(QThread):
    progress_signal = Signal(object, object)  # current, total
    status_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, nexus_service, url, download_path, extract_dir):
        super().__init__()
        self.nexus_service = nexus_service
        self.url = url
        self.download_path = download_path
        self.extract_dir = extract_dir
        self.success = False
        self.error_message = ""

    def run(self):
        try:
            self.status_signal.emit(tr("nexus_downloading_status"))

            def on_progress(current, total):
                self.progress_signal.emit(current, total or 0)

            self.nexus_service.download_to_file(
                self.url,
                self.download_path,
                on_progress=on_progress,
                check_cancel=lambda: self.isInterruptionRequested(),
            )

            if self.isInterruptionRequested():
                return

            self.status_signal.emit(tr("nexus_installing_status"))

            # Unzip
            if self.download_path.suffix.lower() != ".zip":
                raise NexusError("Only .zip downloads are supported right now.")

            self.extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(self.download_path, "r") as z:
                z.extractall(self.extract_dir)

            self.success = True
            self.finished_signal.emit(True, "")

        except Exception as e:
            self.success = False
            self.error_message = str(e)
            self.finished_signal.emit(False, str(e))


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
        self.search_mode: str = "local"  # local | nexus
        self.selected_local_mod_path: str | None = None
        self._nexus_target_mod_name: str | None = None
        self._nexus_last_query: str | None = None
        self._nexus_last_results = []
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

        # Nexus integration
        self.nexus_service = NexusService(self.config_manager.get_nexus_api_key())
        self._thumb_cache: dict[str, QPixmap] = {}
        self.nexus_metadata = NexusMetadataManager(
            self.config_manager.config_root,
            self.game_name,
            legacy_roots=[
                self.config_manager.config_root,
                self.config_manager.get_mods_dir(self.game_name),
            ],
        )
        try:
            self.nexus_metadata.ensure_dirs()
        except Exception:
            pass

        self.builder.init_ui()
        self._setup_file_watcher()
        self.load_mods()

    @staticmethod
    def _safe_disconnect(signal) -> None:
        """Disconnect all slots from a Qt signal without raising warnings/errors."""
        try:
            # Check if signal has any receivers before disconnecting
            # This avoids RuntimeWarning when no slots are connected
            if signal.receivers(signal) > 0:
                signal.disconnect()
        except (TypeError, RuntimeError):
            # TypeError: receivers() may not be available on all signal types
            # RuntimeError: signal may already be disconnected
            try:
                signal.disconnect()
            except Exception:
                pass
        except Exception:
            pass

    def _setup_sidebar_signals(self, sidebar) -> None:
        """Setup standard signal connections for the Nexus details sidebar."""
        self._safe_disconnect(sidebar.install_clicked)
        self._safe_disconnect(sidebar.link_clicked)
        self._safe_disconnect(sidebar.open_page_clicked)
        self._safe_disconnect(sidebar.check_update_clicked)
        self._safe_disconnect(sidebar.close_clicked)

        sidebar.link_clicked.connect(self.link_selected_nexus_mod)
        sidebar.open_page_clicked.connect(self.open_selected_nexus_page)
        sidebar.check_update_clicked.connect(self.check_update_selected_mod)
        sidebar.install_clicked.connect(self.download_selected_nexus_mod)
        sidebar.close_clicked.connect(lambda: sidebar.hide_animated())

    # Search mode handlers (Local/Nexus)
    def on_search_mode_changed(self):
        try:
            combo = getattr(self, "search_mode_combo", None)
            if combo is None:
                return
            data = combo.currentData()
            self.search_mode = str(data) if data else "local"
        except Exception:
            self.search_mode = "local"

        # UX: clear previous results when switching modes (actual panels added later)
        if self.search_mode == "local":
            self.apply_filters(reset_page=True)

    def on_search_text_changed(self):
        # In local mode, keep existing live filtering.
        if self.search_mode == "local":
            self.apply_filters(reset_page=True)
        else:
            # Hide any open dropdown when editing query
            try:
                menu = getattr(self, "nexus_search_menu", None)
                if menu:
                    menu.hide()
            except Exception:
                pass

    def on_search_return_pressed(self):
        # In nexus mode, we'll use Enter to trigger an API lookup.
        if self.search_mode == "nexus":
            # Implemented in later steps (nexus_search_panel)
            try:
                self.perform_nexus_search()
            except Exception:
                pass

    def perform_nexus_search(self):
        query = (self.search_bar.text() or "").strip()
        self._nexus_last_query = query
        # Ensure API key is up-to-date (settings can change while page is open)
        self.nexus_service.set_api_key(self.config_manager.get_nexus_api_key())

        if not self.nexus_service.has_api_key:
            self._update_status(tr("nexus_api_key_missing_status"))
            self._show_nexus_dropdown(error_text=tr("nexus_api_key_missing_status"))
            return

        game_domain = None
        try:
            game_domain = self.config_manager.get_game_nexus_domain(self.game_name)
        except Exception:
            game_domain = None

        try:
            domain, mod_id = self.nexus_service.parse_mod_query(
                query, fallback_game_domain=game_domain
            )
            # Prefer cached mod details to avoid API calls.
            cached = self.nexus_metadata.get_cached_for_mod(domain, mod_id)
            if cached and cached.mod_name:
                mod = NexusMod(
                    game_domain=domain,
                    mod_id=int(mod_id),
                    name=cached.mod_name,
                    summary=cached.mod_summary,
                    author=cached.mod_author,
                    version=cached.mod_version,
                    picture_url=cached.mod_picture_url,
                    endorsement_count=cached.mod_endorsements,
                    unique_downloads=cached.mod_unique_downloads,
                    total_downloads=cached.mod_total_downloads,
                )
                mods = [mod]
            else:
                mod = self.nexus_service.get_mod(domain, mod_id)
                mods = [mod]
        except NexusError as e:
            self._update_status(str(e))
            self._show_nexus_dropdown(error_text=str(e))
            return
        except Exception as e:
            self._update_status(tr("nexus_search_failed", error=str(e)))
            self._show_nexus_dropdown(
                error_text=tr("nexus_search_failed", error=str(e))
            )
            return

        self._nexus_last_results = mods
        self._show_nexus_dropdown(results=mods)
        self._update_status(tr("nexus_results_loaded_status", count=len(mods)))

    def _show_nexus_dropdown(self, *, results=None, error_text: str | None = None):
        """Show a dropdown under the search bar like the desired UX screenshot."""
        try:
            menu = getattr(self, "nexus_search_menu", None)
            if menu is None:
                menu = QMenu(self)
                menu.setStyleSheet(
                    """
                    QMenu {
                        background-color: #2a2a2a;
                        color: #ffffff;
                        border: 1px solid #3d3d3d;
                        border-radius: 10px;
                        padding: 6px;
                    }
                    QMenu::item {
                        padding: 8px 10px;
                        border-radius: 8px;
                        margin: 2px 4px;
                    }
                    QMenu::item:selected {
                        background-color: #0078d4;
                    }
                    QMenu::separator {
                        height: 1px;
                        background: #3d3d3d;
                        margin: 6px 10px;
                    }
                    """
                )
                self.nexus_search_menu = menu

            menu.clear()

            # Section header
            header = QAction(tr("nexus_search_results_section"), self)
            header.setEnabled(False)
            menu.addAction(header)

            if error_text:
                err = QAction(error_text, self)
                err.setEnabled(False)
                menu.addAction(err)
            else:
                mods = results or []
                if not mods:
                    empty = QAction(tr("nexus_results_empty"), self)
                    empty.setEnabled(False)
                    menu.addAction(empty)
                else:
                    for m in mods:
                        text = tr(
                            "nexus_dropdown_item",
                            mod_name=m.name or str(m.mod_id),
                            author=m.author or "-",
                        )
                        act = QAction(text, self)
                        # Best-effort thumbnail icon (usually 1 result, OK to fetch sync)
                        try:
                            if m.picture_url:
                                pix = self._load_thumbnail_pixmap(m.picture_url)
                                if pix and not pix.isNull():
                                    act.setIcon(
                                        QIcon(
                                            pix.scaled(
                                                18,
                                                18,
                                                Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation,
                                            )
                                        )
                                    )
                        except Exception:
                            pass

                        def _mk(mod):
                            return lambda: self._select_nexus_mod_from_dropdown(mod)

                        act.triggered.connect(_mk(m))
                        menu.addAction(act)

            # Show under the search box
            anchor = getattr(self, "search_bar", None)
            if anchor:
                pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
                menu.popup(pos)
        except Exception:
            return

    def _select_nexus_mod_from_dropdown(self, mod):
        # Keep the text in the search box (user pasted url/id), but show details
        try:
            # Build a lightweight object compatible with existing handler
            class _R:
                def __init__(self, m):
                    self.mod = m

            self.on_nexus_result_selected(_R(mod))
        except Exception:
            return

    def on_nexus_result_selected(self, result):
        try:
            mod = result.mod
            self._nexus_target_mod_name = mod.name or f"nexus_mod_{mod.mod_id}"
            sidebar = getattr(self, "nexus_details_sidebar", None)
            if sidebar:
                sidebar.show_animated()
                sidebar.set_details(mod, None)
                sidebar.set_status(tr("nexus_loading_details"))
                sidebar.set_cached_text(tr("nexus_cached_just_now"))
                sidebar.set_nexus_url(
                    f"https://www.nexusmods.com/{mod.game_domain}/mods/{mod.mod_id}"
                )
                sidebar.set_link_mode(linked=True)
                # Load saved folder path if any
                saved_root = self.nexus_metadata.get_mod_root_path(
                    mod.game_domain, mod.mod_id
                )
                sidebar.set_mod_root_path(saved_root)
                # Populate thumbnail (we already can fetch it, dropdown proves it's accessible)
                try:
                    if mod.picture_url:
                        pix = self._load_thumbnail_pixmap(mod.picture_url)
                        sidebar.set_thumbnail(pix)
                except Exception:
                    pass
                # Setup sidebar signal connections
                self._setup_sidebar_signals(sidebar)

            # Prefer cached file details (offline + fewer requests).
            # Update: Auto-fetch file details if not cached to show file size immediately.
            cached = self.nexus_metadata.get_cached_for_mod(mod.game_domain, mod.mod_id)
            latest: NexusModFile | None = None

            if cached and cached.file_id:
                latest = NexusModFile(
                    file_id=int(cached.file_id),
                    name=cached.file_name,
                    version=cached.file_version,
                    size_kb=cached.file_size_kb,
                    category_name=cached.file_category,
                    category_id=None,
                    is_primary=None,
                    uploaded_timestamp=cached.file_uploaded_timestamp,
                )
                if sidebar:
                    sidebar.set_details(mod, latest)
                    sidebar.set_status("")
                    sidebar.set_cached_text(self._fmt_cached_age(cached.cached_at))
            else:
                # Not cached? Fetch file list to get size/version info.
                if sidebar:
                    sidebar.set_status(tr("nexus_loading_details"))

                try:
                    if self.nexus_service.has_api_key:
                        files = self.nexus_service.get_mod_files(
                            mod.game_domain, mod.mod_id
                        )
                        latest = self.nexus_service.pick_latest_main_file(files)

                        if latest:
                            if sidebar:
                                sidebar.set_details(mod, latest)
                                sidebar.set_status(tr("nexus_details_fetched_status"))
                                sidebar.set_cached_text(tr("nexus_cached_just_now"))

                            # Cache it so next time it's instant
                            self.nexus_metadata.upsert_cache_for_mod(
                                game_domain=mod.game_domain,
                                mod_id=mod.mod_id,
                                mod_name=mod.name,
                                mod_version=mod.version,
                                mod_author=mod.author,
                                mod_endorsements=mod.endorsement_count,
                                mod_unique_downloads=mod.unique_downloads,
                                mod_total_downloads=mod.total_downloads,
                                mod_picture_url=mod.picture_url,
                                mod_summary=mod.summary,
                                file_id=latest.file_id,
                                file_name=latest.name,
                                file_version=latest.version,
                                file_size_kb=latest.size_kb,
                                file_category=latest.category_name,
                                file_uploaded_timestamp=latest.uploaded_timestamp,
                                nexus_url=f"https://www.nexusmods.com/{mod.game_domain}/mods/{mod.mod_id}",
                            )
                        else:
                            # No files found
                            if sidebar:
                                sidebar.set_details(mod, None)
                                sidebar.set_status(tr("nexus_no_files_found_status"))
                    else:
                        # No API key, can only show mod info
                        if sidebar:
                            sidebar.set_details(mod, None)
                            sidebar.set_status(tr("nexus_api_key_missing_status"))

                except Exception as e:
                    # Fallback to just mod details if fetch fails
                    if sidebar:
                        sidebar.set_details(mod, None)
                        sidebar.set_status(
                            tr("nexus_details_fetch_failed", error=str(e))
                        )

            self._update_status(
                tr("nexus_selected_mod_status", mod_name=mod.name or str(mod.mod_id))
            )

        except Exception:
            pass

    def on_nexus_download_requested(self, result):
        try:
            # Selecting also wires up download
            self.on_nexus_result_selected(result)
            self.download_selected_nexus_mod()
        except Exception:
            pass

    def download_selected_nexus_mod(self):
        """Download and install the currently selected Nexus mod (zip only)."""
        sidebar = getattr(self, "nexus_details_sidebar", None)
        mod = sidebar.current_mod() if sidebar else None
        file = sidebar.current_file() if sidebar else None
        if not mod:
            return

        if not self.nexus_service.has_api_key:
            self._update_status(tr("nexus_api_key_missing_status"))
            if sidebar:
                sidebar.set_status(tr("nexus_api_key_missing_status"))
            return

        try:
            files = self.nexus_service.get_mod_files(mod.game_domain, mod.mod_id)
            chosen = file or self.nexus_service.pick_latest_main_file(files)
            if not chosen:
                raise NexusError("No downloadable files found for this mod.")

            links = self.nexus_service.get_download_links(
                mod.game_domain, mod.mod_id, chosen.file_id
            )
            if not links:
                raise NexusError("No download link returned by Nexus.")
            url = links[0].url

            with TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                dl_path = tmp_dir / f"{mod.mod_id}-{chosen.file_id}.zip"
                extract_dir = tmp_dir / "extract"

                # Setup Progress Dialog
                progress = QProgressDialog(
                    tr("nexus_downloading_status"),
                    tr("cancel_button"),
                    0,
                    100,
                    self,
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setAutoClose(False)
                progress.setAutoReset(False)
                progress.setMinimumDuration(0)

                # Setup Worker
                worker = NexusDownloadWorker(
                    self.nexus_service, url, dl_path, extract_dir
                )

                dl_label = mod.name or chosen.name or tr("nexus_downloading_status")

                def on_download_progress(current, total):
                    if total > 0:
                        progress.setMaximum(100)
                        pct = int((current / total) * 100)
                        progress.setValue(pct)
                        progress.setLabelText(f"{dl_label} ({pct}%)")
                    else:
                        progress.setMaximum(0)

                def on_status(text):
                    progress.setLabelText(text)
                    if text == tr("nexus_installing_status"):
                        progress.setRange(0, 0)  # indeterminate for extraction

                def on_finished(success, msg):
                    progress.close()

                worker.progress_signal.connect(on_download_progress)
                worker.status_signal.connect(on_status)
                worker.finished_signal.connect(on_finished)
                progress.canceled.connect(worker.requestInterruption)

                worker.start()
                progress.exec()
                worker.wait()

                if not worker.success:
                    if worker.error_message:
                        raise NexusError(worker.error_message)
                    else:
                        if sidebar:
                            sidebar.set_status(tr("nexus_install_cancelled_status"))
                        return

                if sidebar:
                    sidebar.set_status(tr("nexus_installing_status"))

                # Use Nexus mod name as folder name
                mod_name_hint = (
                    mod.name or chosen.name or f"nexus_{mod.mod_id}_{chosen.file_id}"
                ).strip()

                mod_root_path = sidebar.get_mod_root_path() if sidebar else None

                # Save the folder rule for future updates if specified
                if mod_root_path:
                    self.nexus_metadata.set_mod_root_path(
                        game_domain=mod.game_domain,
                        mod_id=mod.mod_id,
                        mod_root_path=mod_root_path,
                    )

                # Install using unified API
                installed = self.mod_installer.install_mod(
                    extract_dir,
                    mod_name_hint=mod_name_hint,
                    mod_root_path=mod_root_path,
                )

                if installed:
                    # Track metadata for update checking
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    installed_name = (
                        installed[0]
                        if isinstance(installed[0], str)
                        else installed[0].name
                    )
                    folder_path = mods_dir / installed_name

                    import logging

                    log = logging.getLogger(__name__)
                    log.debug(
                        "Metadata tracking: installed_name=%s, folder_path=%s",
                        installed_name,
                        folder_path,
                    )

                    # Find the local path for metadata
                    # Use rglob to find DLLs at any depth (e.g., mod/mod.dll)
                    if folder_path.exists() and folder_path.is_dir():
                        dlls_inside = list(folder_path.rglob("*.dll"))
                        log.debug("Found DLLs: %s", dlls_inside)
                        if dlls_inside:
                            local_path = str(dlls_inside[0].resolve())
                        else:
                            local_path = str(folder_path.resolve())
                    else:
                        local_path = str(folder_path.resolve())
                        log.debug("Folder doesn't exist: %s", folder_path)

                    log.debug("Saving metadata with local_path=%s", local_path)
                    self.nexus_metadata.update_after_download(
                        game_domain=mod.game_domain,
                        local_mod_path=local_path,
                        mod_id=mod.mod_id,
                        file_id=chosen.file_id,
                        mod_name=mod.name,
                        mod_version=mod.version,
                        mod_author=mod.author,
                        mod_endorsements=mod.endorsement_count,
                        mod_unique_downloads=mod.unique_downloads,
                        mod_total_downloads=mod.total_downloads,
                        mod_picture_url=mod.picture_url,
                        mod_summary=mod.summary,
                        file_name=chosen.name,
                        file_version=chosen.version,
                        file_size_kb=chosen.size_kb,
                        file_category=chosen.category_name,
                        file_uploaded_timestamp=chosen.uploaded_timestamp,
                        nexus_url=f"https://www.nexusmods.com/{mod.game_domain}/mods/{mod.mod_id}",
                    )
                    log.debug("Metadata saved successfully")
                    self._update_status(tr("nexus_install_success_status"))
                    if sidebar:
                        sidebar.set_status(tr("nexus_install_success_status"))
                else:
                    if sidebar:
                        sidebar.set_status(tr("nexus_install_cancelled_status"))
        except Exception as e:
            self._update_status(tr("nexus_download_failed_status", error=str(e)))
            if sidebar:
                sidebar.set_status(tr("nexus_download_failed_status", error=str(e)))

    def open_selected_nexus_page(self):
        sidebar = getattr(self, "nexus_details_sidebar", None)
        url = sidebar.current_url() if sidebar else None
        if not url:
            return
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            return

    def check_update_selected_mod(self):
        """
        Check if an update exists for the currently selected local-linked mod.
        For Nexus-only selection, this just refreshes file info.
        """
        sidebar = getattr(self, "nexus_details_sidebar", None)
        if not sidebar:
            return
        mod = sidebar.current_mod()
        if not mod:
            return

        self.nexus_service.set_api_key(self.config_manager.get_nexus_api_key())
        if not self.nexus_service.has_api_key:
            sidebar.set_status(tr("nexus_api_key_missing_status"))
            return

        try:
            # Determine tracked file for local mods (if any)
            tracked = None
            if self.selected_local_mod_path:
                tracked = self.nexus_metadata.find_for_local_mod(
                    self.selected_local_mod_path
                )

            files = self.nexus_service.get_mod_files(mod.game_domain, mod.mod_id)
            latest = self.nexus_service.pick_latest_main_file(files)
            sidebar.set_details(mod, latest)
            sidebar.set_cached_text(tr("nexus_cached_just_now"))
            # Cache refreshed details for offline viewing
            if latest:
                self.nexus_metadata.upsert_cache_for_mod(
                    game_domain=mod.game_domain,
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    mod_version=mod.version,
                    mod_author=mod.author,
                    mod_endorsements=mod.endorsement_count,
                    mod_unique_downloads=mod.unique_downloads,
                    mod_total_downloads=mod.total_downloads,
                    mod_picture_url=mod.picture_url,
                    mod_summary=mod.summary,
                    file_id=latest.file_id,
                    file_name=latest.name,
                    file_version=latest.version,
                    file_size_kb=latest.size_kb,
                    file_category=latest.category_name,
                    file_uploaded_timestamp=latest.uploaded_timestamp,
                    nexus_url=sidebar.current_url(),
                )

            if (
                tracked
                and latest
                and tracked.file_id
                and latest.file_id != tracked.file_id
            ):
                sidebar.set_status(tr("nexus_update_available_status"))
            else:
                sidebar.set_status(tr("nexus_up_to_date_status"))
        except Exception as e:
            sidebar.set_status(tr("nexus_update_check_failed_status", error=str(e)))

    def link_selected_nexus_mod(self):
        """
        Link a LOCAL mod (selected from the mod list) to a Nexus mod URL/ID
        so we can download updates into the same mod folder later.
        """
        local_path = self.selected_local_mod_path
        if not local_path:
            QMessageBox.information(
                self, tr("settings_title"), tr("nexus_link_select_local_first")
            )
            return

        # Ask user for Nexus URL or ID
        text, ok = QInputDialog.getText(
            self,
            tr("nexus_link_title"),
            tr("nexus_link_prompt"),
            text="",
        )
        if not ok:
            return
        query = (text or "").strip()
        if not query:
            return

        # Ensure API key is current; linking itself doesn't require key, but fetching details does.
        self.nexus_service.set_api_key(self.config_manager.get_nexus_api_key())

        fallback_domain = None
        try:
            fallback_domain = self.config_manager.get_game_nexus_domain(self.game_name)
        except Exception:
            fallback_domain = None

        try:
            domain, mod_id = self.nexus_service.parse_mod_query(
                query, fallback_game_domain=fallback_domain
            )
            self.nexus_metadata.link_local_mod(
                game_domain=domain,
                local_mod_path=local_path,
                mod_id=mod_id,
                nexus_url=query,
            )
            # Populate sidebar immediately if possible
            if self.nexus_service.has_api_key:
                mod = self.nexus_service.get_mod(domain, mod_id)
                files = self.nexus_service.get_mod_files(domain, mod_id)
                latest = self.nexus_service.pick_latest_main_file(files)
                # Ensure stored metadata includes the real Nexus display name
                try:
                    self.nexus_metadata.link_local_mod(
                        game_domain=domain,
                        local_mod_path=local_path,
                        mod_id=mod_id,
                        nexus_url=query,
                        mod_name=mod.name,
                    )
                except Exception:
                    pass
                self._nexus_target_mod_name = Path(local_path).name
                sidebar = getattr(self, "nexus_details_sidebar", None)
                if sidebar:
                    sidebar.show_animated()
                    sidebar.set_details(mod, latest)
                    sidebar.set_status(tr("nexus_linked_status"))
            self._update_status(tr("nexus_linked_status"))
        except Exception as e:
            QMessageBox.warning(
                self, tr("ERROR"), tr("nexus_link_failed_status", error=str(e))
            )

    def on_local_mod_selected(self, mod_path: str):
        """Show sidebar for a local mod only if linked to Nexus."""
        try:
            self.selected_local_mod_path = str(Path(mod_path).resolve())
            self._nexus_target_mod_name = Path(self.selected_local_mod_path).name
        except Exception:
            self.selected_local_mod_path = mod_path
            self._nexus_target_mod_name = Path(mod_path).name if mod_path else None

        sidebar = getattr(self, "nexus_details_sidebar", None)
        if not sidebar:
            return

        # Check if mod is linked to Nexus BEFORE showing sidebar
        try:
            linked = self.nexus_metadata.find_for_local_mod(
                self.selected_local_mod_path
            )
        except Exception:
            linked = None

        # If not linked, close the sidebar and return
        if not linked:
            if sidebar.isVisible():
                sidebar.hide_animated()
            return

        # Setup signal connections
        self._setup_sidebar_signals(sidebar)

        # Build offline mod/file from cached metadata
        try:
            cached_mod = NexusMod(
                game_domain=linked.game_domain,
                mod_id=int(linked.mod_id),
                name=linked.mod_name,
                summary=linked.mod_summary,
                author=linked.mod_author,
                version=linked.mod_version,
                picture_url=linked.mod_picture_url,
                endorsement_count=linked.mod_endorsements,
                unique_downloads=linked.mod_unique_downloads,
                total_downloads=linked.mod_total_downloads,
            )
            cached_file = (
                NexusModFile(
                    file_id=int(linked.file_id),
                    name=linked.file_name,
                    version=linked.file_version,
                    size_kb=linked.file_size_kb,
                    category_name=linked.file_category,
                    category_id=None,
                    is_primary=None,
                    uploaded_timestamp=linked.file_uploaded_timestamp,
                )
                if linked.file_id
                else None
            )
            sidebar.set_details(cached_mod, cached_file)
            sidebar.set_status(tr("nexus_linked_status"))
            sidebar.set_cached_text(self._fmt_cached_age(linked.cached_at))
            sidebar.set_nexus_url(
                linked.nexus_url
                or f"https://www.nexusmods.com/{linked.game_domain}/mods/{linked.mod_id}"
            )
            sidebar.set_link_mode(linked=True)

            # Load thumbnail before showing sidebar
            try:
                if cached_mod.picture_url:
                    pix = self._load_thumbnail_pixmap(cached_mod.picture_url)
                    sidebar.set_thumbnail(pix)
            except Exception:
                pass

            # Show with animation
            sidebar.show_animated()
        except Exception:
            # Keep sidebar hidden if anything fails
            return

    @staticmethod
    def _fmt_cached_age(iso: str | None) -> str:
        if not iso:
            return tr("nexus_cached_unknown")
        try:
            dt = datetime.fromisoformat(iso)
            now = datetime.now(UTC)
            seconds = max(0, int((now - dt).total_seconds()))
            if seconds < 60:
                return tr("nexus_cached_secs_ago", seconds=seconds)
            minutes = seconds // 60
            if minutes < 60:
                return tr("nexus_cached_mins_ago", minutes=minutes)
            hours = minutes // 60
            return tr("nexus_cached_hours_ago", hours=hours)
        except Exception:
            return tr("nexus_cached_unknown")

    def _load_thumbnail_pixmap(self, url: str) -> QPixmap | None:
        """Best-effort thumbnail loader for Nexus cards (small images only)."""
        try:
            url = (url or "").strip()
            if not url:
                return None
            cached = self._thumb_cache.get(url)
            if cached and not cached.isNull():
                return cached
            import requests

            resp = requests.get(url, timeout=4)
            resp.raise_for_status()
            pix = QPixmap()
            if pix.loadFromData(resp.content):
                self._thumb_cache[url] = pix
                return pix
        except Exception:
            return None
        return None

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
        # Metadata folder should live under the ACTIVE profile's mods directory
        try:
            self.nexus_metadata = NexusMetadataManager(
                self.config_manager.config_root,
                self.game_name,
                legacy_roots=[
                    self.config_manager.config_root,
                    self.config_manager.get_mods_dir(self.game_name),
                ],
            )
            self.nexus_metadata.ensure_dirs()
        except Exception:
            pass
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

    def install_mod(self, source: Path, **kwargs) -> list[str]:
        """Universal mod installation entry point."""
        return self.mod_installer.install_mod(source, **kwargs)

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
