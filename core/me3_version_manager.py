import subprocess
import sys
import requests
import os
import re
from typing import Optional, Tuple, Callable
from pathlib import Path
import zipfile
if sys.platform == "win32":
    import winreg
import requests
import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QStandardPaths
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QFileDialog
from PyQt6.QtCore import Qt, QTimer


class ME3Downloader(QObject):
    """Handles downloading ME3 installer files in a separate thread (for Windows)."""
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str, str)  # message, file_path

    def __init__(self, url: str, save_path: str):
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
    """Runs 'me3 update' command in a separate thread to prevent UI freezing."""
    update_finished = pyqtSignal(int, str)  # return_code, output_message

    def __init__(self, prepare_command_func: Callable[[list], list]):
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
                cmd, 
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


class ME3LinuxInstaller(QObject):
    """Runs ME3 installer script in a separate thread for Linux/macOS."""
    install_finished = pyqtSignal(int, str)  # return_code, output_message

    def __init__(self, installer_url: str, prepare_command_func: Callable[[list], list], env_vars: dict = None):
        super().__init__()
        self.installer_url = installer_url
        self._prepare_command = prepare_command_func
        self.env_vars = env_vars if env_vars else {}

    def run(self):
        """Executes the installer script by piping curl's output to a shell."""
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


