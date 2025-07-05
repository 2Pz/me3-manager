import subprocess
import sys
import requests
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QMessageBox, QProgressDialog, QFileDialog, QDialog, QFrame
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QStandardPaths

from core.config_manager import ConfigManager
from ui.game_page import GamePage
from ui.terminal import EmbeddedTerminal
from ui.draggable_game_button import DraggableGameButton, DraggableGameContainer
from utils.resource_path import resource_path
from version import VERSION

class ME3Downloader(QObject):
    """Handles downloading a file in a separate thread."""
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str, str) 

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
    update_finished = pyqtSignal(int, str) 
    def run(self):
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                ["me3", "update"],
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                timeout=120
            )
            output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
            self.update_finished.emit(result.returncode, output)
        except FileNotFoundError:
            self.update_finished.emit(-1, "'me3' command not found. Make sure it is installed and in your system's PATH.")
        except subprocess.TimeoutExpired:
            self.update_finished.emit(-2, "The update process timed out after 2 minutes.")
        except Exception as e:
            self.update_finished.emit(-3, f"An unexpected error occurred: {e}")


class HelpAboutDialog(QDialog):
    """A custom dialog for Help, About, and maintenance actions."""
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Help / About")
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

        description = QLabel(
            "This application helps you manage all mods supported by Mod Engine 3.\n"
            "Use the options below to update or download ME3 Stable/Pre-release"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        actions_header = QLabel("Actions")
        actions_header.setObjectName("HeaderLabel")
        layout.addWidget(actions_header)

        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)

        self.update_cli_button = QPushButton("Update ME3")
        self.update_cli_button.clicked.connect(self.handle_update_cli)
        if self.main_window.me3_version == "Not Installed":
            self.update_cli_button.setDisabled(True)
            self.update_cli_button.setToolTip("ME3 is not installed, cannot update.")
        actions_layout.addWidget(self.update_cli_button)

        stable_version, stable_url = self.main_window._fetch_github_release_info('latest')
        prerelease_version, prerelease_url = self.main_window._fetch_github_release_info('prerelease')
        
        stable_btn_text = "Download Latest Installer (Stable)"
        if stable_version: stable_btn_text += f" ({stable_version})"
        self.stable_button = QPushButton(stable_btn_text)
        self.stable_button.setObjectName("DownloadStableButton")
        self.stable_button.clicked.connect(lambda: self.handle_download('latest', stable_url))
        if not stable_url: self.stable_button.setDisabled(True)
        actions_layout.addWidget(self.stable_button)

        prerelease_btn_text = "Download Pre-release Installer"
        if prerelease_version: prerelease_btn_text += f" ({prerelease_version})"
        self.prerelease_button = QPushButton(prerelease_btn_text)
        self.prerelease_button.clicked.connect(lambda: self.handle_download('prerelease', prerelease_url))
        if not prerelease_url: self.prerelease_button.setDisabled(True)
        actions_layout.addWidget(self.prerelease_button)

        layout.addLayout(actions_layout)
        layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        
        button_box_layout = QHBoxLayout()
        button_box_layout.addStretch()
        button_box_layout.addWidget(close_button)
        layout.addLayout(button_box_layout)

    def handle_update_cli(self):
        self.main_window.trigger_cli_update()
        self.accept()

    def handle_download(self, release_type, url):
        if url:
            self.main_window._start_download_process(url)
        else:
            QMessageBox.warning(self, "Not Found", f"Could not find an installer for the {release_type} release.")
        self.accept()


