import subprocess
import sys
import requests
import os
import re

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QMessageBox, QProgressDialog, QFileDialog, QDialog, QFrame
)
from PyQt6.QtGui import QFont, QIcon, QDesktopServices
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QStandardPaths, QUrl, QTimer, pyqtSlot

from core.config_manager import ConfigManager
from ui.game_page import GamePage
from ui.terminal import EmbeddedTerminal
from ui.draggable_game_button import DraggableGameButton, DraggableGameContainer
from ui.settings_dialog import SettingsDialog
from utils.resource_path import resource_path
from version import VERSION

class ME3Downloader(QObject):
    """Handles downloading a file in a separate thread (for Windows installer)."""
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str, str) # message, file_path

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self._is_cancelled = False

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        self.download_finished.emit("Download cancelled.", "")
                        return
                    if chunk:
                        bytes_downloaded += len(chunk)
                        f.write(chunk)
                        if total_size > 0:
                            progress = int((bytes_downloaded / total_size) * 100)
                            self.download_progress.emit(progress)
            self.download_finished.emit("Download complete!", self.save_path)
        except requests.RequestException as e:
            self.download_finished.emit(f"Network error: {e}", "")
        except Exception as e:
            self.download_finished.emit(f"An error occurred: {e}", "")

    def cancel(self):
        self._is_cancelled = True

class ME3Updater(QObject):
    """Runs 'me3 update' in a separate thread to prevent UI freezing."""
    update_finished = pyqtSignal(int, str) # return_code, output_message

    def __init__(self, prepare_command_func):
        super().__init__()
        self._prepare_command = prepare_command_func

    def run(self):
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            cmd = self._prepare_command(["me3", "update"])
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False,
                startupinfo=startupinfo, timeout=120
            )
            output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
            self.update_finished.emit(result.returncode, output)
        except FileNotFoundError:
            self.update_finished.emit(-1, "'me3' command not found. Make sure it is installed and in your system's PATH.")
        except subprocess.TimeoutExpired:
            self.update_finished.emit(-2, "The update process timed out after 2 minutes.")
        except Exception as e:
            self.update_finished.emit(-3, f"An unexpected error occurred: {e}")

class ME3LinuxInstaller(QObject):
    """Runs ME3 installer script in a separate thread for Linux/macOS."""
    install_finished = pyqtSignal(int, str)  # return_code, output_message

    def __init__(self, installer_url, prepare_command_func, env_vars=None):
        super().__init__()
        self.installer_url = installer_url
        self.env_vars = env_vars if env_vars else {}

    def run(self):
        """
        Executes the installer script by piping curl's output to a shell.
        """
        try:
            # Start with the current environment
            env = os.environ.copy()
            # Set required vars and merge any custom ones (like VERSION)
            env['ME3_QUIET'] = 'no'
            env.update(self.env_vars)

            command_string = f"curl --proto '=https' --tlsv1.2 -sSfL {self.installer_url} | sh"
            is_flatpak = sys.platform == "linux" and os.environ.get('FLATPAK_ID')

            if is_flatpak:
                cmd = ["flatpak-spawn", "--host", "sh", "-c", command_string]
                use_shell = False
            else:
                cmd = command_string
                use_shell = True

            result = subprocess.run(
                cmd,
                shell=use_shell,
                capture_output=True,
                text=True,
                check=False,
                timeout=150,
                env=env
            )

            output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
            self.install_finished.emit(result.returncode, output)

        except subprocess.TimeoutExpired:
            self.install_finished.emit(-2, "The installation process timed out after 2.5 minutes.")
        except Exception as e:
            self.install_finished.emit(-3, f"An unexpected error occurred: {e}")


    def _prepare_command(self, cmd: list) -> list:
        """Enhanced command preparation with better environment handling."""
        if sys.platform == "linux" and os.environ.get('FLATPAK_ID'):
            # For Flatpak, we need to spawn the command on the host system
            return ["flatpak-spawn", "--host"] + cmd
        return cmd