class ME3VersionManager:
    """
    Centralized manager for ME3 version checking, updating, and installation.
    Handles both Windows and Linux/macOS platforms.
    """

    def __init__(self, parent_widget, config_manager, refresh_callback: Callable[[], None]):
        self.parent = parent_widget
        self.config_manager = config_manager
        self.refresh_callback = refresh_callback
        self.progress_dialog = None
        self.thread = None
        self.worker = None
        self.installation_monitor_timer = QTimer()
        self.installation_monitor_timer.timeout.connect(self._check_installation_status)
        self.monitoring_installation = False
        self.last_known_version = None

    def _prepare_command(self, cmd: list) -> list:
        """Enhanced command preparation with better environment handling."""
        if sys.platform == "linux" and os.environ.get('FLATPAK_ID'):
            # For Flatpak, we need to spawn the command on the host system
            return ["flatpak-spawn", "--host"] + cmd
        return cmd

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text."""
        return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub('', text)

    def _fetch_github_version_python(self) -> Optional[str]:
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

    def _fetch_github_release_info(self, release_type: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch GitHub release information.
        
        Args:
            release_type: 'latest' for stable release or 'prerelease' for pre-release
            
        Returns:
            Tuple of (version_tag, download_url)
        """
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
                if release_data is None:
                    return None, None
            else:
                return None, None

            version_tag = release_data.get('tag_name')
            for asset in release_data.get('assets', []):
                if asset.get('name') == asset_name:
                    return version_tag, asset.get('browser_download_url')
                    
        except requests.RequestException:
            return None, None
            
        return None, None

    def _open_file_or_directory(self, path: str, run_file: bool = False):
        """Open a file or directory using the system's default application."""
        try:
            target_path = path if run_file else os.path.dirname(path)
            if sys.platform == "win32":
                os.startfile(target_path)
            else:  # Linux/macOS
                subprocess.run(["xdg-open", target_path], check=True)
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Could not perform action: {e}")

    def update_me3_cli(self):
        """Update ME3 CLI using 'me3 update' command."""
        current_version = self.config_manager.get_me3_version()
        if not current_version:
            QMessageBox.warning(self.parent, "ME3 Not Installed", 
                               "ME3 is not installed. Please install it first before trying to update.")
            return

        self.progress_dialog = QProgressDialog("Running 'me3 update'...", None, 0, 0, self.parent)
        self.progress_dialog.setWindowTitle("Updating ME3 CLI")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)

        self.thread = QThread()
        self.worker = ME3Updater(self._prepare_command)
        self.worker.moveToThread(self.thread)
        self.worker.update_finished.connect(self._on_update_finished)
        self.thread.started.connect(self.worker.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def _on_update_finished(self, return_code: int, output: str):
        """Handle completion of ME3 update process."""
        self._cleanup_thread()
        
        clean_output = self._strip_ansi_codes(output)
        
        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()
        
        if return_code == 0:
            QMessageBox.information(self.parent, "Update Complete", 
                                  f"ME3 has been updated successfully.\n\n{clean_output}")
        else:
            QMessageBox.warning(self.parent, "Update Failed", 
                              f"The update command failed:\n\n{clean_output}")

    def download_windows_installer(self, release_type: str = 'latest'):
        """Download Windows ME3 installer."""
        if sys.platform != "win32":
            QMessageBox.warning(self.parent, "Platform Error", 
                              "Windows installer download is only available on Windows.")
            return

        version, download_url = self._fetch_github_release_info(release_type)
        if not download_url:
            QMessageBox.warning(self.parent, "Error", 
                              f"Could not fetch {release_type} release information from GitHub.")
            return

        downloads_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        save_path, _ = QFileDialog.getSaveFileName(
            self.parent, 
            "Save ME3 Installer", 
            os.path.join(downloads_path, "me3_installer.exe"), 
            "Executable Files (*.exe)"
        )
        
        if not save_path:
            return

        self.progress_dialog = QProgressDialog("Downloading me3_installer.exe...", "Cancel", 0, 100, self.parent)
        self.progress_dialog.setWindowTitle("Downloading")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self._cancel_download)
        
        self.thread = QThread()
        self.worker = ME3Downloader(download_url, save_path)
        self.worker.moveToThread(self.thread)
        self.worker.download_progress.connect(self.progress_dialog.setValue)
        self.worker.download_finished.connect(self._on_download_finished)
        self.thread.started.connect(self.worker.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def _cancel_download(self):
        """Cancel the current download."""
        if hasattr(self, 'worker') and isinstance(self.worker, ME3Downloader):
            self.worker.cancel()

    def _start_installation_monitoring(self):
        """Start monitoring for ME3 installation changes."""
        self.last_known_version = self.config_manager.get_me3_version()
        self.monitoring_installation = True
        self.installation_monitor_timer.start(2000)  # Check every 2 seconds
        print("Started monitoring ME3 installation...")
    
    def _stop_installation_monitoring(self):
        """Stop monitoring for ME3 installation changes."""
        self.installation_monitor_timer.stop()
        self.monitoring_installation = False
        print("Stopped monitoring ME3 installation.")
    
    def _check_installation_status(self):
        """Check if ME3 installation status has changed."""
        current_version = self.config_manager.get_me3_version()
        
        if current_version != self.last_known_version:
            print(f"ME3 version changed: {self.last_known_version} -> {current_version}")
            self._stop_installation_monitoring()
            self.refresh_callback()
            
            # Show success message if ME3 was newly installed
            if self.last_known_version is None and current_version is not None:
                QMessageBox.information(
                    self.parent,
                    "Installation Detected",
                    f"ME3 v{current_version} has been successfully installed!\nThe application has been refreshed."
                )
    
    def _on_download_finished(self, message: str, file_path: str):
        """Handle completion of ME3 installer download."""
        self._cleanup_thread()
        
        if "complete" in message.lower() and file_path:
            reply = QMessageBox.information(
                self.parent, 
                "Download Complete", 
                f"ME3 installer downloaded to:\n{file_path}\n\nWould you like to run it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._open_file_or_directory(file_path, run_file=True)
                # Start monitoring for installation completion
                self._start_installation_monitoring()
                
        elif "cancelled" not in message.lower():
            QMessageBox.critical(self.parent, "Download Failed", message)

    def custom_install_windows_me3(self, release_type: str = 'latest'):
        """Download and install ME3 portable distribution for Windows."""
        if sys.platform != "win32":
            QMessageBox.warning(self.parent, "Platform Error", 
                            "Custom Windows installer is only available on Windows.")
            return

        # Get the ZIP download URL
        version, zip_url = self._fetch_github_release_info_zip(release_type)
        if not zip_url:
            QMessageBox.warning(self.parent, "Error", 
                            f"Could not fetch {release_type} release information from GitHub.")
            return

        # Show installation path to user
        install_path = os.path.join(
            os.path.expanduser("~"), "AppData", "Local", "garyttierney", "me3", "bin"
        )

        # Confirm installation
        reply = QMessageBox.question(
            self.parent, 
            f"Install ME3 Custom ({version})",
            f"This will download and install ME3 {version} to:\n"
            f"{install_path}\n\n"
            f"The installation directory will be added to your user PATH.\n\n"
            f"Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Setup temporary file
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"me3-windows-amd64-{version}.zip")

        self.progress_dialog = QProgressDialog("Installing ME3 Custom Distribution...", "Cancel", 0, 100, self.parent)
        self.progress_dialog.setWindowTitle("Installing ME3")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self._cancel_custom_install)
        
        self.thread = QThread()
        self.worker = ME3CustomInstaller(zip_url, temp_path)
        self.worker.moveToThread(self.thread)
        self.worker.download_progress.connect(self.progress_dialog.setValue)
        self.worker.install_finished.connect(self._on_custom_install_finished)
        self.thread.started.connect(self.worker.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def _fetch_github_release_info_zip(self, release_type: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch GitHub release information for ZIP distribution.
        
        Args:
            release_type: 'latest' for stable release or 'prerelease' for pre-release
            
        Returns:
            Tuple of (version_tag, zip_download_url)
        """
        asset_name = 'me3-windows-amd64.zip'
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
                if release_data is None:
                    return None, None
            else:
                return None, None

            version_tag = release_data.get('tag_name')
            for asset in release_data.get('assets', []):
                if asset.get('name') == asset_name:
                    return version_tag, asset.get('browser_download_url')
                    
        except requests.RequestException:
            return None, None
            
        return None, None

    def _cancel_custom_install(self):
        """Cancel the current custom installation."""
        if hasattr(self, 'worker') and isinstance(self.worker, ME3CustomInstaller):
            self.worker.cancel()

    def _on_custom_install_finished(self, return_code: int, message: str):
        """Handle completion of custom ME3 installation."""
        self._cleanup_thread()
        
        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()
        
        if return_code == 0:
            QMessageBox.information(self.parent, "Installation Complete", message)
        else:
            QMessageBox.warning(self.parent, "Installation Failed", message)

    def install_linux_me3(self, release_type: str = 'latest', custom_installer_url: str = None):
        """Install or update ME3 on Linux/macOS using installer script."""
        if sys.platform == "win32":
            QMessageBox.warning(self.parent, "Platform Error", 
                              "Linux installer is not available on Windows. Use the Windows installer instead.")
            return

        if custom_installer_url:
            installer_url = custom_installer_url
            script_type = "custom"
        else:
            version, installer_url = self._fetch_github_release_info(release_type)
            script_type = release_type
            
        if not installer_url:
            QMessageBox.warning(self.parent, "Error", 
                              f"Could not fetch {script_type} installer URL from GitHub.")
            return

        reply = QMessageBox.question(
            self.parent, 
            f"Install ME3 ({script_type.title()})",
            f"This will run the {script_type} ME3 installer script.\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Prepare environment variables
        env_vars = {}
        latest_version = self._fetch_github_version_python()
        if latest_version:
            env_vars['VERSION'] = latest_version

        self.progress_dialog = QProgressDialog("Running ME3 installer script...", None, 0, 0, self.parent)
        self.progress_dialog.setWindowTitle("Installing ME3")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)

        self.thread = QThread()
        self.worker = ME3LinuxInstaller(installer_url, self._prepare_command, env_vars)
        self.worker.moveToThread(self.thread)
        self.worker.install_finished.connect(self._on_linux_install_finished)
        self.thread.started.connect(self.worker.run)
        
        self.thread.start()
        self.progress_dialog.show()

    def _on_linux_install_finished(self, return_code: int, output: str):
        """Handle completion of Linux ME3 installation."""
        self._cleanup_thread()

        clean_output = self._strip_ansi_codes(output)
        
        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()

        if return_code == 0:
            # Try to find the version from the script's output
            version_match = re.search(r"using latest version: (v[0-9]+\.[0-9]+\.[0-9]+)", clean_output)
            final_message = "Installation Complete"
            
            if version_match:
                installed_version = version_match.group(1)
                final_message += f"\n\nVersion Installed: {installed_version}"
            
            final_message += f"\n\n{clean_output}"
            
            QMessageBox.information(self.parent, "Installation Complete", final_message)
        else:
            QMessageBox.warning(self.parent, "Installation Failed", 
                              f"The installation script failed:\n\n{clean_output}")

    def _cleanup_thread(self):
        """Clean up thread and progress dialog."""
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        self.worker = None

    def get_available_versions(self) -> dict:
        """Get information about available ME3 versions."""
        stable_version, stable_url = self._fetch_github_release_info('latest')
        prerelease_version, prerelease_url = self._fetch_github_release_info('prerelease')
        
        return {
            'stable': {
                'version': stable_version,
                'url': stable_url,
                'available': bool(stable_url)
            },
            'prerelease': {
                'version': prerelease_version,
                'url': prerelease_url,
                'available': bool(prerelease_url)
            }
        }

    def check_for_updates(self) -> dict:
        """Check if updates are available for the current ME3 installation."""
        current_version = self.config_manager.get_me3_version()
        if not current_version:
            return {'installed': False, 'current_version': None}
            
        available_versions = self.get_available_versions()
        
        # Don't add 'v' prefix since current_version already has it
        current_version_tag = current_version if current_version.startswith('v') else f"v{current_version}"
        
        return {
            'installed': True,
            'current_version': current_version_tag,
            'stable_available': available_versions['stable']['available'],
            'stable_version': available_versions['stable']['version'],
            'prerelease_available': available_versions['prerelease']['available'],
            'prerelease_version': available_versions['prerelease']['version'],
            'has_stable_update': (
                available_versions['stable']['available'] and 
                available_versions['stable']['version'] != current_version_tag
            ),
            'has_prerelease_update': (
                available_versions['prerelease']['available'] and 
                available_versions['prerelease']['version'] != current_version_tag
            )
        }
    
class ME3CustomInstaller(QObject):
    """Handles downloading and installing ME3 portable distribution for Windows."""
    download_progress = pyqtSignal(int)
    install_finished = pyqtSignal(int, str)  # return_code, message

    def __init__(self, url: str, temp_path: str):
        super().__init__()
        self.url = url
        self.temp_path = temp_path
        # UPDATED: Use garyttierney path to match official installer structure
        self.install_path = os.path.join(
            os.path.expanduser("~"), "AppData", "Local", "garyttierney", "me3", "bin"
        )
        self._is_cancelled = False

    def run(self):
        try:
            # Step 1: Download the ZIP file
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            
            with open(self.temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        self.install_finished.emit(-1, "Download cancelled.")
                        return
                    if chunk:
                        bytes_downloaded += len(chunk)
                        f.write(chunk)
                        if total_size > 0:
                            progress = int((bytes_downloaded / total_size) * 50)  # First 50% for download
                            self.download_progress.emit(progress)
            
            # Step 2: Extract and install
            self.download_progress.emit(50)  # Download complete
            
            # Create installation directory
            os.makedirs(self.install_path, exist_ok=True)
            
            # Extract ZIP file
            with zipfile.ZipFile(self.temp_path, 'r') as zip_ref:
                # First, let's see what's actually in the archive
                all_files = zip_ref.namelist()
                
                # Look for bin folder in various possible structures
                bin_files = []
                bin_folder_path = None
                
                # Check different possible patterns
                for file_path in all_files:
                    normalized_path = file_path.replace('\\', '/')
                    path_parts = normalized_path.split('/')
                    
                    # Look for 'bin' folder at any level
                    if 'bin' in path_parts:
                        bin_index = path_parts.index('bin')
                        # Check if this is a file inside the bin folder (not the folder itself)
                        if bin_index < len(path_parts) - 1 and path_parts[bin_index + 1]:
                            bin_files.append(file_path)
                            if bin_folder_path is None:
                                # Remember the path structure up to 'bin'
                                bin_folder_path = '/'.join(path_parts[:bin_index + 1])
                
                # If no bin folder found, look for the target executables directly
                if not bin_files:
                    target_files = ['me3.exe', 'me3_mod_host.dll', 'me3-launcher.exe']
                    for file_path in all_files:
                        filename = os.path.basename(file_path)
                        if filename in target_files:
                            bin_files.append(file_path)
                
                if not bin_files:
                    # Debug: show what files we found
                    files_list = '\n'.join(all_files[:10])  # Show first 10 files
                    if len(all_files) > 10:
                        files_list += f'\n... and {len(all_files) - 10} more files'
                    
                    self.install_finished.emit(-2, 
                        f"Could not find ME3 executables in the downloaded archive.\n\n"
                        f"Archive contains {len(all_files)} files:\n{files_list}")
                    return
                
                # Extract the found files
                extracted_count = 0
                for file_path in bin_files:
                    try:
                        # Get just the filename for the target
                        filename = os.path.basename(file_path)
                        if filename:  # Skip directories
                            target_path = os.path.join(self.install_path, filename)
                            with zip_ref.open(file_path) as source, open(target_path, 'wb') as target:
                                target.write(source.read())
                                extracted_count += 1
                    except Exception as e:
                        print(f"Warning: Failed to extract {file_path}: {e}")
                        continue
                
                if extracted_count == 0:
                    self.install_finished.emit(-2, "Failed to extract any files from the archive.")
                    return
            
            self.download_progress.emit(75)  # Extraction complete
            
            # Step 3: Add to user PATH (no admin required)
            if self._add_to_user_path(self.install_path):
                self.download_progress.emit(90)  # PATH update complete
                
                # Step 4: Refresh environment variables
                self._refresh_environment()
                self.download_progress.emit(100)  # Complete
                
                # Clean up temp file
                try:
                    os.remove(self.temp_path)
                except:
                    pass
                
                self.install_finished.emit(0, f"ME3 has been successfully installed to:\n{self.install_path}\n\nThe installation directory has been added to your user PATH.")
            else:
                self.install_finished.emit(-3, "Installation completed but failed to add to user PATH environment variable.")
                
        except zipfile.BadZipFile:
            self.install_finished.emit(-2, "Downloaded file is not a valid ZIP archive.")
        except requests.RequestException as e:
            self.install_finished.emit(-1, f"Network error: {e}")
        except Exception as e:
            self.install_finished.emit(-3, f"An error occurred: {e}")

    def _add_to_user_path(self, new_path: str) -> bool:
        """Add the installation path to the user PATH environment variable."""
        try:
            # Open the user Environment subkey in the registry
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                            r"Environment",
                            0, winreg.KEY_ALL_ACCESS) as key:
                
                # Get current PATH value
                try:
                    current_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current_path = ""
                
                # Split PATH into individual paths and clean them up
                paths = [p.strip() for p in current_path.split(';') if p.strip()]
                
                # UPDATED: Remove any existing ME3 paths (both old and new patterns)
                cleaned_paths = []
                for path in paths:
                    # Normalize path separators and check if it ends with me3\bin or garyttierney\me3\bin
                    normalized_path = path.replace('/', '\\').rstrip('\\').lower()
                    if not (normalized_path.endswith('\\me3\\bin') or 
                           normalized_path.endswith('\\garyttierney\\me3\\bin')):
                        cleaned_paths.append(path)
                    else:
                        print(f"Removed existing ME3 path from user PATH: {path}")
                
                # Add the new path if it's not already there
                if new_path not in cleaned_paths:
                    cleaned_paths.append(new_path)
                    print(f"Added new ME3 path to user PATH: {new_path}")
                
                # Set the new PATH value
                new_path_value = ';'.join(cleaned_paths)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path_value)
                return True
                    
        except Exception as e:
            print(f"Error updating user PATH: {e}")
            return False

    def _refresh_environment(self):
        """Refresh environment variables without requiring logout/restart."""
        try:
            # Broadcast WM_SETTINGCHANGE message to all windows
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            
            result = ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                "Environment",
                2,  # SMTO_ABORTIFHUNG
                5000,  # 5 second timeout
                None
            )
            
            if result == 0:
                print("Warning: Failed to broadcast environment variable changes")
            else:
                print("Successfully broadcasted environment variable changes")
            
            # IMPORTANT: Also refresh the current process's environment
            self._refresh_current_process_path()
                
        except Exception as e:
            print(f"Warning: Could not refresh environment variables: {e}")

    def _refresh_current_process_path(self):
        """Refresh the PATH environment variable for the current process."""
        try:
            # Read the updated user PATH from registry
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ) as key:
                try:
                    user_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    user_path = ""
            
            # Get system PATH
            system_path = os.environ.get('PATH', '')
            
            # UPDATED: Clean the current process PATH of old ME3 entries (both patterns)
            current_process_paths = [p.strip() for p in system_path.split(';') if p.strip()]
            cleaned_system_paths = []
            for path in current_process_paths:
                normalized_path = path.replace('/', '\\').rstrip('\\').lower()
                if not (normalized_path.endswith('\\me3\\bin') or 
                       normalized_path.endswith('\\garyttierney\\me3\\bin')):
                    cleaned_system_paths.append(path)
            
            # Combine user PATH with cleaned system PATH (user PATH takes precedence)
            if user_path:
                new_path = user_path + ';' + ';'.join(cleaned_system_paths)
            else:
                new_path = ';'.join(cleaned_system_paths)
            
            # Update the current process's PATH
            os.environ['PATH'] = new_path
            print(f"Updated current process PATH, ME3 installation: {self.install_path}")
            
        except Exception as e:
            print(f"Warning: Could not refresh current process PATH: {e}")


    def cancel(self):
        self._is_cancelled = True