class ModEngine3Manager(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.me3_version = self.get_me3_version()
        self.init_ui()
        self.setup_file_watcher()
    
    def get_me3_version(self):
        """Get the version of the me3 command-line tool."""
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["me3", "--version"],
                capture_output=True, text=True, check=True, startupinfo=startupinfo
            )
            parts = result.stdout.strip().split()
            return "v" + " ".join(parts[1:]) if len(parts) > 1 else "Unknown Format"
        except (FileNotFoundError, subprocess.CalledProcessError):
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
        """Create navigation sidebar"""
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
        help_button.setFixedHeight(35)
        help_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 8px;
                padding: 8px; text-align: center; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #4d4d4d; }
        """)
        help_button.clicked.connect(self.show_help_dialog)
        layout.addWidget(help_button)
        
        footer_text = f"Manager v{VERSION}\nME3 CLI: {self.me3_version}\nby 2Pz"
        self.footer_label = QLabel(footer_text)
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #888888; font-size: 10px; line-height: 1.4;")
        layout.addWidget(self.footer_label)
        parent.addWidget(sidebar)

    def show_help_dialog(self):
        """Shows the custom Help/About dialog."""
        dialog = HelpAboutDialog(self)
        dialog.exec()
    
    def trigger_cli_update(self):
        """Initiates the ME3 CLI update process in a separate thread."""
        self.update_progress_dialog = QProgressDialog("Running 'me3 update'...", None, 0, 0, self)
        self.update_progress_dialog.setWindowTitle("Updating ME3 CLI")
        self.update_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.update_progress_dialog.setCancelButton(None)

        self.update_thread = QThread()
        self.updater = ME3Updater()
        self.updater.moveToThread(self.update_thread)
        self.updater.update_finished.connect(self.on_cli_update_finished)
        self.update_thread.started.connect(self.updater.run)
        
        self.update_thread.start()
        self.update_progress_dialog.show()

    def on_cli_update_finished(self, return_code, output):
        """Handles the result of the ME3 CLI update process."""
        self.update_thread.quit()
        self.update_thread.wait()
        
        if hasattr(self, 'update_progress_dialog'):
            self.update_progress_dialog.close()
        
        old_version = self.me3_version
        self.me3_version = self.get_me3_version()
        
        if old_version != self.me3_version:
            new_footer_text = f"Manager v{VERSION}\nME3 CLI: {self.me3_version}\nby 2Pz"
            self.footer_label.setText(new_footer_text)
            output += f"\n\nSuccess! ME3 version updated from {old_version} to {self.me3_version}."
        
        if return_code == 0:
            QMessageBox.information(self, "Update Complete", output)
        else:
            QMessageBox.warning(self, "Update Failed", f"The update command failed with the following output:\n\n{output}")
    
    def _fetch_github_release_info(self, release_type: str) -> tuple[str | None, str | None]:
        """Fetches release version and download URL from GitHub."""
        asset_name = 'me3_installer.exe'
        repo_api_base = "https://api.github.com/repos/garyttierney/me3/releases"
        try:
            if release_type == 'latest':
                api_url = f"{repo_api_base}/latest"
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                release_data = response.json()
                version_tag = release_data.get('tag_name')
                for asset in release_data.get('assets', []):
                    if asset.get('name') == asset_name: return version_tag, asset.get('browser_download_url')
            elif release_type == 'prerelease':
                api_url = repo_api_base
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                for release in response.json():
                    if release.get('prerelease', False):
                        version_tag = release.get('tag_name')
                        for asset in release.get('assets', []):
                            if asset.get('name') == asset_name: return version_tag, asset.get('browser_download_url')
        except requests.RequestException: return None, None
        return None, None

    def _start_download_process(self, download_url: str):
        """Handles the file dialog and thread creation for the download."""
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
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        if hasattr(self, 'progress_dialog'): self.progress_dialog.close()
        
        if "complete" in message.lower():
            reply = QMessageBox.information(
                self, "Success", f"Download complete!\nSaved to: {file_path}\n\nDo you want to open the folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes and sys.platform == "win32":
                try: os.startfile(os.path.dirname(file_path))
                except Exception as e: QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
        elif "cancelled" not in message.lower():
            QMessageBox.critical(self, "Download Failed", message)

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
    
    def switch_game(self, game_name: str):
        for name, button in self.game_buttons.items(): button.setChecked(name == game_name)
        for name, page in self.game_pages.items(): page.setVisible(name == game_name)
    
    def setup_file_watcher(self):
        self.config_manager.file_watcher.directoryChanged.connect(self.on_mods_changed)
    
    def on_mods_changed(self, path: str):
        for page in self.game_pages.values(): page.load_mods()
    
    def on_game_order_changed(self, new_order):
        self.config_manager.set_game_order(new_order)
