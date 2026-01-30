from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QSizePolicy,
    QWidget,
)

from me3_manager.core.mod_manager import ImprovedModManager
from me3_manager.core.nexus_metadata import NexusMetadataManager
from me3_manager.services.community_service import CommunityService
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
from me3_manager.utils.archive_utils import ARCHIVE_EXTENSIONS
from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.translator import tr


class NexusDownloadWorker(QThread):
    progress_signal = Signal(object, object)  # current, total
    status_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, nexus_service, url, download_path):
        super().__init__()
        self.nexus_service = nexus_service
        self.url = url
        self.download_path = download_path
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

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        self.community_service = CommunityService()
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
        self.on_search_mode_changed()  # Ensure correct initial state

    @staticmethod
    def _safe_disconnect(signal) -> None:
        """Disconnect all slots from a Qt signal without raising warnings/errors."""
        try:
            # Directly disconnect all slots from the signal
            # In PySide6, disconnect() with no args disconnects all slots
            signal.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            # AttributeError: signal may already be None or not have disconnect()
            # RuntimeError: signal may already be disconnected or has no slots
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
        self._safe_disconnect(sidebar.mod_root_changed)

        sidebar.link_clicked.connect(self.link_selected_nexus_mod)
        sidebar.open_page_clicked.connect(self.open_selected_nexus_page)
        sidebar.check_update_clicked.connect(self.check_update_selected_mod)
        sidebar.install_clicked.connect(self.download_selected_nexus_mod)
        sidebar.file_selected.connect(self.on_sidebar_file_selected)
        sidebar.mod_root_changed.connect(self.on_sidebar_mod_root_changed)
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
            if hasattr(self, "mods_scroll_area"):
                self.mods_scroll_area.setVisible(True)
            else:
                self.mods_widget.setVisible(True)

            if hasattr(self, "pagination_widget"):
                self.pagination_widget.setVisible(True)
            if hasattr(self, "community_search_panel"):
                self.community_search_panel.setVisible(False)
            self.apply_filters(reset_page=True)

        elif self.search_mode == "community":
            if hasattr(self, "mods_scroll_area"):
                self.mods_scroll_area.setVisible(False)
            else:
                self.mods_widget.setVisible(False)

            if hasattr(self, "pagination_widget"):
                self.pagination_widget.setVisible(False)
            if hasattr(self, "community_search_panel"):
                self.community_search_panel.setVisible(True)
            self.perform_community_search()
        else:
            # Nexus mode (overlay dropdown), show local mods in background?
            # Or hide everything?
            # Existing behavior was likely just showing local mods + dropdown.
            # Let's keep local mods visible for Nexus mode.
            if hasattr(self, "mods_scroll_area"):
                self.mods_scroll_area.setVisible(True)
            else:
                self.mods_widget.setVisible(True)

            if hasattr(self, "pagination_widget"):
                self.pagination_widget.setVisible(True)
            if hasattr(self, "community_search_panel"):
                self.community_search_panel.setVisible(False)

    def on_search_text_changed(self):
        # In local mode, keep existing live filtering.
        if self.search_mode == "local":
            self.apply_filters(reset_page=True)
        elif self.search_mode == "community":
            self.perform_community_search()
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
        elif self.search_mode == "community":
            self.perform_community_search()

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

        mods = []
        try:
            # First, try to parse as mod ID or URL
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
        except NexusError:
            # Not a valid ID or URL - try searching by name using GraphQL v2
            if game_domain:
                try:
                    mods = self.nexus_service.search_mods_by_name(game_domain, query)
                    if not mods:
                        self._update_status(tr("nexus_results_empty"))
                        self._show_nexus_dropdown(error_text=tr("nexus_results_empty"))
                        return
                except Exception as e:
                    self._update_status(tr("nexus_search_failed", error=str(e)))
                    self._show_nexus_dropdown(
                        error_text=tr("nexus_search_failed", error=str(e))
                    )
                    return
            else:
                self._update_status(tr("nexus_game_not_supported"))
                self._show_nexus_dropdown(error_text=tr("nexus_game_not_supported"))
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

    def perform_community_search(self):
        """Fetch all community profiles and filter locally."""
        panel = getattr(self, "community_search_panel", None)
        if not panel:
            return

        panel.set_status(tr("community_searching_status"))

        try:
            # fetch_profiles handles caching, so this is fast if already fetched
            profiles = self.community_service.fetch_profiles(self.game_name)

            query = (self.search_bar.text() or "").strip().lower()
            if query:
                filtered = [
                    p
                    for p in profiles
                    if query in p.name.lower() or query in p.description.lower()
                ]
            else:
                filtered = profiles

            panel.set_results(filtered)

        except Exception as e:
            panel.set_status(tr("community_search_failed", error=str(e)))

    def on_community_install_requested(self, profile):
        """Handle install request from community panel."""
        try:
            with TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                dl_path = tmp_dir / profile.filename

                # Show indeterminate progress
                progress = QProgressDialog(
                    tr("community_downloading_status", profile=profile.name),
                    tr("cancel_button"),
                    0,
                    0,  # Indeterminate
                    self,
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)

                # We can't cancel the requests.get easily without thread,
                # but let's just do blocking download for MVP as per existing patterns
                # or better, use a simple loop.
                # Actually CommunityService.download_profile uses stream, so we can support cancel/progress later.
                # For now blocking download with spinner.

                progress.show()
                # Force UI update
                from PySide6.QtWidgets import QApplication

                QApplication.processEvents()

                result_path = self.community_service.download_profile(profile, dl_path)
                progress.close()

                if result_path and result_path.exists():
                    self.handle_downloaded_profile(result_path)

        except Exception as e:
            QMessageBox.critical(self, tr("error"), str(e))

    def handle_downloaded_profile(self, path: Path):
        """Invoke the mod installer to handle the downloaded profile."""
        if not path.exists():
            return

        # We use the parent folder (temp dir) as the base context.
        # This works fine for profiles that rely on Nexus links.
        # For profiles relying on local files, those files won't be present,
        # but _handle_profile_import should gracefully handle or warn about missing local files
        # (or just skip them and install what it can).

        # We access the internal method _handle_profile_import because it isn't exposed publicly yet
        # but it is the correct reuse of logic.
        self.mod_installer._handle_profile_import(path.parent, path)

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
                        # Note: Thumbnails removed from dropdown for faster display
                        # Images are shown in the details sidebar after selection

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

                # Fetch available files to populate the dropdown
                # We do this asynchronously/lazily normally, but for the detail view needed for selection, we fetch now.
                files = []
                try:
                    if self.nexus_service.has_api_key:
                        files = self.nexus_service.get_mod_files(
                            mod.game_domain, mod.mod_id
                        )
                except Exception:
                    pass

                # Determine which file should be selected by default
                selected_file_id = None

                # 1. Prefer currently installed/tracked file
                cached_meta = self.nexus_metadata.get_cached_for_mod(
                    mod.game_domain, mod.mod_id
                )
                if cached_meta and cached_meta.file_id:
                    selected_file_id = int(cached_meta.file_id)

                # 2. If not installed, pick latest main file
                if selected_file_id is None and files:
                    latest = self.nexus_service.pick_latest_main_file(files)
                    if latest:
                        selected_file_id = latest.file_id

                # Populate the sidebar dropdown
                sidebar.populate_files(files, selected_file_id)

                # Populate thumbnail
                try:
                    if mod.picture_url:
                        pix = self._load_thumbnail_pixmap(mod.picture_url)
                        sidebar.set_thumbnail(pix)
                except Exception:
                    pass
                # Setup sidebar signal connections
                self._setup_sidebar_signals(sidebar)

            # Update displayed details based on the Selected File (or Mod if no file)
            # Find the file object for the selected ID
            target_file = None
            if files and selected_file_id:
                for f in files:
                    if f.file_id == selected_file_id:
                        target_file = f
                        break

            # Fallback to cached file object if we couldn't fetch list but have cache
            if (
                not target_file
                and cached_meta
                and cached_meta.file_id == selected_file_id
            ):
                target_file = NexusModFile(
                    file_id=int(cached_meta.file_id),
                    name=cached_meta.file_name,
                    version=cached_meta.file_version,
                    size_kb=cached_meta.file_size_kb,
                    category_name=cached_meta.file_category,
                    category_id=None,
                    is_primary=None,
                    uploaded_timestamp=cached_meta.file_uploaded_timestamp,
                )

            if target_file:
                sidebar.set_details(mod, target_file)
                if cached_meta and cached_meta.file_id == selected_file_id:
                    sidebar.set_status("")
                    sidebar.set_cached_text(self._fmt_cached_age(cached_meta.cached_at))
                else:
                    sidebar.set_status(tr("nexus_details_fetched_status"))
                    sidebar.set_cached_text(tr("nexus_cached_just_now"))

            # Save cache if we fetched fresh data
            if target_file and self.nexus_service.has_api_key:
                self.nexus_metadata.upsert_cache_for_mod(
                    game_domain=mod.game_domain,
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    mod_version=target_file.version,
                    mod_author=mod.author,
                    mod_endorsements=mod.endorsement_count,
                    mod_unique_downloads=mod.unique_downloads,
                    mod_total_downloads=mod.total_downloads,
                    mod_picture_url=mod.picture_url,
                    mod_summary=mod.summary,
                    file_id=target_file.file_id,
                    file_name=target_file.name,
                    file_version=target_file.version,
                    file_size_kb=target_file.size_kb,
                    file_category=target_file.category_name,
                    file_uploaded_timestamp=target_file.uploaded_timestamp,
                    nexus_url=f"https://www.nexusmods.com/{mod.game_domain}/mods/{mod.mod_id}",
                    mod_root_path=sidebar.get_mod_root_path() if sidebar else None,
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

    def on_sidebar_file_selected(self, file_id: int):
        """Handle sidebar file selection change: update details to show the specific file."""
        try:
            sidebar = getattr(self, "nexus_details_sidebar", None)
            if not sidebar:
                return

            mod = sidebar.current_mod()
            if not mod:
                return

            if not self.nexus_service.has_api_key:
                return

            try:
                files = self.nexus_service.get_mod_files(mod.game_domain, mod.mod_id)
                target_file = next((f for f in files if f.file_id == file_id), None)

                if target_file:
                    sidebar.set_details(mod, target_file)
            except Exception:
                pass

        except Exception:
            pass

    def on_sidebar_mod_root_changed(self, new_root: str):
        """Handle manual edit of mod folder path in sidebar."""
        sidebar = getattr(self, "nexus_details_sidebar", None)
        if not sidebar:
            return
        mod = sidebar.current_mod()
        if not mod:
            return

        try:
            self.nexus_metadata.set_mod_root_path(
                mod.game_domain, mod.mod_id, new_root or None
            )
        except Exception:
            pass

    def download_selected_nexus_mod(
        self,
        mod=None,
        load_mods=True,
        mod_root_path: str | None = None,
        file_category: str | None = None,
        file_id: int | None = None,
        file_name: str | None = None,
        install_name: str | None = None,
        ignore_sidebar: bool = False,
    ):
        """Download and install a Nexus mod (zip only).

        Args:
            mod: Optional mod object. If None, uses sidebar's current mod.
            load_mods: Whether to refresh mod list after install.
            mod_root_path: Optional path within archive to use as mod root.
            file_category: Optional category preference (e.g. "MAIN", "UPDATE").
            file_id: Optional specific file ID to download. Takes precedence.
            file_name: Optional file name pattern to match (case-insensitive substring).
            install_name: Optional name for the installed folder (destination name).
            ignore_sidebar: If True, do not pull state (mod, file selection, rules) from the sidebar.
        """
        import logging

        sidebar = getattr(self, "nexus_details_sidebar", None)
        if hasattr(self, "nexus_details_sidebar") and not ignore_sidebar:
            sidebar = self.nexus_details_sidebar
        else:
            sidebar = None

        if mod is None:
            mod = sidebar.current_mod() if sidebar else None

        if not mod:
            return

        # If file_id not explicit, check from sidebar
        target_file_id = file_id
        if target_file_id is None and sidebar:
            target_file_id = sidebar.current_selected_file_id()

        if not file_category and sidebar and not target_file_id:
            # Fallback to category if no specific file selected (shouldn't happen with new sidebar)
            # But let's keep it safe.
            # sidebar.current_category() existed before? Now it's gone.
            # So we rely on target_file_id.
            pass

        if not self.nexus_service.has_api_key:
            self._update_status(tr("nexus_api_key_missing_status"))
            if sidebar:
                sidebar.set_status(tr("nexus_api_key_missing_status"))
            return

        log = logging.getLogger(__name__)

        try:
            files = self.nexus_service.get_mod_files(mod.game_domain, mod.mod_id)

            chosen = None
            if target_file_id:
                chosen = next((f for f in files if f.file_id == target_file_id), None)

            # If file_name provided, try to match by name pattern
            if not chosen and file_name:
                pattern = file_name.lower()
                for f in files:
                    if f.name and pattern in f.name.lower():
                        chosen = f
                        break

            if not chosen:
                # Fallback to picking by category or latest main
                # Since we removed current_category() from sidebar, we only have file_category arg
                chosen = self.nexus_service.pick_file(
                    files, category_preference=file_category or "MAIN"
                )

            if not chosen:
                raise NexusError("No downloadable files found for this mod.")

            url = None
            try:
                links = self.nexus_service.get_download_links(
                    mod.game_domain, mod.mod_id, chosen.file_id
                )
                if links:
                    url = links[0].url
            except NexusError as e:
                # Free users frequently get 403 here; fall back to WebView automation.
                log.info("API download_link blocked; falling back to WebView: %s", e)
                url = None

            if not url:
                # Compliant fallback for free users: open system browser and watch Downloads.
                from me3_manager.services.download_watcher import (
                    DownloadWatcher,
                    get_downloads_dir,
                )

                base = f"https://www.nexusmods.com/{mod.game_domain}/mods/{mod.mod_id}"
                candidates = [
                    f"{base}?tab=files&file_id={chosen.file_id}",
                    f"{base}?tab=files&file_id={chosen.file_id}&nmm=1",
                ]

                # NOTE: Nexus often blocks direct access to internal widget endpoints like
                # DownloadPopUp with an "Access Denied" page. Prefer full mod pages.
                try:
                    PlatformUtils.open_url(candidates[0])
                except Exception:
                    PlatformUtils.open_url(base)

                downloads_dir = get_downloads_dir()
                watcher = DownloadWatcher(
                    directory=downloads_dir, allowed_exts=tuple(ARCHIVE_EXTENSIONS)
                )

                progress = QProgressDialog(
                    tr("nexus_browser_download_waiting"),
                    tr("cancel_button"),
                    0,
                    0,
                    self,
                )
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)

                found_path: dict[str, str] = {}

                def _on_found(p: str):
                    found_path["path"] = p
                    progress.close()

                def _on_failed(msg: str):
                    found_path["error"] = msg
                    progress.close()

                watcher.found.connect(_on_found)
                watcher.failed.connect(_on_failed)
                progress.canceled.connect(watcher.requestInterruption)
                watcher.start()
                progress.exec()
                watcher.wait()

                if "path" not in found_path:
                    raise NexusError(
                        found_path.get("error") or "Failed to resolve download."
                    )

                # Install directly from the downloaded archive.
                dl_file = Path(found_path["path"])
                installed = self.mod_installer.install_mod(
                    dl_file,
                    mod_name_hint=(
                        mod.name
                        or chosen.name
                        or f"nexus_{mod.mod_id}_{chosen.file_id}"
                    ),
                    load_mods=load_mods,
                    mod_root_path=mod_root_path,
                )
                if installed:
                    # Track metadata for update checking (match API install behavior).
                    mods_dir = self.config_manager.get_mods_dir(self.game_name)
                    installed_name = (
                        installed[0]
                        if isinstance(installed[0], str)
                        else installed[0].name
                    )
                    folder_path = mods_dir / installed_name

                    if folder_path.exists() and folder_path.is_dir():
                        local_path = self._determine_metadata_local_path(folder_path)
                    else:
                        local_path = str(folder_path.resolve())

                    self.nexus_metadata.upsert_cache_for_mod(
                        game_domain=mod.game_domain,
                        mod_id=mod.mod_id,
                        local_mod_path=local_path,
                        file_id=chosen.file_id,
                        mod_name=mod.name,
                        mod_version=chosen.version,
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
                        mod_root_path=mod_root_path
                        or (sidebar.get_mod_root_path() if sidebar else None),
                    )

                    self._update_status(tr("nexus_install_success_status"))
                    if sidebar:
                        # Refresh sidebar details with updated file info
                        sidebar.set_details(mod, chosen)
                        sidebar.set_cached_text(tr("nexus_cached_just_now"))
                        sidebar.set_status(tr("nexus_install_success_status"))
                return installed

            with TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                # Get actual extension from file name, default to .zip
                file_ext = ".zip"
                if chosen.name:
                    ext = Path(chosen.name).suffix.lower()
                    if ext in ARCHIVE_EXTENSIONS:
                        file_ext = ext
                dl_path = tmp_dir / f"{mod.mod_id}-{chosen.file_id}{file_ext}"

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
                worker = NexusDownloadWorker(self.nexus_service, url, dl_path)

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

                # Use Nexus mod name as folder name, or override if install_name provided
                if install_name:
                    mod_name_hint = install_name.strip()
                else:
                    mod_name_hint = (
                        mod.name
                        or chosen.name
                        or f"nexus_{mod.mod_id}_{chosen.file_id}"
                    ).strip()

                mod_root_path = mod_root_path or (
                    sidebar.get_mod_root_path() if sidebar else None
                )

                # Save the folder rule for future updates if specified
                if mod_root_path:
                    self.nexus_metadata.set_mod_root_path(
                        game_domain=mod.game_domain,
                        mod_id=mod.mod_id,
                        mod_root_path=mod_root_path,
                    )

                # Install using unified API
                installed = self.mod_installer.install_mod(
                    dl_path,
                    mod_name_hint=mod_name_hint,
                    mod_root_path=mod_root_path,
                    delete_archive=True,
                    load_mods=load_mods,
                )

                # Capture interactively selected root path if one wasn't provided upfront
                if not mod_root_path:
                    selected_root = self.mod_installer.get_last_selected_mod_root_path()
                    if selected_root:
                        self.nexus_metadata.set_mod_root_path(
                            game_domain=mod.game_domain,
                            mod_id=mod.mod_id,
                            mod_root_path=selected_root,
                        )
                        if sidebar:
                            sidebar.set_mod_root_path(selected_root)

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

                    if folder_path.exists() and folder_path.is_dir():
                        local_path = self._determine_metadata_local_path(folder_path)
                    else:
                        local_path = str(folder_path.resolve())
                        log.debug("Folder doesn't exist: %s", folder_path)

                    log.debug("Saving metadata with local_path=%s", local_path)
                    self.nexus_metadata.upsert_cache_for_mod(
                        game_domain=mod.game_domain,
                        mod_id=mod.mod_id,
                        local_mod_path=local_path,
                        file_id=chosen.file_id,
                        mod_name=mod.name,
                        mod_version=chosen.version,
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
                        mod_root_path=mod_root_path
                        or (sidebar.get_mod_root_path() if sidebar else None),
                    )
                    log.debug("Metadata saved successfully")
                    self._update_status(tr("nexus_install_success_status"))
                    if sidebar:
                        # Refresh sidebar details with updated file info
                        sidebar.set_details(mod, chosen)
                        sidebar.set_cached_text(tr("nexus_cached_just_now"))
                        sidebar.set_status(tr("nexus_install_success_status"))

                    # Refresh mod list so any cached "update available" badge disappears immediately
                    try:
                        if load_mods:
                            self.load_mods(reset_page=False)
                    except Exception:
                        pass
                    return installed
                else:
                    if sidebar:
                        sidebar.set_status(tr("nexus_install_cancelled_status"))
                    return []
        except Exception as e:
            self._update_status(tr("nexus_download_failed_status", error=str(e)))
            if sidebar:
                sidebar.set_status(tr("nexus_download_failed_status", error=str(e)))
            return []

    def _determine_metadata_local_path(self, folder_path: Path) -> str:
        """
        Determine the correct local path key for metadata.

        Logic:
        - If folder contains game assets or regulation.bin -> It's a Package Mod -> Use folder path.
        - Otherwise -> It's a Native Mod wrapper -> Use the first DLL path found inside.
        """
        is_package_mod = False
        try:
            # Check recursively for any acceptable folder
            # If we find any standard mod folder anywhere inside, treat it as a Package Mod (Folder)
            # This covers standard mods, nested mods, and containers.
            for path in folder_path.rglob("*"):
                if path.is_dir() and path.name in ACCEPTABLE_FOLDERS:
                    is_package_mod = True
                    break

            # Check for regulation.bin (also recursive to be safe, though usually near root)
            if not is_package_mod:
                if (folder_path / "regulation.bin").exists() or (
                    folder_path / "regulation.bin.disabled"
                ).exists():
                    is_package_mod = True
                # Fallback check for nested regulation.bin if root check failed
                if not is_package_mod:
                    for bin_file in folder_path.rglob("regulation.bin*"):
                        if bin_file.name in (
                            "regulation.bin",
                            "regulation.bin.disabled",
                        ):
                            is_package_mod = True
                            break
        except Exception:
            pass

        if is_package_mod:
            # For package mods, key metadata by the folder path
            import logging

            log = logging.getLogger(__name__)
            local_path = str(folder_path.resolve())
            log.debug("Identified as Package Mod. Keying by folder: %s", local_path)
            return local_path
        else:
            # For native mods (DLL wrappers), prefer the DLL path
            import logging

            log = logging.getLogger(__name__)
            dlls_inside = list(folder_path.rglob("*.dll"))
            log.debug("Found DLLs: %s", dlls_inside)
            if dlls_inside:
                return str(dlls_inside[0].resolve())
            else:
                return str(folder_path.resolve())

    def open_selected_nexus_page(self):
        sidebar = getattr(self, "nexus_details_sidebar", None)
        url = sidebar.current_url() if sidebar else None
        if not url:
            return
        PlatformUtils.open_url(url)

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

            # Use tracked category if available so we check for updates to the correct stream
            pref = tracked.file_category if tracked else "MAIN"
            latest = self.nexus_service.pick_file(files, category_preference=pref)

            # NOTE: Do NOT update sidebar details or cache here - checking for updates
            # should only notify about availability without modifying displayed info.
            # Details are updated only after user installs the update.

            if (
                tracked
                and latest
                and tracked.file_id
                and latest.file_id != tracked.file_id
            ):
                if self.selected_local_mod_path:
                    self.nexus_metadata.set_update_check_result(
                        local_mod_path=self.selected_local_mod_path,
                        update_available=True,
                        latest_file_id=latest.file_id,
                        latest_version=latest.version,
                        error=None,
                    )
                sidebar.set_status(
                    tr("nexus_update_available_status", version=latest.version or "")
                )
            else:
                if self.selected_local_mod_path and tracked:
                    self.nexus_metadata.set_update_check_result(
                        local_mod_path=self.selected_local_mod_path,
                        update_available=False,
                        latest_file_id=latest.file_id if latest else None,
                        latest_version=latest.version if latest else None,
                        error=None,
                    )
                sidebar.set_status(tr("nexus_up_to_date_status"))
        except Exception as e:
            if self.selected_local_mod_path:
                self.nexus_metadata.set_update_check_error(
                    local_mod_path=self.selected_local_mod_path, error=str(e)
                )
            sidebar.set_status(tr("nexus_update_check_failed_status", error=str(e)))

    def check_updates_for_all_installed_mods_on_startup(self) -> None:
        """
        Background check for updates for all installed mods that are linked to Nexus.
        Non-blocking: runs in a worker thread and refreshes the mod list when done.
        """
        try:
            api_key = self.config_manager.get_nexus_api_key()
        except Exception:
            api_key = None

        self.nexus_service.set_api_key(api_key)
        if not self.nexus_service.has_api_key:
            return

        try:
            items = self.nexus_metadata.load_game("unknown")
        except Exception:
            items = {}

        tracked_mods = [
            m
            for m in items.values()
            if m
            and m.local_mod_path
            and m.mod_id
            and m.game_domain
            and m.file_id is not None
        ]
        if not tracked_mods:
            return

        # Avoid duplicate workers
        if getattr(self, "_startup_update_worker", None) is not None:
            try:
                if self._startup_update_worker.isRunning():
                    return
            except Exception:
                pass

        from PySide6.QtCore import QThread, Signal

        class _StartupUpdateWorker(QThread):
            finished_refresh = Signal()

            def __init__(self, gp: "GamePage", mods):
                super().__init__(gp)
                self.gp = gp
                self.mods = mods

            def run(self):
                for t in self.mods:
                    try:
                        files = self.gp.nexus_service.get_mod_files(
                            t.game_domain, int(t.mod_id)
                        )
                        # Respect stored file category preference (e.g. keep Optional mods updating as Optional)
                        pref = t.file_category or "MAIN"
                        latest = self.gp.nexus_service.pick_file(
                            files, category_preference=pref
                        )
                        if latest and t.file_id and latest.file_id != t.file_id:
                            self.gp.nexus_metadata.set_update_check_result(
                                local_mod_path=str(t.local_mod_path),
                                update_available=True,
                                latest_file_id=latest.file_id,
                                latest_version=latest.version,
                                error=None,
                            )
                        else:
                            self.gp.nexus_metadata.set_update_check_result(
                                local_mod_path=str(t.local_mod_path),
                                update_available=False,
                                latest_file_id=latest.file_id if latest else None,
                                latest_version=latest.version if latest else None,
                                error=None,
                            )
                    except Exception as e:
                        try:
                            self.gp.nexus_metadata.set_update_check_error(
                                local_mod_path=str(t.local_mod_path), error=str(e)
                            )
                        except Exception:
                            pass
                self.finished_refresh.emit()

        self._startup_update_worker = _StartupUpdateWorker(self, tracked_mods)
        self._startup_update_worker.finished_refresh.connect(
            lambda: self.load_mods(reset_page=False)
        )
        self._startup_update_worker.start()

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

            # Load saved folder path if any
            saved_root = self.nexus_metadata.get_mod_root_path(
                linked.game_domain, linked.mod_id
            )
            sidebar.set_mod_root_path(saved_root)

            # Populate files list with just the installed file for now (offline view)
            # If user wants more files, they can "Check Update" or we could auto-fetch if we wanted.
            # But primarily we must clear the old list.
            files_list = []
            if cached_file:
                files_list.append(cached_file)
            sidebar.populate_files(
                files_list, cached_file.file_id if cached_file else None
            )

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

    def rename_mod(self, mod_path: str):
        """Handle mod rename request."""
        # Find current name
        current_name = "Unknown"
        if mod_path in self.mod_infos:
            current_name = self.mod_infos[mod_path].name

        # Check if it has a custom name already
        try:
            mod_path_resolved = str(Path(mod_path).resolve())
            linked = self.nexus_metadata.find_for_local_mod(mod_path_resolved)
            if linked and linked.custom_name:
                current_name = linked.custom_name
            elif linked and linked.mod_name:
                # If we are using Nexus name but no custom name, we might want to start editing from that
                current_name = linked.mod_name
        except Exception:
            pass

        new_name, ok = QInputDialog.getText(
            self,
            tr("rename_mod_title", default="Rename Mod"),
            tr("rename_mod_msg", default="Enter new name:"),
            text=current_name,
        )

        if ok:
            # If empty string, we treat it as "reset to default" -> pass None
            final_name = new_name.strip() if new_name.strip() else None

            try:
                mod_path_resolved = str(Path(mod_path).resolve())
                self.nexus_metadata.set_mod_custom_name(mod_path_resolved, final_name)
                self.load_mods(reset_page=False)
                self._update_status(
                    tr("mod_renamed_status", default="Mod renamed successfully")
                )
            except Exception as e:
                self._update_status(
                    tr(
                        "mod_rename_failed_status",
                        default="Failed to rename mod: {error}",
                        error=str(e),
                    )
                )

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

        # List of DLLs that provide alternative save mechanisms.
        # Format: just the filename. We automatically check for the stem (name without extension) as well.
        alt_save_dlls = [
            "ersc.dll",
            "nrsc.dll",
            "ds3sc.dll",
            "nightreign_alt_saves.dll",
            "eldenring_alt_saves.dll",
            "armoredcore6_alt_saves.dll",
        ]

        # If Seamless Co-op or other alt-save mod is enabled, do not show the banner
        try:
            mods_data = getattr(self, "all_mods_data", {}) or {}
            seamless_enabled = False

            for mod_path, info in mods_data.items():
                if not info.get("enabled", False):
                    continue
                path_lower = str(mod_path).lower()
                name_lower = str(info.get("name", "")).lower()

                for dll in alt_save_dlls:
                    # 1. Check if file path ends with the dll name
                    if path_lower.endswith((f"/{dll}", f"\\{dll}")):
                        seamless_enabled = True
                        break

                    # 2. Check if mod name matches the stem (e.g. "ersc" for "ersc.dll")
                    stem = dll.rsplit(".", 1)[0]
                    # Original logic compatibility: ends with /stem OR equals stem
                    if (
                        name_lower.endswith((f"/{stem}", f"\\{stem}"))
                        or name_lower == stem
                    ):
                        seamless_enabled = True
                        break

                if seamless_enabled:
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
