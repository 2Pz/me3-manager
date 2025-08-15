import subprocess
import sys
import requests
import os
import re
from ui.game_management_dialog import GameManagementDialog

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QMessageBox, QProgressDialog, QFileDialog, QDialog, QFrame
)
from PyQt6.QtGui import QFont, QIcon, QDesktopServices
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QStandardPaths, QUrl, QTimer, pyqtSlot

from core.config_manager import ConfigManager
from core.me3_version_manager import ME3VersionManager  # Import the new version manager
from ui.game_page import GamePage
from ui.terminal import EmbeddedTerminal
from ui.draggable_game_button import DraggableGameButton, DraggableGameContainer
from ui.settings_dialog import SettingsDialog
from utils.resource_path import resource_path
from version import VERSION


class HelpAboutDialog(QDialog):
    """A custom dialog for Help, About, and maintenance actions."""
    def __init__(self, main_window, initial_setup=False):
        super().__init__(main_window)
        self.main_window = main_window
        self.version_manager = main_window.version_manager  # Use the centralized version manager
        self.setMinimumWidth(550)
        self.setStyleSheet("""
            QDialog { background-color: #252525; color: #ffffff; }
            QLabel { background-color: transparent; }
            QPushButton {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                padding: 10px 16px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3d3d3d; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; border-color: #333333; }
            #TitleLabel { font-size: 18px; font-weight: bold; }
            #VersionLabel { color: #aaaaaa; }
            #HeaderLabel { font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px; }
            #DownloadStableButton { background-color: #0078d4; border: none; }
            #DownloadStableButton:hover { background-color: #005a9e; }
            #KoFiButton { background-color: #0078d4; border: none; font-weight: bold; }
            #KoFiButton:hover { background-color: #106ebe; }
            #VideoLinkLabel { color: #0078d4; text-decoration: underline; }
            #VideoLinkLabel:hover { color: #005a9e; }
            #WarningLabel { color: #ff4d4d; font-size: 16px; font-weight: bold; }
            #WarningInfoLabel { color: #f0c674; margin-bottom: 5px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Mod Engine 3 Manager")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        
        versions_text = f"Manager Version: {VERSION}  |  ME3 CLI Version: {self.main_window.me3_version}"
        version_label = QLabel(versions_text)
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self.close_button = QPushButton()  # Defined here for use in if/else

        if initial_setup:
            self.setWindowTitle("ME3 Installation Required")
            
            warning_layout = QVBoxLayout()
            warning_layout.setSpacing(5)
            
            warning_label = QLabel("ME3 Not Installed")
            warning_label.setObjectName("WarningLabel")
            warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning_layout.addWidget(warning_label)

            warning_info_label = QLabel("The manager needs Mod Engine 3 installed to work properly.")
            warning_info_label.setObjectName("WarningInfoLabel")
            warning_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning_info_label.setWordWrap(True)
            warning_layout.addWidget(warning_info_label)
            
            layout.addLayout(warning_layout)
            self.close_button.setText("Install Later")
        else:
            self.setWindowTitle("Help / About")
            description = QLabel(
                "This application helps you manage all mods supported by Mod Engine 3.\n"
                "Use the options below to update or install ME3."
            )
            description.setWordWrap(True)
            layout.addWidget(description)
            self.close_button.setText("Close")
        
        video_header = QLabel("Tutorial")
        video_header.setObjectName("HeaderLabel")
        layout.addWidget(video_header)
        
        if sys.platform == "win32":
            video_link = QLabel('<a href="https://www.youtube.com/watch?v=2Pz123">How to Use ME3 Mod Manager | Full Setup & Mod Installation Guide</a>')
        else:
            # For Linux/macOS, use the same video link but with a different text
            # since the installation process is different.
            video_link = QLabel('<a href="https://www.youtube.com/watch?v=gMvBdP3TGDg">How to Use ME3 Mod Manager | Full Setup & Mod Installation Guide for LInux</a>')
        video_link.setObjectName("VideoLinkLabel")
        video_link.setOpenExternalLinks(True)
        video_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(video_link)
        
        actions_header = QLabel("Actions")
        actions_header.setObjectName("HeaderLabel")
        layout.addWidget(actions_header)
        
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)

        if sys.platform == "win32":
            self.setup_windows_buttons(actions_layout)
        else:
            self.setup_linux_buttons(actions_layout)

        layout.addLayout(actions_layout)
        layout.addStretch()
        
        button_box_layout = QHBoxLayout()
        
        support_button = QPushButton("Support Me on Ko-fi")
        support_button.setObjectName("KoFiButton")
        support_button.setCursor(Qt.CursorShape.PointingHandCursor)
        support_button.clicked.connect(self.open_kofi_link)
        button_box_layout.addWidget(support_button)

        button_box_layout.addStretch()
        
        self.close_button.clicked.connect(self.accept)
        button_box_layout.addWidget(self.close_button)
        
        layout.addLayout(button_box_layout)

    def open_kofi_link(self):
        url = QUrl("https://ko-fi.com/2pz123")
        QDesktopServices.openUrl(url)

    def setup_windows_buttons(self, layout):
        # Update ME3 button
        self.update_cli_button = QPushButton("Update ME3")
        self.update_cli_button.clicked.connect(self.handle_update_cli)
        if self.main_window.me3_version == "Not Installed":
            self.update_cli_button.setDisabled(True)
            self.update_cli_button.setToolTip("ME3 is not installed, cannot update.")
        layout.addWidget(self.update_cli_button)

        # Get version info using the centralized version manager
        versions_info = self.version_manager.get_available_versions()
        
        # Stable installer button
        btn_text = f"Download Latest Installer (Stable) (Recommended)"
        if versions_info['stable']['version']:
            btn_text += f" ({versions_info['stable']['version']})"
        self.stable_button = QPushButton(btn_text)
        #self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(lambda: self.handle_download('latest'))
        if not versions_info['stable']['available']:
            self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)

        # Custom installer button
        custom_btn_text = f"Custom Portable Installer (Env Fix)"
        if versions_info['stable']['version']:
            custom_btn_text += f" ({versions_info['stable']['version']})"
        self.custom_button = QPushButton(custom_btn_text)
        self.custom_button.setObjectName("DownloadStableButton")
        self.custom_button.clicked.connect(lambda: self.handle_custom_install('latest'))
        if not versions_info['stable']['available']:
            self.custom_button.setDisabled(True)
        layout.addWidget(self.custom_button)

        # Pre-release installer button
        btn_text = f"Download Pre-release Installer"
        if versions_info['prerelease']['version']:
            btn_text += f" ({versions_info['prerelease']['version']})"
        self.prerelease_button = QPushButton(btn_text)
        self.prerelease_button.clicked.connect(lambda: self.handle_download('prerelease'))
        if not versions_info['prerelease']['available']:
            self.prerelease_button.setDisabled(True)
        layout.addWidget(self.prerelease_button)
        
    def setup_linux_buttons(self, layout):
        """Creates buttons for Linux/macOS, highlighting the stable official script."""
        # Get version info using the centralized version manager
        versions_info = self.version_manager.get_available_versions()
        
        # Stable installer button (Official & Recommended)
        btn_text = "Install/Update with Official Stable Script (Recommended)"
        if versions_info['stable']['version']:
            btn_text += f" ({versions_info['stable']['version']})"
        self.stable_button = QPushButton(btn_text)
        self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(lambda: self.handle_linux_install('latest'))
        if not versions_info['stable']['available']:
            self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)
        
        # Pre-release installer button
        btn_text = "Install/Update with Official Pre-release Script"
        if versions_info['prerelease']['version']:
            btn_text += f" ({versions_info['prerelease']['version']})"
        self.prerelease_button = QPushButton(btn_text)
        self.prerelease_button.clicked.connect(lambda: self.handle_linux_install('prerelease'))
        if not versions_info['prerelease']['available']:
            self.prerelease_button.setDisabled(True)
        layout.addWidget(self.prerelease_button)

    def handle_custom_install(self, release_type):
        """Handle custom Windows ME3 installation using the version manager."""
        self.version_manager.custom_install_windows_me3(release_type)
        self.accept()

    def handle_update_cli(self):
        """Handle ME3 CLI update using the version manager."""
        self.version_manager.update_me3_cli()
        self.accept()

    def handle_download(self, release_type):
        """Handle Windows installer download using the version manager."""
        self.version_manager.download_windows_installer(release_type)
        self.accept()
        
    def handle_linux_install(self, release_type):
        """Handle Linux ME3 installation using the version manager."""
        self.version_manager.install_linux_me3(release_type)
        self.accept()


class ModEngine3Manager(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.me3_version = self.get_me3_version()
        
        # Initialize the centralized version manager
        self.version_manager = ME3VersionManager(
        parent_widget=self,
        config_manager=self.config_manager,
        refresh_callback=self.refresh_me3_status 
    )
        
        self.init_ui()

   
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.perform_global_refresh)

        # Connect BOTH directory and file change signals to the same refresh slot.
        self.config_manager.file_watcher.directoryChanged.connect(self.schedule_global_refresh)
        self.config_manager.file_watcher.fileChanged.connect(self.schedule_global_refresh) 

        self.check_me3_installation()
        self.auto_launch_steam_if_enabled()
        self.check_for_me3_updates_if_enabled()

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
        for game_name in game_order:
            btn = DraggableGameButton(game_name)
            btn.setFixedHeight(45)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 8px;
                    padding: 8px 16px; text-align: left; font-size: 13px; font-weight: 500;
                }
                QPushButton:hover { background-color: #3d3d3d; border-color: #4d4d4d; }
                QPushButton:checked { background-color: #0078d4; border-color: #0078d4; color: white; }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, name=game_name: self.switch_game(name))
            self.game_container.add_game_button(game_name, btn)
            self.game_buttons[game_name] = btn
        
        self.game_container.set_game_order(game_order)

        # 5. Rebuild the game pages in the content area
        from ui.game_page import GamePage
        # Iterate through the ordered list to add pages sequentially
        for game_name in game_order:
            if game_name in self.config_manager.games:
                page = GamePage(game_name, self.config_manager)
                page.setVisible(False)
                self.content_layout.addWidget(page)  # Add to the end of the (now empty) layout
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

    def check_for_me3_updates_if_enabled(self):
        """Check for ME3 updates on startup if enabled in settings."""
        if not self.config_manager.get_check_for_updates():
            return
            
        if self.me3_version == "Not Installed":
            return
            
        update_info = self.version_manager.check_for_updates()
        if update_info.get('has_stable_update', False):
            stable_version = update_info.get('stable_version', 'Unknown')
            current_version = update_info.get('current_version', 'Unknown')
            
            reply = QMessageBox.question(
                self,
                "ME3 Update Available",
                f"A new version of ME3 is available!\n\n"
                f"Current version: {current_version}\n"
                f"New version: {stable_version}\n\n"
                f"Would you like to update now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if sys.platform == "win32":
                    self.version_manager.download_windows_installer('latest')
                else:
                    self.version_manager.install_linux_me3('latest')

    def _prepare_command(self, cmd: list) -> list:
        """Enhanced command preparation with better environment handling."""
        if sys.platform == "linux" and os.environ.get('FLATPAK_ID'):
            return ["flatpak-spawn", "--host"] + cmd
        return cmd

    def open_file_or_directory(self, path: str, run_file: bool = False):
        try:
            target_path = path if run_file else os.path.dirname(path)
            if sys.platform == "win32":
                os.startfile(target_path)
            else: # Linux
                subprocess.run(["xdg-open", target_path], check=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not perform action: {e}")

    def strip_ansi_codes(self, text: str) -> str:
        return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub('', text)
    
    def get_me3_version(self):
        version = self.config_manager.get_me3_version()
        if version:
            return f"v{version}"
        return "Not Installed"
    
    def init_ui(self):
        self.setWindowTitle("Mod Engine 3 Manager")
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
        splitter.setSizes([250, 950])
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
    
    def create_sidebar(self, parent):
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("QWidget { background-color: #252525; border-right: 1px solid #3d3d3d; }")
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
        for game_name in game_order:
            btn = DraggableGameButton(game_name)
            btn.setFixedHeight(45)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 8px;
                    padding: 8px 16px; text-align: left; font-size: 13px; font-weight: 500;
                }
                QPushButton:hover { background-color: #3d3d3d; border-color: #4d4d4d; }
                QPushButton:checked { background-color: #0078d4; border-color: #0078d4; color: white; }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, name=game_name: self.switch_game(name))
            self.game_container.add_game_button(game_name, btn)
            self.game_buttons[game_name] = btn
        self.game_container.set_game_order(game_order)
        layout.addWidget(self.game_container)
        layout.addStretch()
        
        # Manage Games button
        manage_games_button = QPushButton("Manage Games")
        manage_games_button.clicked.connect(self.show_game_management_dialog)
        layout.addWidget(manage_games_button)
        
        help_button = QPushButton("Help / About")
        help_button.clicked.connect(self.show_help_dialog)
        layout.addWidget(help_button)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(settings_button)
        footer_text = f"Manager v{VERSION}\nME3 CLI: {self.me3_version}\nby 2Pz"
        self.footer_label = QLabel(footer_text)
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #888888; font-size: 10px; line-height: 1.4;")
        layout.addWidget(self.footer_label)
        parent.addWidget(sidebar)

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
        
        first_game = self.config_manager.get_game_order()[0]
        self.switch_game(first_game)
        self.terminal = EmbeddedTerminal()
        self.content_layout.addWidget(self.terminal)
        parent.addWidget(self.content_stack)

    def check_me3_installation(self):
        if self.me3_version == "Not Installed":
            self.prompt_for_me3_installation()

    def prompt_for_me3_installation(self):
        """Shows the installer dialog when ME3 is not found on startup."""
        dialog = HelpAboutDialog(self, initial_setup=True)
        dialog.exec()

    def refresh_me3_status(self):
        """Refresh ME3 status and update UI components."""
        old_version = self.me3_version
        self.config_manager.refresh_me3_info()
        self.me3_version = self.get_me3_version()

        if old_version != self.me3_version:
            # Update footer label
            self.footer_label.setText(f"Manager v{VERSION}\nME3 CLI: {self.me3_version}\nby 2Pz")
            
            # Trigger a full refresh of the application state
            self.perform_global_refresh()
            
           # print(f"ME3 version updated: {old_version} -> {self.me3_version}")

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

    @pyqtSlot(str)
    def schedule_global_refresh(self, path: str):
        """
        This method is triggered by the QFileSystemWatcher. It starts a
        debounced timer to perform a full refresh, preventing rapid-fire updates.
        """
        #print(f"Filesystem change detected at: {path}. Scheduling a full refresh.")
        self.refresh_timer.start(500)

    def perform_global_refresh(self):
        """
        This is the master refresh function. It cleans the config and then forces
        every single game page to completely reload its UI from that clean config.
        """
        #print("Performing global state refresh...")

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

        #print("Global refresh complete.")
    
    def on_game_order_changed(self, new_order):
        self.config_manager.set_game_order(new_order)

    def auto_launch_steam_if_enabled(self):
        if self.config_manager.get_auto_launch_steam():
            if not self.config_manager.launch_steam_silently():
                print("Failed to launch Steam (or it's already running).")

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

    def download_me3_installer(self, release_type='latest'):
        """Download ME3 installer using the version manager."""
        if sys.platform == "win32":
            self.version_manager.download_windows_installer(release_type)
        else:
            QMessageBox.information(self, "Platform Info", 
                                  "Use the Linux installation scripts from the Help/About dialog instead.")

    def install_me3_linux(self, release_type='latest'):
        """Install ME3 on Linux using the version manager."""
        if sys.platform != "win32":
            self.version_manager.install_linux_me3(release_type)
        else:
            QMessageBox.information(self, "Platform Info", 
                                  "Use the Windows installer download from the Help/About dialog instead.")