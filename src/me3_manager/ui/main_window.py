import logging
import re
import sys

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from me3_manager import __version__ as VERSION
from me3_manager.core.config_facade import ConfigFacade
from me3_manager.core.me3_version_manager import ME3VersionManager
from me3_manager.services.app_update_checker import AppUpdateChecker
from me3_manager.services.steam_service import SteamService
from me3_manager.ui.app_controller import AppController
from me3_manager.ui.dialogs.game_management_dialog import GameManagementDialog
from me3_manager.ui.dialogs.help_about_dialog import HelpAboutDialog
from me3_manager.ui.dialogs.settings_dialog import SettingsDialog
from me3_manager.ui.draggable_game_button import (
    DraggableGameButton,
    DraggableGameContainer,
)
from me3_manager.ui.game_page import GamePage
from me3_manager.ui.terminal import EmbeddedTerminal
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.status import Status
from me3_manager.utils.translator import tr

log = logging.getLogger(__name__)

GAME_BUTTON_STYLE = """
    QPushButton {
        background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 8px;
        padding: 8px 16px; text-align: left; font-size: 13px; font-weight: 500;
    }
    QPushButton:hover { background-color: #3d3d3d; border-color: #4d4d4d; }
    QPushButton:checked { background-color: #0078d4; border-color: #0078d4; color: white; }
"""