class HelpAboutDialog(QDialog):
    """A custom dialog for Help, About, and maintenance actions."""
    def __init__(self, main_window, initial_setup=False):
        super().__init__(main_window)
        self.main_window = main_window
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

        self.close_button = QPushButton() # Defined here for use in if/else

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
        
        video_link = QLabel('<a href="https://www.youtube.com/watch?v=Xtshnmu6Y2o">How to Use ME3 Mod Manager | Full Setup & Mod Installation Guide</a>')
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
        self.update_cli_button = QPushButton("Update ME3")
        self.update_cli_button.clicked.connect(self.handle_update_cli)
        if self.main_window.me3_version == "Not Installed":
            self.update_cli_button.setDisabled(True)
            self.update_cli_button.setToolTip("ME3 is not installed, cannot update.")
        layout.addWidget(self.update_cli_button)

        stable_v, stable_url = self.main_window._fetch_github_release_info('latest')
        prerelease_v, prerelease_url = self.main_window._fetch_github_release_info('prerelease')
        
        btn_text = f"Download Latest Installer (Stable) (Recommended)"
        if stable_v: btn_text += f" ({stable_v})"
        self.stable_button = QPushButton(btn_text)
        self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(lambda: self.handle_download('latest', stable_url))
        if not stable_url: self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)

        btn_text = f"Download Pre-release Installer"
        if prerelease_v: btn_text += f" ({prerelease_v})"
        self.prerelease_button = QPushButton(btn_text)
        self.prerelease_button.clicked.connect(lambda: self.handle_download('prerelease', prerelease_url))
        if not prerelease_url: self.prerelease_button.setDisabled(True)
        layout.addWidget(self.prerelease_button)
    
    def setup_linux_buttons(self, layout):
        """Creates buttons for Linux/macOS, highlighting the stable official script."""
        stable_v, stable_url = self.main_window._fetch_github_release_info('latest')
        prerelease_v, prerelease_url = self.main_window._fetch_github_release_info('prerelease')
        
        # Stable installer button (Official & Recommended)
        btn_text = "Install/Update with Official Stable Script (Recommended)"
        if stable_v: btn_text += f" ({stable_v})"
        self.stable_button = QPushButton(btn_text)
        self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(lambda: self.handle_linux_install('latest', stable_url))
        if not stable_url: self.stable_button.setDisabled(True)
        layout.addWidget(self.stable_button)
        
        # Custom installer button (Alternative)
        custom_button = QPushButton("Install/Update with Custom Script")
        custom_button.setToolTip("An alternative custom script for better error handling.")
        custom_button.clicked.connect(self.handle_custom_install)
        layout.addWidget(custom_button)

        # Pre-release installer button
        btn_text = "Install/Update with Official Pre-release Script"
        if prerelease_v: btn_text += f" ({prerelease_v})"
        self.prerelease_button = QPushButton(btn_text)
        self.prerelease_button.clicked.connect(lambda: self.handle_linux_install('prerelease', prerelease_url))
        if not prerelease_url: self.prerelease_button.setDisabled(True)
        layout.addWidget(self.prerelease_button)

    def handle_custom_install(self):
        """Handle installation using the custom installer script."""
        custom_installer_url = "https://github.com/2Pz/me3-manager/releases/download/Linux-0.0.1/installer.sh"
        self.main_window._start_custom_install_process(custom_installer_url)
        self.accept()

    def handle_update_cli(self):
        self.main_window.trigger_cli_update()
        self.accept()

    def handle_download(self, release_type, url):
        self.main_window._start_download_process(url)
        self.accept()
        
    def handle_linux_install(self, release_type, url):
        self.main_window._start_linux_install_process(url)
        self.accept()