class ModEngine3Manager(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigFacade()
        self.me3_version = self.get_me3_version()
        self.app_update_info = None  # Store update info for display

        # Initialize the centralized version manager
        self.version_manager = ME3VersionManager(
            parent_widget=self,
            config_manager=self.config_manager,
            path_manager=self.config_manager.path_manager,
            refresh_callback=self.refresh_me3_status,
        )

        # Initialize app update checker
        self.app_update_checker = AppUpdateChecker(VERSION)

        self.init_ui()

        # App-level controller orchestration
        self.steam_service = SteamService()
        self.app_controller = AppController(self, self.config_manager)
        self.app_controller.wire_file_watcher()
        self.app_controller.run_startup_checks()

    def add_game(self, game_name: str):
        if game_name in self.game_buttons:
            return
        btn = DraggableGameButton(game_name)
        btn.setFixedHeight(45)
        btn.setStyleSheet("/* same style as before */")
        btn.setCheckable(True)
        btn.clicked.connect(lambda checked, name=game_name: self.switch_game(name))
        self.game_container.add_game_button(game_name, btn)
        self.game_buttons[game_name] = btn

        page = GamePage(game_name, self.config_manager)
        page.setVisible(False)
        self.content_layout.insertWidget(-1, page)
        self.game_pages[game_name] = page

    def remove_game(self, game_name: str):
        btn = self.game_buttons.pop(game_name, None)
        if btn:
            self.game_container.remove_game_button(btn)
        page = self.game_pages.pop(game_name, None)
        if page:
            self.content_layout.removeWidget(page)
            page.deleteLater()

    def show_game_management_dialog(self):
        """Show the game management dialog"""
        dialog = GameManagementDialog(self.config_manager, self)
        dialog.games_changed.connect(self.refresh_sidebar)
        dialog.exec()

    def refresh_sidebar(self):
        """
        Refreshes the sidebar and content area after games have been
        added, removed, or reordered, ensuring the correct layout is maintained.
        """
        # 1. Preserve the current state (which game is selected)
        current_game = None
        for name, button in self.game_buttons.items():
            if button.isChecked():
                current_game = name
                break

        # 2. Detach the terminal to preserve it while we rebuild the layout
        self.content_layout.removeWidget(self.terminal)

        # 3. Completely clear all old UI elements
        # Clear sidebar buttons from the container
        for button in self.game_buttons.values():
            self.game_container.remove_game_button(button)
        self.game_buttons.clear()

        # Clear content pages from the layout and delete them
        for page in self.game_pages.values():
            self.content_layout.removeWidget(page)
            page.deleteLater()
        self.game_pages.clear()

        # At this point, the content_layout is empty.

        # 4. Rebuild the sidebar with the new game order
        game_order = self.config_manager.get_game_order()
        self._populate_game_buttons(game_order)

        # 5. Rebuild the game pages in the content area
        # Iterate through the ordered list to add pages sequentially
        for game_name in game_order:
            if game_name in self.config_manager.games:
                page = GamePage(game_name, self.config_manager)
                page.setVisible(False)
                self.content_layout.addWidget(
                    page
                )  # Add to the end of the (now empty) layout
                self.game_pages[game_name] = page

        # 6. Re-attach the terminal at the very end of the layout
        self.content_layout.addWidget(self.terminal)

        # 7. Restore the active game selection
        all_games = self.config_manager.get_game_order()
        if not all_games:
            # If no games are left, the view will be empty except for the terminal.
            pass
        elif current_game and current_game in self.game_buttons:
            # If the previously selected game still exists, re-select it.
            self.switch_game(current_game)
        else:
            # Otherwise, default to the first game in the new list.
            self.switch_game(all_games[0])

    def check_for_app_updates(self):
        """Check for me3-manager app updates on startup."""
        try:
            self.app_update_info = self.app_update_checker.check_for_updates()
            if self.app_update_info and self.app_update_info.get("update_available"):
                self.update_footer_text()
                log.info(
                    "App update available: %s -> %s",
                    self.app_update_info["current_version"],
                    self.app_update_info["latest_version"],
                )
        except Exception as e:
            log.error("Failed to check for app updates: %s", e)

    def check_for_me3_updates_if_enabled(self):
        """Check for ME3 updates on startup if enabled in settings."""
        if not self.config_manager.get_check_for_updates():
            return

        if (
            self.config_manager.me3_info_manager.get_me3_installation_status()
            == Status.NOT_INSTALLED
        ):
            return

        update_info = self.version_manager.check_for_updates()
        if update_info.get("has_stable_update", False):
            stable_version = update_info.get("stable_version", "Unknown")
            current_version = update_info.get("current_version", "Unknown")

            reply = QMessageBox.question(
                self,
                tr("me3_update_available_question_title"),
                tr(
                    "me3_update_available_question",
                    current_version=current_version,
                    stable_version=stable_version,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                if sys.platform == "win32":
                    # Route via version manager so portable installs use ZIP replacement
                    self.version_manager.update_me3_cli()
                else:
                    self.version_manager.install_linux_me3()

    def _prepare_command(self, cmd: list) -> list:
        """Enhanced command preparation with better environment handling."""
        return PlatformUtils.prepare_command(cmd)

    def open_file_or_directory(self, path: str, run_file: bool = False):
        try:
            ok = (
                PlatformUtils.open_dir(path)
                if not run_file
                else PlatformUtils.open_path(path, run_file=True)
            )
            if not ok:
                QMessageBox.warning(
                    self,
                    tr("ERROR"),
                    tr(
                        "could_not_perform_action", e="Desktop service rejected request"
                    ),
                )
        except Exception as e:
            QMessageBox.warning(self, tr("ERROR"), tr("could_not_perform_action", e=e))

    def strip_ansi_codes(self, text: str) -> str:
        return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])").sub("", text)

    def get_me3_version(self):
        version = self.config_manager.get_me3_version()
        if version:
            return f"v{version}"
        return tr("not_installed")

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.setWindowIcon(QIcon(resource_path("resources/icon/icon.ico")))
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
            QWidget { background-color: #1e1e1e; color: #ffffff; }
            QSplitter::handle { background-color: #3d3d3d; }
            QSplitter::handle:horizontal { width: 2px; }
        """)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.create_sidebar(splitter)
        self.create_content_area(splitter)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 940])
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def create_sidebar(self, parent):
        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar.setStyleSheet(
            "QWidget { background-color: #252525; border-right: 1px solid #3d3d3d; }"
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)
        title = QLabel("Mod Engine 3")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 16px;")
        layout.addWidget(title)
        self.game_container = DraggableGameContainer()
        self.game_container.game_order_changed.connect(self.on_game_order_changed)
        self.game_buttons = {}
        game_order = self.config_manager.get_game_order()
        self._populate_game_buttons(game_order)
        layout.addWidget(self.game_container)
        layout.addStretch()

        # Manage Games button
        manage_games_button = QPushButton(tr("manage_games"))
        manage_games_button.clicked.connect(self.show_game_management_dialog)
        layout.addWidget(manage_games_button)

        help_button = QPushButton(tr("help_about_title"))
        help_button.clicked.connect(self.show_help_dialog)
        layout.addWidget(help_button)
        settings_button = QPushButton(tr("settings"))
        settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(settings_button)

        # Create footer label with initial text
        self.footer_label = QLabel()
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet(
            "color: #888888; font-size: 10px; line-height: 1.4;"
        )
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setTextFormat(Qt.TextFormat.RichText)
        self.update_footer_text()  # Set initial text
        layout.addWidget(self.footer_label)
        parent.addWidget(sidebar)

    def _create_game_button(self, game_name: str) -> DraggableGameButton:
        """Create a styled game button for the sidebar."""
        btn = DraggableGameButton(game_name)
        btn.setFixedHeight(45)
        btn.setStyleSheet(GAME_BUTTON_STYLE)
        btn.setCheckable(True)
        btn.clicked.connect(lambda checked, name=game_name: self.switch_game(name))
        return btn

    def _populate_game_buttons(self, game_order: list[str]) -> None:
        """Populate the game container with buttons for each game in the order list."""
        for game_name in game_order:
            btn = self._create_game_button(game_name)
            self.game_container.add_game_button(game_name, btn)
            self.game_buttons[game_name] = btn
        self.game_container.set_game_order(game_order)

    def show_help_dialog(self):
        dialog = HelpAboutDialog(self, initial_setup=False)
        dialog.exec()

    def create_content_area(self, parent):
        self.content_stack = QWidget()
        self.content_layout = QVBoxLayout(self.content_stack)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.game_pages = {}
        for game_name in self.config_manager.games.keys():
            page = GamePage(game_name, self.config_manager)
            page.setVisible(False)
            self.content_layout.addWidget(page)
            self.game_pages[game_name] = page

        game_order = self.config_manager.get_game_order()
        if game_order:
            first_game = game_order[0]
            self.switch_game(first_game)

        self.terminal = EmbeddedTerminal()
        self.content_layout.addWidget(self.terminal)
        parent.addWidget(self.content_stack)

    def check_me3_installation(self):
        if (
            self.config_manager.me3_info_manager.get_me3_installation_status()
            == Status.NOT_INSTALLED
        ):
            self.prompt_for_me3_installation()

    def prompt_for_me3_installation(self):
        """Shows the installer dialog when ME3 is not found on startup."""
        dialog = HelpAboutDialog(self, initial_setup=True)
        dialog.exec()

    def update_footer_text(self):
        """Update footer text with version info and update notification if available."""
        base_text = tr("footer_text", VERSION=VERSION, me3_version=self.me3_version)
        # Convert \n to <br/> for HTML rendering
        base_text = base_text.replace("\n", "<br/>")

        if self.app_update_info and self.app_update_info.get("update_available"):
            latest_version = self.app_update_info.get("latest_version", "Unknown")
            download_url = self.app_update_info.get("download_url", "")
            update_text = tr(
                "app_update_available",
                latest_version=latest_version,
                download_url=download_url,
            )
            # Combine base text with update notification
            full_text = f"{base_text}<br/><br/>{update_text}"
            self.footer_label.setText(full_text)
        else:
            self.footer_label.setText(base_text)

    def refresh_me3_status(self):
        """Refresh ME3 status and update UI components."""
        old_version = self.me3_version
        self.config_manager.refresh_me3_info()
        self.me3_version = self.get_me3_version()

        if old_version != self.me3_version:
            # Update footer label
            self.update_footer_text()

            # Trigger a full refresh of the application state
            self.perform_global_refresh()

        log.info("ME3 version updated: %s -> %s", old_version, self.me3_version)

    def switch_game(self, game_name: str):
        for name, button in self.game_buttons.items():
            button.setChecked(name == game_name)
        for name, page in self.game_pages.items():
            page.setVisible(name == game_name)

    def setup_file_watcher(self):
        """
        This is a placeholder that is now handled by config_manager's own init.
        We just need to make sure the connection is right.
        """
        # The connection is now made in __init__ for robustness.
        # We can call setup_file_watcher() from config_manager to ensure paths are up-to-date.
        self.config_manager.setup_file_watcher()

    @Slot(str)
    def schedule_global_refresh(self, path: str):
        """
        This method is triggered by the QFileSystemWatcher. It starts a
        debounced timer to perform a full refresh, preventing rapid-fire updates.
        """

        # Delegate to controller's debounced timer
        if hasattr(self, "app_controller"):
            self.app_controller.schedule_global_refresh(500)
        else:
            pass

    def perform_global_refresh(self):
        """
        This is the master refresh function. It cleans the config and then forces
        every single game page to completely reload its UI from that clean config.
        """

        # Step 1: Prune the master list of profiles from the settings file.
        # This removes profiles whose folders have been deleted.
        self.config_manager.validate_and_prune_profiles()

        # After an install/update, re-validate the format of each active profile.
        for game_name in self.game_pages.keys():
            profile_path = self.config_manager.get_profile_path(game_name)
            if profile_path.exists():
                self.config_manager.check_and_reformat_profile(profile_path)

        # Step 2: For each game, sync the *active* profile's contents with the filesystem.
        # This removes individual mods from a profile if their files are gone.
        for game_name in self.game_pages.keys():
            self.config_manager.sync_profile_with_filesystem(game_name)

        # Step 3: Now that the config is fully clean, tell every game page to reload its UI.
        for game_page in self.game_pages.values():
            if isinstance(game_page, GamePage):
                # The simplified load_mods will now read the clean data and update the entire page,
                # including the profile dropdown.
                game_page.load_mods(reset_page=False)

        # Step 4: Update the file watcher to only monitor directories that still exist.
        self.config_manager.setup_file_watcher()

    def on_game_order_changed(self, new_order):
        self.config_manager.set_game_order(new_order)

    def auto_launch_steam_if_enabled(self):
        if self.config_manager.get_auto_launch_steam():
            # Try ME3-provided steam path first
            steam_path = None
            try:
                steam_path = self.config_manager.get_steam_path()
            except Exception:
                steam_path = None
            if not self.steam_service.launch(steam_path):
                log.warning("Failed to launch Steam (or it's already running)")

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def check_for_updates(self):
        """Check for available ME3 updates using the version manager."""
        return self.version_manager.check_for_updates()

    def get_available_me3_versions(self):
        """Get available ME3 versions using the version manager."""
        return self.version_manager.get_available_versions()

    def update_me3_cli(self):
        """Update ME3 CLI using the version manager."""
        self.version_manager.update_me3_cli()

    def download_me3_installer(self):
        """Download ME3 installer using the version manager."""
        if sys.platform == "win32":
            self.version_manager.download_windows_installer()
        else:
            QMessageBox.information(
                self, tr("platform_info"), tr("platform_info_desc_linux")
            )

    def install_me3_linux(self):
        """Install ME3 on Linux using the version manager."""
        if sys.platform != "win32":
            self.version_manager.install_linux_me3()
        else:
            QMessageBox.information(
                self, tr("platform_info"), tr("platform_info_desc_win")
            )