class ModEngine3Manager(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        super().__init__()
        self.config_manager = ConfigManager()
        self.me3_version = self.get_me3_version()
        self.init_ui()
   
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.perform_global_refresh)

        # Connect BOTH directory and file change signals to the same refresh slot.
        self.config_manager.file_watcher.directoryChanged.connect(self.schedule_global_refresh)
        self.config_manager.file_watcher.fileChanged.connect(self.schedule_global_refresh) 

        self.check_me3_installation()
        self.auto_launch_steam_if_enabled()


    def _fetch_github_version_python(self) -> str | None:
        """Uses Python's requests to fetch the latest ME3 release version from GitHub."""
        api_url = "https://api.github.com/repos/garyttierney/me3/releases/latest"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            version = data.get('tag_name')
            if version and version.startswith('v'):
                print(f"Successfully fetched version from GitHub API: {version}")
                return version
        except requests.RequestException as e:
            print(f"Python-based GitHub API request failed: {e}")
            return None
        return None

    def _prepare_command(self, cmd: list) -> list:
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
    
    def trigger_cli_update(self):
        self.progress_dialog = QProgressDialog("Running 'me3 update'...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Updating ME3 CLI")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)

        self.thread = QThread()
        self.updater = ME3Updater(self._prepare_command)
        self.updater.moveToThread(self.thread)
        self.updater.update_finished.connect(self.on_update_finished)
        self.thread.started.connect(self.updater.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def on_update_finished(self, return_code, output):
        self.thread.quit()
        self.thread.wait()
        if hasattr(self, 'progress_dialog'): self.progress_dialog.close()
        
        clean_output = self.strip_ansi_codes(output)
        self.refresh_me3_status()
        
        if return_code == 0:
            QMessageBox.information(self, "Update Complete", clean_output)
        else:
            QMessageBox.warning(self, "Update Failed", f"The update command failed:\n\n{clean_output}")
    
    def _fetch_github_release_info(self, release_type: str) -> tuple[str | None, str | None]:
        asset_name = 'me3_installer.exe' if sys.platform == "win32" else 'installer.sh'
        repo_api_base = "https://api.github.com/repos/garyttierney/me3/releases"
        try:
            if release_type == 'latest':
                api_url = f"{repo_api_base}/latest"
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                release_data = response.json()
            elif release_type == 'prerelease':
                api_url = repo_api_base
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                release_data = None
                for release in response.json():
                    if release.get('prerelease', False):
                        release_data = release
                        break
                if release_data is None: return None, None
            else: return None, None

            version_tag = release_data.get('tag_name')
            for asset in release_data.get('assets', []):
                if asset.get('name') == asset_name:
                    return version_tag, asset.get('browser_download_url')
        except requests.RequestException:
            return None, None
        return None, None

    def _start_download_process(self, download_url: str):
        if not download_url: 
            QMessageBox.warning(self, "Error", "Download URL is not available.")
            return
        downloads_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        save_path, _ = QFileDialog.getSaveFileName(self, "Save ME3 Installer", os.path.join(downloads_path, "me3_installer.exe"), "Executable Files (*.exe)")
        if not save_path: return

        self.progress_dialog = QProgressDialog("Downloading me3_installer.exe...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Downloading")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download)
        
        self.thread = QThread()
        self.downloader = ME3Downloader(download_url, save_path)
        self.downloader.moveToThread(self.thread)
        self.downloader.download_progress.connect(self.progress_dialog.setValue)
        self.downloader.download_finished.connect(self.on_download_finished)
        self.thread.started.connect(self.downloader.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def cancel_download(self):
        if hasattr(self, 'downloader'): self.downloader.cancel()

    def on_download_finished(self, message, file_path):
        self.thread.quit()
        self.thread.wait()
        if hasattr(self, 'progress_dialog'): self.progress_dialog.close()
        
        if "complete" in message.lower() and file_path:
            reply = QMessageBox.information(self, "Download Complete", 
                f"ME3 installer downloaded to:\n{file_path}\n\nWould you like to run it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.open_file_or_directory(file_path, run_file=True)
                QMessageBox.information(self, "Installation", "The installer has been launched.\nThe manager will automatically refresh once installation is complete.")
        elif "cancelled" not in message.lower():
            QMessageBox.critical(self, "Download Failed", message)
        
        self.refresh_me3_status_and_ui()

    def _start_linux_install_process(self, installer_url: str):
        if not installer_url:
            QMessageBox.warning(self, "Error", "Installer URL is not available.")
            return

        reply = QMessageBox.question(self, "Install ME3",
            "This will run the official ME3 installer script.\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # Silently fetch the version and prepare environment variables
            env_vars = {}
            latest_version = self._fetch_github_version_python()
            if latest_version:
                # If found, set the VERSION for the script to use
                env_vars['VERSION'] = latest_version
            # If not found, do nothing; the script will use its own logic.

            self.progress_dialog = QProgressDialog("Running ME3 installer script...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Installing ME3")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setCancelButton(None)

            self.thread = QThread()
            self.installer = ME3LinuxInstaller(installer_url, self._prepare_command, env_vars)
            self.installer.moveToThread(self.thread)
            self.installer.install_finished.connect(self.on_linux_install_finished)
            self.thread.started.connect(self.installer.run)
            self.thread.start()
            self.progress_dialog.show()

    def _start_custom_install_process(self, installer_url: str):
        """Start the custom ME3 installation process for Linux/macOS."""
        reply = QMessageBox.question(self, "Install ME3 (Custom Script)",
            "This will run an alternative, custom ME3 installer script.\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # Silently fetch the version and prepare environment variables
            env_vars = {}
            latest_version = self._fetch_github_version_python()
            if latest_version:
                # If found, set the VERSION for the script to use
                env_vars['VERSION'] = latest_version
            # If not found, do nothing; the script will use its own logic.

            self.progress_dialog = QProgressDialog("Running ME3 installer script...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Installing ME3")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setCancelButton(None)

            self.thread = QThread()
            self.installer = ME3LinuxInstaller(installer_url, self._prepare_command, env_vars)
            self.installer.moveToThread(self.thread)
            self.installer.install_finished.connect(self.on_linux_install_finished)
            self.thread.started.connect(self.installer.run)
            self.thread.start()
            self.progress_dialog.show()

    def on_linux_install_finished(self, return_code, output):
        self.thread.quit()
        self.thread.wait()
        if hasattr(self, 'progress_dialog'): self.progress_dialog.close()

        clean_output = self.strip_ansi_codes(output)
        
        if return_code == 0:
            # Try to find the version from the script's output for a more informative message
            version_match = re.search(r"using latest version: (v[0-9]+\.[0-9]+\.[0-9]+)", clean_output)
            final_message = "Installation Complete"
            
            if version_match:
                installed_version = version_match.group(1)
                final_message += f"\n\nVersion Installed: {installed_version}"
            
            final_message += f"\n\n{clean_output}"
            
            QMessageBox.information(self, "Installation Complete", final_message)
            
            # Auto-refresh the UI after successful installation
            self.refresh_me3_status_and_ui()
        else:
            QMessageBox.warning(self, "Installation Failed", f"The script failed:\n\n{clean_output}")
            # Still refresh in case of partial installation
            self.refresh_me3_status_and_ui()

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

    def refresh_me3_status_and_ui(self):
        """Refresh ME3 status and update UI without requiring app restart."""
        old_version = self.me3_version
        self.config_manager.refresh_me3_info()
        self.me3_version = self.get_me3_version()

        # Update footer label
        self.footer_label.setText(f"Manager v{VERSION}\nME3 CLI: {self.me3_version}\nby 2Pz")
        
        # If ME3 was just installed, refresh all game pages to enable functionality
        if old_version == "Not Installed" and self.me3_version != "Not Installed":
            QMessageBox.information(self, "ME3 Ready", f"ME3 {self.me3_version} is now installed and ready to use!")
            # Refresh all game pages to enable ME3-dependent features
            self.perform_global_refresh()
        elif old_version != self.me3_version and self.me3_version != "Not Installed":
            QMessageBox.information(self, "ME3 Updated", f"ME3 updated from {old_version} to {self.me3_version}.")

    def refresh_me3_status(self):
        """Legacy method - now calls the enhanced version."""
        self.refresh_me3_status_and_ui()

    def switch_game(self, game_name: str):
        for name, button in self.game_buttons.items(): button.setChecked(name == game_name)
        for name, page in self.game_pages.items(): page.setVisible(name == game_name)
    
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
        print(f"Filesystem change detected at: {path}. Scheduling a full refresh.")
        self.refresh_timer.start(500)

    def perform_global_refresh(self):
        """
        This is the master refresh function. It cleans the config and then forces
        every single game page to completely reload its UI from that clean config.
        """
        print("Performing global state refresh...")

        # Step 1: Prune the master list of profiles from the settings file.
        # This removes profiles whose folders have been deleted.
        self.config_manager.validate_and_prune_profiles()

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

        print("Global refresh complete.")
    
    def on_game_order_changed(self, new_order):
        self.config_manager.set_game_order(new_order)

    def auto_launch_steam_if_enabled(self):
        if self.config_manager.get_auto_launch_steam():
            if not self.config_manager.launch_steam_silently():
                print("Failed to launch Steam (or it's already running).")

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()
