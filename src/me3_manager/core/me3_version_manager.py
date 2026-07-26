import ctypes
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests
from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QMessageBox, QProgressDialog

from me3_manager.services.me3_service import Me3Service
from me3_manager.utils.command_runner import CommandRunner
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.status import Status
from me3_manager.utils.translator import tr

if sys.platform == "win32":
    import winreg

log = logging.getLogger(__name__)


def _download_file(
    url: str,
    save_path: str,
    progress_callback: Callable[[int], None],
    is_cancelled_callback: Callable[[], bool],
    cancel_action: Callable[[], None],
    progress_scale: float = 1.0,
) -> bool:
    """Helper to download a file with progress updates and cancellation check."""
    response = requests.get(url, stream=True, timeout=15)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))
    bytes_downloaded = 0

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if is_cancelled_callback():
                cancel_action()
                return False
            if chunk:
                bytes_downloaded += len(chunk)
                f.write(chunk)
                if total_size > 0:
                    progress = int(
                        (bytes_downloaded / total_size) * 100 * progress_scale
                    )
                    progress_callback(progress)
    return True


class ME3Downloader(QObject):
    """Handles downloading ME3 installer files in a separate thread (for Windows)."""

    download_progress = Signal(int)
    download_finished = Signal(int, str, str)  # status_code, message, file_path

    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self._is_cancelled = False

    def run(self):
        try:

            def cancel_action():
                self.download_finished.emit(
                    Status.CANCELLED, tr("download_cancelled"), ""
                )

            success = _download_file(
                self.url,
                self.save_path,
                self.download_progress.emit,
                lambda: self._is_cancelled,
                cancel_action,
                1.0,
            )

            if not success:
                return

            self.download_finished.emit(
                Status.SUCCESS, tr("download_complete"), self.save_path
            )
        except requests.RequestException as e:
            self.download_finished.emit(
                Status.NETWORK_ERROR, tr("NETWORK_ERROR", e=e), ""
            )
        except Exception as e:
            self.download_finished.emit(Status.FAILED, tr("ERROR_OCCURRED", e=e), "")

    def cancel(self):
        self._is_cancelled = True


class ME3Updater(QObject):
    """Runs 'me3 update' command in a separate thread to prevent UI freezing."""

    update_finished = Signal(int, int, str)  # status_code, return_code, output

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
            returncode, stdout, stderr = CommandRunner.run(
                cmd, timeout=120, capture_output=True, text=True
            )

            output = ((stdout or "").strip() + "\n" + (stderr or "").strip()).strip()
            status_code = Status.SUCCESS if returncode == 0 else Status.FAILED
            self.update_finished.emit(status_code, returncode, output)

        except FileNotFoundError:
            self.update_finished.emit(
                Status.NOT_INSTALLED, -1, tr("me3_command_not_found")
            )
        except subprocess.TimeoutExpired:
            self.update_finished.emit(
                Status.TIMEOUT, -2, tr("update_process_timeout", minutes="2")
            )
        except Exception as e:
            self.update_finished.emit(
                Status.FAILED, -3, tr("UNEXPECTED_ERROR_OCCURRED", e=e)
            )


class ME3LinuxInstaller(QObject):
    """Runs ME3 installer script in a separate thread for Linux."""

    install_finished = Signal(int, int, str)  # status_code, return_code, output

    def __init__(
        self,
        installer_url: str,
        prepare_command_func: Callable[[list], list],
        env_vars: dict = None,
    ):
        super().__init__()
        self.installer_url = installer_url
        self._prepare_command = prepare_command_func
        self.env_vars = env_vars or {}

    def run(self):
        """Executes the installer script by piping curl's output to a shell."""
        try:
            # Start with the current environment
            env = os.environ.copy()
            # Set required vars and merge any custom ones (like VERSION)
            env["ME3_QUIET"] = "no"
            env.update(self.env_vars)

            command_string = (
                f"curl --proto '=https' --tlsv1.2 -sSfL {self.installer_url} | sh"
            )
            is_flatpak = sys.platform == "linux" and os.environ.get("FLATPAK_ID")

            if is_flatpak:
                # Ensure LD_LIBRARY_PATH does not interfere with host shell/libs
                cmd = [
                    "flatpak-spawn",
                    "--host",
                    "env",
                    "-u",
                    "LD_LIBRARY_PATH",
                    "sh",
                    "-c",
                    command_string,
                ]
                use_shell = False
            else:
                # Explicitly unset LD_LIBRARY_PATH for the child shell and pipeline
                cmd = [
                    "env",
                    "-u",
                    "LD_LIBRARY_PATH",
                    "sh",
                    "-c",
                    command_string,
                ]
                use_shell = False

            returncode, stdout, stderr = CommandRunner.run(
                cmd, shell=use_shell, timeout=150, env=env
            )

            out_s = (stdout or "").strip()
            err_s = (stderr or "").strip()
            output = (out_s + "\n" + err_s).strip()
            status_code = Status.SUCCESS if returncode == 0 else Status.FAILED
            self.install_finished.emit(status_code, returncode, output)

        except subprocess.TimeoutExpired:
            self.install_finished.emit(
                Status.TIMEOUT, -2, tr("update_process_timeout", minutes="2.5")
            )
        except Exception as e:
            self.install_finished.emit(
                Status.FAILED, -3, tr("UNEXPECTED_ERROR_OCCURRED", e=e)
            )


class ME3VersionManager(QObject):
    """
    Centralized manager for ME3 version checking, updating, and installation.
    Handles both Windows and Linux platforms.
    """

    def __init__(
        self,
        parent_widget,
        config_manager,
        path_manager,
        refresh_callback: Callable[[], None],
    ):
        super().__init__(parent_widget)
        self.parent = parent_widget
        self.config_manager = config_manager
        self.path_manager = path_manager
        self.refresh_callback = refresh_callback
        self.me3_service = Me3Service()
        self.progress_dialog = None
        self.thread = None
        self.worker = None
        self.installation_monitor_timer = QTimer()
        self.installation_monitor_timer.timeout.connect(self._check_installation_status)
        self.monitoring_installation = False
        self.last_known_version = None

    def _create_progress_dialog(
        self, title: str, text: str, cancellable: bool = False, maximum: int = 0
    ) -> QProgressDialog:
        """Helper to create a standard progress dialog."""
        cancel_text = tr("CANCEL") if cancellable else None
        dialog = QProgressDialog(text, cancel_text, 0, maximum, self.parent)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        if not cancellable:
            dialog.setCancelButton(None)
        return dialog

    def _confirm_action_with_checkbox(
        self,
        title: str,
        text: str,
        checkbox_text: str,
        default_button=QMessageBox.StandardButton.Yes,
    ) -> tuple[bool, bool]:
        """Show a Yes/No confirmation dialog with an optional checkbox."""
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(default_button)
        checkbox = QCheckBox(checkbox_text)
        checkbox.setChecked(False)
        msg_box.setCheckBox(checkbox)
        return msg_box.exec() == QMessageBox.StandardButton.Yes, checkbox.isChecked()

    def _prepare_command(self, cmd: list) -> list:
        """Enhanced command preparation with better environment handling."""
        return PlatformUtils.prepare_command(cmd)

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text."""
        return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])").sub("", text)

    def _fetch_github_version_python(self) -> str | None:
        """Uses Python's requests to fetch the latest ME3 release version from GitHub."""
        api_url = "https://api.github.com/repos/garyttierney/me3/releases/latest"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            version = data.get("tag_name")
            if version and version.startswith("v"):
                log.debug("Fetched version from GitHub API: %s", version)
                return version
        except requests.RequestException as e:
            log.error("Python-based GitHub API request failed: %s", e)
            return None
        return None

    @staticmethod
    def _default_asset_name(asset_name: str | None) -> str:
        """Return the platform-appropriate asset name when none is given."""
        if asset_name is not None:
            return asset_name
        return "me3_installer.exe" if sys.platform == "win32" else "installer.sh"

    def _fetch_github_release_info(
        self, asset_name: str | None = None
    ) -> tuple[str | None, str | None]:
        """Fetch latest stable GitHub release information via service.

        Args:
            asset_name: Override asset name. If None, auto-detects based on platform.
        """
        asset_name = self._default_asset_name(asset_name)
        release = self.me3_service.fetch_latest_release()
        version_tag = self.me3_service.get_latest_version_tag(release)
        url = self.me3_service.get_asset_url(release, asset_name)
        return version_tag, url

    def _fetch_github_release_info_for_version(
        self, version_tag: str, asset_name: str | None = None
    ) -> tuple[str | None, str | None]:
        """Fetch release info for a specific version tag.

        Args:
            version_tag: The version tag to fetch (e.g. 'v0.12.1').
            asset_name: Override asset name. If None, auto-detects based on platform.
        """
        asset_name = self._default_asset_name(asset_name)
        release = self.me3_service.fetch_release_by_tag(version_tag)
        tag = self.me3_service.get_latest_version_tag(release)
        url = self.me3_service.get_asset_url(release, asset_name)
        return tag, url

    def _open_file_or_directory(self, path: str, run_file: bool = False):
        """Open a file or directory using the system's default application."""
        try:
            if not PlatformUtils.open_path(path, run_file=run_file):
                QMessageBox.warning(
                    self.parent,
                    tr("ERROR"),
                    tr(
                        "could_not_perform_action", e="Desktop service rejected request"
                    ),
                )
        except Exception as e:
            QMessageBox.warning(
                self.parent, tr("ERROR"), tr("could_not_perform_action", e=e)
            )

    def _is_portable_install(self) -> bool:
        """Detect if the current ME3 install is the custom portable distribution install."""
        try:
            bin_dir = self.path_manager.get_me3_binary_path()
            exe_name = "me3.exe" if sys.platform == "win32" else "me3"
            exe_path = bin_dir / exe_name
            if exe_path.is_file():
                if sys.platform == "win32" or os.access(exe_path, os.X_OK):
                    return True

            me3_path = shutil.which("me3")
            if me3_path:
                me3_path_norm = str(Path(me3_path).resolve()).replace("\\", "/").lower()
                bin_dir_norm = str(bin_dir.resolve()).replace("\\", "/").lower()
                if me3_path_norm.startswith(bin_dir_norm + "/"):
                    return True

            # Fallback check: compare installation prefix to expected me3 root
            me3_info = getattr(self.path_manager, "me3_info", None)
            if me3_info:
                install_prefix = me3_info.get_installation_prefix()
                if install_prefix:
                    from me3_manager.core.paths.profile_paths import get_me3_root

                    me3_root = get_me3_root(self.path_manager.config_root)
                    if str(install_prefix).replace("/", "\\").lower().rstrip(
                        "\\"
                    ) == str(me3_root).replace("/", "\\").lower().rstrip("\\"):
                        return True
        except Exception:
            return False

        return False

    def _is_portable_install_windows(self) -> bool:
        """Alias for backwards compatibility."""
        return self._is_portable_install()

    def install_specific_version(self, version_tag: str):
        """Install a specific ME3 version (upgrade or downgrade).

        Routes through the appropriate platform-specific installation
        method with the chosen version's download URL.
        """
        current_version = self.config_manager.get_me3_version()
        current_tag = (
            f"v{current_version}"
            if current_version and not current_version.startswith("v")
            else current_version
        )

        # Confirm the version change with the user
        reply = QMessageBox.question(
            self.parent,
            tr("confirm_version_change_title"),
            tr(
                "confirm_version_change",
                version=version_tag,
                current_version=current_tag or tr("not_installed"),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Kill any running me3 processes before replacing binaries
        self.kill_me3_processes()

        if self._is_portable_install():
            self.custom_install_me3(version_tag=version_tag)
        elif sys.platform == "win32":
            self.download_windows_installer(version_tag=version_tag)
        else:
            self.install_linux_me3(version_tag=version_tag)

    def update_me3_cli(self):
        """Update ME3 CLI using 'me3 update' command."""
        current_version = self.config_manager.get_me3_version()
        if not current_version:
            QMessageBox.warning(
                self.parent, tr("me3_not_installed"), tr("me3_not_installed_warning")
            )
            return

        # If using portable custom install, update via custom distribution replacement
        if self._is_portable_install():
            self.custom_install_me3()
            return

        self.progress_dialog = self._create_progress_dialog(
            title=tr("me3_update_title"),
            text=tr("me3_update_process"),
            cancellable=False,
            maximum=0,
        )

        self._start_worker(ME3Updater(self._prepare_command), self._on_update_finished)

    def _on_update_finished(self, status_code: int, return_code: int, output: str):
        """Handle completion of ME3 update process."""
        self._cleanup_thread()

        clean_output = self._strip_ansi_codes(output)

        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()

        if status_code == Status.SUCCESS:
            QMessageBox.information(
                self.parent,
                tr("update_complete"),
                tr("update_complete_text", clean_output=clean_output),
            )
        elif status_code == Status.NOT_INSTALLED:
            QMessageBox.warning(
                self.parent,
                tr("me3_not_installed"),
                clean_output,
            )
        elif status_code == Status.TIMEOUT:
            QMessageBox.warning(
                self.parent,
                tr("update_timeout"),
                clean_output,
            )
        else:
            QMessageBox.warning(
                self.parent,
                tr("update_failed"),
                tr("update_failed_text", clean_output=clean_output),
            )

    def download_windows_installer(self, version_tag: str | None = None):
        """Download Windows ME3 installer.

        Args:
            version_tag: If provided, download this specific version instead of latest.
        """
        if sys.platform != "win32":
            QMessageBox.warning(
                self.parent, tr("platform_error"), tr("platform_error_text_win")
            )
            return

        if version_tag:
            version, download_url = self._fetch_github_release_info_for_version(
                version_tag
            )
        else:
            version, download_url = self._fetch_github_release_info()
        if not download_url:
            QMessageBox.warning(
                self.parent,
                tr("ERROR"),
                "Could not fetch latest release information from GitHub.",
            )
            return

        downloads_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        save_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            tr("save_me3_installer"),
            os.path.join(downloads_path, "me3_installer.exe"),
            "Executable Files (*.exe)",
        )

        if not save_path:
            return

        self.progress_dialog = self._create_progress_dialog(
            title=tr("DOWNLOADING"),
            text=tr("downloading_me3_installer"),
            cancellable=True,
            maximum=100,
        )
        self.progress_dialog.canceled.connect(self._cancel_download)

        self._start_worker(
            ME3Downloader(download_url, save_path),
            self._on_download_finished,
            self.progress_dialog.setValue,
        )

    def _cancel_download(self):
        """Cancel the current download."""
        if hasattr(self, "worker") and isinstance(self.worker, ME3Downloader):
            self.worker.cancel()

    def _start_installation_monitoring(self):
        """Start monitoring for ME3 installation changes."""
        self.last_known_version = self.config_manager.get_me3_version()
        self.monitoring_installation = True
        self.installation_monitor_timer.start(2000)  # Check every 2 seconds
        log.debug("Started monitoring ME3 installation...")

    def _stop_installation_monitoring(self):
        """Stop monitoring for ME3 installation changes."""
        self.installation_monitor_timer.stop()
        self.monitoring_installation = False
        log.debug("Stopped monitoring ME3 installation.")

    def _check_installation_status(self):
        """Check if ME3 installation status has changed."""
        current_version = self.config_manager.get_me3_version()

        if current_version != self.last_known_version:
            log.info(
                "ME3 version changed: %s -> %s",
                self.last_known_version,
                current_version,
            )
            self._stop_installation_monitoring()
            if hasattr(self.path_manager, "refresh_config_root"):
                self.path_manager.refresh_config_root()
            if hasattr(self.path_manager, "ensure_directories"):
                self.path_manager.ensure_directories()
            self.refresh_callback()

            # Show success message if ME3 was newly installed
            if self.last_known_version is None and current_version is not None:
                QMessageBox.information(
                    self.parent,
                    tr("installation_detected"),
                    tr("installation_detected_text", current_version=current_version),
                )

    def _on_download_finished(self, status_code: int, message: str, file_path: str):
        """Handle completion of ME3 installer download."""
        self._cleanup_thread()

        if status_code == Status.SUCCESS and file_path:
            reply = QMessageBox.information(
                self.parent,
                tr("download_complete"),
                tr("download_complete_text", file_path=file_path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._open_file_or_directory(file_path, run_file=True)
                # Start monitoring for installation completion
                self._start_installation_monitoring()

        elif status_code == Status.CANCELLED:
            # Don't show error for cancelled downloads
            pass
        elif status_code == Status.NETWORK_ERROR:
            QMessageBox.critical(self.parent, tr("network_error"), message)
        else:
            QMessageBox.critical(self.parent, tr("download_failed"), message)

    def custom_install_windows_me3(self):
        """Backwards compatibility wrapper for custom_install_me3."""
        self.custom_install_me3()

    def custom_install_me3(
        self, target_dir: str | Path | None = None, version_tag: str | None = None
    ):
        """Download and install ME3 portable distribution for Windows or Linux.

        Args:
            target_dir: Override the installation directory.
            version_tag: If provided, install this specific version instead of latest.
        """
        if sys.platform not in ("win32", "linux"):
            QMessageBox.warning(
                self.parent,
                tr("platform_error"),
                "Portable custom install is only supported on Windows and Linux.",
            )
            return

        asset_name = (
            "me3-windows-amd64.zip"
            if sys.platform == "win32"
            else "me3-linux-amd64.tar.gz"
        )

        # Get the archive download URL (specific version or latest)
        if version_tag:
            version, download_url = self._fetch_github_release_info_for_version(
                version_tag, asset_name
            )
        else:
            version, download_url = self._fetch_github_release_info(asset_name)
        if not download_url:
            QMessageBox.warning(
                self.parent,
                tr("ERROR"),
                f"Could not fetch latest release information ({asset_name}) from GitHub.",
            )
            return

        from me3_manager.core.paths.profile_paths import get_custom_me3_location

        existing_custom = get_custom_me3_location()
        if target_dir:
            selected_dir = str(target_dir)
        elif existing_custom:
            selected_dir = str(existing_custom)
        else:
            # Prompt user to choose a custom location for ME3 installation and mods
            default_base_dir = self.path_manager.config_root.parent.parent
            selected_dir = QFileDialog.getExistingDirectory(
                self.parent,
                tr("select_me3_install_directory"),
                str(default_base_dir),
            )
            if not selected_dir:
                return

        # Persist custom location in manager_settings.json
        try:
            if (
                hasattr(self.path_manager, "settings_manager")
                and self.path_manager.settings_manager
            ):
                self.path_manager.settings_manager.set(
                    "custom_me3_location", selected_dir
                )
            else:
                import json

                from me3_manager.core.paths.profile_paths import (
                    get_manager_settings_path,
                )

                settings_path = get_manager_settings_path()
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                data = {}
                if settings_path.exists():
                    try:
                        with open(settings_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        pass
                data["custom_me3_location"] = selected_dir
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
        except Exception as e:
            log.warning("Failed to save custom_me3_location: %s", e)

        # Refresh path manager to adopt the new custom root and generate mod directories
        if hasattr(self.path_manager, "refresh_config_root"):
            self.path_manager.refresh_config_root()
        if hasattr(self.path_manager, "ensure_directories"):
            self.path_manager.ensure_directories()

        # Get installation path from selected custom location
        install_path = Path(selected_dir) / "bin"
        install_path.mkdir(parents=True, exist_ok=True)

        # Confirm installation
        title_key = (
            "custom_installer_question_title_win"
            if sys.platform == "win32"
            else "custom_installer_question_title"
        )
        question_key = (
            "custom_installer_question_win"
            if sys.platform == "win32"
            else "custom_installer_question"
        )

        title_str = tr(title_key, version=version)
        if title_str == title_key:
            title_str = tr("custom_installer_question_title_win", version=version)

        question_str = tr(question_key, version=version, install_path=str(install_path))
        if question_str == question_key:
            question_str = tr(
                "custom_installer_question_win",
                version=version,
                install_path=str(install_path),
            )

        confirmed, add_to_path = self._confirm_action_with_checkbox(
            title_str,
            question_str,
            tr("add_to_path_checkbox"),
            default_button=QMessageBox.StandardButton.Yes,
        )
        if not confirmed:
            return

        # Setup temporary file
        import tempfile

        temp_dir = tempfile.gettempdir()
        ext = ".zip" if sys.platform == "win32" else ".tar.gz"
        temp_path = os.path.join(temp_dir, f"me3-portable-{version}{ext}")

        self.progress_dialog = self._create_progress_dialog(
            title=tr("installing_me3"),
            text=tr("installing_me3_custom_distribution"),
            cancellable=True,
            maximum=100,
        )
        self.progress_dialog.canceled.connect(self._cancel_custom_install)

        self._start_worker(
            ME3CustomInstaller(
                download_url,
                temp_path,
                self.path_manager,
                add_to_path=add_to_path,
                install_path=install_path,
            ),
            self._on_custom_install_finished,
            self.progress_dialog.setValue,
        )

    def _cancel_custom_install(self):
        """Cancel the current custom installation."""
        if hasattr(self, "worker") and isinstance(self.worker, ME3CustomInstaller):
            self.worker.cancel()

    def _on_custom_install_finished(
        self, status_code: int, return_code: int, message: str
    ):
        """Handle completion of custom ME3 installation."""
        self._cleanup_thread()
        if hasattr(self.path_manager, "refresh_config_root"):
            self.path_manager.refresh_config_root()
        if hasattr(self.path_manager, "ensure_directories"):
            self.path_manager.ensure_directories()
        if hasattr(self.config_manager, "setup_file_watcher"):
            self.config_manager.setup_file_watcher()

        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()

        if status_code == Status.SUCCESS:
            # Check if ME3 is actually detected (PATH update might require restart)
            me3_version = self.config_manager.get_me3_version()
            bin_dir = self.path_manager.get_me3_binary_path()
            exe_path = bin_dir / ("me3.exe" if sys.platform == "win32" else "me3")

            if me3_version or exe_path.exists():
                QMessageBox.information(
                    self.parent, tr("installation_complete"), message
                )
            else:
                # Installation successful but me3 command not found -> Restart required
                QMessageBox.warning(
                    self.parent,
                    tr("installation_restart_required_title"),
                    tr(
                        "installation_restart_required_body",
                        install_path=self.path_manager.get_me3_binary_path(),
                    ),
                )
        elif status_code == Status.CANCELLED:
            # Don't show error for cancelled installations
            pass
        elif status_code == Status.NETWORK_ERROR:
            QMessageBox.warning(self.parent, tr("network_error"), message)
        elif status_code == Status.PERMISSION_ERROR:
            QMessageBox.warning(self.parent, tr("permission_error"), message)
        elif status_code == Status.INVALID_DATA:
            QMessageBox.warning(self.parent, tr("invalid_data_error"), message)
        else:
            QMessageBox.warning(self.parent, tr("installation_failed"), message)

    def install_linux_me3(
        self, custom_installer_url: str = None, version_tag: str | None = None
    ):
        """Install or update ME3 on Linux using installer script.

        Args:
            custom_installer_url: Override the installer script URL.
            version_tag: If provided, install this specific version instead of latest.
        """
        if sys.platform == "win32":
            QMessageBox.warning(
                self.parent, tr("platform_error"), tr("platform_error_text_linux")
            )
            return

        if custom_installer_url:
            installer_url = custom_installer_url
            script_type = "custom"
        elif version_tag:
            version, installer_url = self._fetch_github_release_info_for_version(
                version_tag
            )
            script_type = version_tag
        else:
            version, installer_url = self._fetch_github_release_info()
            script_type = "latest"

        if not installer_url:
            QMessageBox.warning(
                self.parent,
                tr("ERROR"),
                f"Could not fetch {script_type} installer URL from GitHub.",
            )
            return

        reply = QMessageBox.question(
            self.parent,
            tr("linux_installer_question_title", script_type=script_type),
            tr("linux_installer_question_linux", script_type=script_type),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Prepare environment variables
        env_vars = {}
        if version_tag:
            env_vars["VERSION"] = version_tag
        else:
            latest_version = self._fetch_github_version_python()
            if latest_version:
                env_vars["VERSION"] = latest_version

        self.progress_dialog = self._create_progress_dialog(
            title=tr("installing_me3"),
            text=tr("running_me3_installer"),
            cancellable=False,
            maximum=0,
        )

        self._start_worker(
            ME3LinuxInstaller(installer_url, self._prepare_command, env_vars),
            self._on_linux_install_finished,
        )

    def _on_linux_install_finished(
        self, status_code: int, return_code: int, output: str
    ):
        """Handle completion of Linux ME3 installation."""
        self._cleanup_thread()

        clean_output = self._strip_ansi_codes(output)

        # Refresh ME3 status and trigger app refresh
        self.refresh_callback()

        if status_code == Status.SUCCESS:
            # Try to find the version from the script's output
            version_match = re.search(
                r"using latest version: (v[0-9]+\.[0-9]+\.[0-9]+)", clean_output
            )
            final_message = tr("installation_complete")

            if version_match:
                installed_version = version_match.group(1)
                final_message += tr(
                    "version_installed", installed_version=installed_version
                )

            final_message += f"\n\n{clean_output}"

            QMessageBox.information(
                self.parent, tr("installation_complete"), final_message
            )
        elif status_code == Status.TIMEOUT:
            QMessageBox.warning(
                self.parent,
                tr("installation_timeout"),
                clean_output,
            )
        else:
            QMessageBox.warning(
                self.parent,
                tr("installation_failed"),
                tr("install_script_failed", clean_output=clean_output),
            )

    def _start_worker(self, worker, finish_slot, progress_slot=None):
        self.thread = QThread()
        self.worker = worker
        self.worker.moveToThread(self.thread)
        if progress_slot and hasattr(self.worker, "download_progress"):
            self.worker.download_progress.connect(progress_slot)

        # Connect to the appropriate finish signal
        if hasattr(self.worker, "update_finished"):
            self.worker.update_finished.connect(finish_slot)
        elif hasattr(self.worker, "download_finished"):
            self.worker.download_finished.connect(finish_slot)
        elif hasattr(self.worker, "install_finished"):
            self.worker.install_finished.connect(finish_slot)

        self.thread.started.connect(self.worker.run)
        self.thread.start()
        self.progress_dialog.show()

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
        stable_version, stable_url = self._fetch_github_release_info()

        return {
            "stable": {
                "version": stable_version,
                "url": stable_url,
                "available": bool(stable_url),
            },
        }

    def check_for_updates(self) -> dict:
        """Check if updates are available for the current ME3 installation."""
        current_version = self.config_manager.get_me3_version()
        if not current_version:
            return {"installed": False, "current_version": None}

        available_versions = self.get_available_versions()

        # Don't add 'v' prefix since current_version already has it
        current_version_tag = (
            current_version
            if current_version.startswith("v")
            else f"v{current_version}"
        )

        return {
            "installed": True,
            "current_version": current_version_tag,
            "stable_available": available_versions["stable"]["available"],
            "stable_version": available_versions["stable"]["version"],
            "has_stable_update": (
                available_versions["stable"]["available"]
                and available_versions["stable"]["version"] != current_version_tag
            ),
        }

    def _remove_me3_from_user_path(self, paths_to_remove: list[str] | None = None):
        """Remove ME3 installation paths from user PATH (Registry on Windows, shell profiles on Linux)."""
        norm_remove = set()
        if paths_to_remove:
            for p in paths_to_remove:
                if p:
                    norm_remove.add(os.path.normpath(p).lower())
                    norm_remove.add(os.path.normpath(os.path.join(p, "bin")).lower())

        if sys.platform == "win32":
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS
                ) as key:
                    try:
                        current_path, _ = winreg.QueryValueEx(key, "Path")
                    except FileNotFoundError:
                        current_path = ""

                    paths = [p.strip() for p in current_path.split(";") if p.strip()]
                    cleaned_paths = []
                    for path in paths:
                        norm = os.path.normpath(path).lower()
                        if (
                            norm.endswith(("\\me3\\bin", "\\garyttierney\\me3\\bin"))
                            or norm in norm_remove
                        ):
                            log.info(
                                "Removing ME3 path from Windows user PATH: %s", path
                            )
                        else:
                            cleaned_paths.append(path)

                    new_path_value = ";".join(cleaned_paths)
                    winreg.SetValueEx(
                        key, "Path", 0, winreg.REG_EXPAND_SZ, new_path_value
                    )

                # Broadcast environment update
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x001A
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 2, 5000, None
                )
            except Exception as e:
                log.warning("Error updating registry PATH during uninstall: %s", e)

            # Update current process PATH environment variable
            try:
                curr = os.environ.get("PATH", "").split(";")
                cleaned = []
                for p in curr:
                    norm = os.path.normpath(p).lower()
                    if not (
                        norm.endswith(("\\me3\\bin", "\\garyttierney\\me3\\bin"))
                        or norm in norm_remove
                    ):
                        cleaned.append(p)
                os.environ["PATH"] = ";".join(cleaned)
            except Exception as e:
                log.warning("Error updating process PATH during uninstall: %s", e)
        else:
            try:
                home = Path.home()
                target_files = [home / ".bashrc", home / ".profile", home / ".zshrc"]
                for rc_file in target_files:
                    if not rc_file.exists():
                        continue
                    try:
                        with open(rc_file, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        new_lines = []
                        for line in lines:
                            skip = False
                            if "me3" in line.lower() and "PATH" in line:
                                skip = True
                            for r in norm_remove:
                                if r in line.lower():
                                    skip = True
                                    break
                            if not skip:
                                new_lines.append(line)
                        with open(rc_file, "w", encoding="utf-8") as f:
                            f.writelines(new_lines)
                    except Exception as e:
                        log.warning("Failed to update %s: %s", rc_file, e)

                curr = os.environ.get("PATH", "").split(":")
                cleaned = []
                for p in curr:
                    norm = p.replace("\\", "/").rstrip("/").lower()
                    if not (norm.endswith("/.local/bin") or norm in norm_remove):
                        cleaned.append(p)
                os.environ["PATH"] = ":".join(cleaned)
            except Exception as e:
                log.warning("Error updating Linux PATH during uninstall: %s", e)

    def kill_me3_processes(self) -> None:
        """Kill any running me3 background processes to release file locks."""
        import time

        try:
            if sys.platform == "win32":
                for proc in ("me3.exe", "me3-launcher.exe"):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/IM", proc],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            else:
                for proc in ("me3", "me3-launcher"):
                    subprocess.run(
                        ["pkill", "-9", "-f", proc],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            time.sleep(0.2)
        except Exception as e:
            log.debug("Failed to kill me3 processes: %s", e)

    def uninstall_me3(self) -> bool:
        """Uninstall ME3 completely, deleting binaries, custom/official installations, PATH entries, and AppData/settings."""
        from me3_manager.core.paths.profile_paths import (
            get_custom_me3_location,
        )

        custom_loc = get_custom_me3_location()
        custom_exists = custom_loc and custom_loc.exists()

        official_exists = False
        official_win_base = None
        official_linux_bin = None
        uninstaller_exe = None

        if sys.platform == "win32":
            localappdata = Path(
                os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
            )
            for subpath in ("Programs/garyttierney/me3", "garyttierney/me3"):
                target_dir = localappdata / subpath
                if target_dir.exists():
                    official_exists = True
                    if not official_win_base:
                        official_win_base = target_dir
                    for exe in target_dir.glob("*.exe"):
                        if exe.name.lower().startswith(("unins", "uninstall", "maint")):
                            uninstaller_exe = exe
                            break
                if uninstaller_exe:
                    break
        elif sys.platform == "linux":
            official_linux_bin = Path.home() / ".local" / "bin" / "me3"
            official_exists = official_linux_bin.exists()

        base_appdata = None
        if sys.platform == "win32":
            base_appdata = (
                Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
                / "garyttierney"
            )
        else:
            base_appdata = (
                Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "me3"
            )

        paths_to_show = []
        paths_to_clean = []

        if custom_exists and custom_loc:
            p_str = str(custom_loc)
            if p_str not in paths_to_show:
                paths_to_show.append(p_str)
            paths_to_clean.append(p_str)
            paths_to_clean.append(str(custom_loc / "bin"))

        if official_exists:
            if sys.platform == "win32" and official_win_base:
                p_str = str(official_win_base)
                if p_str not in paths_to_show and p_str != str(base_appdata):
                    paths_to_show.append(p_str)
                paths_to_clean.append(p_str)
                paths_to_clean.append(str(official_win_base / "bin"))
            elif sys.platform == "linux" and official_linux_bin:
                p_str = str(official_linux_bin)
                if p_str not in paths_to_show:
                    paths_to_show.append(p_str)
                paths_to_clean.append(p_str)

        if base_appdata and base_appdata.exists():
            p_str = str(base_appdata)
            if p_str not in paths_to_show:
                paths_to_show.append(p_str)
            paths_to_clean.append(p_str)

        if not paths_to_show:
            try:
                bin_path = self.path_manager.get_me3_binary_path()
                paths_to_show.append(str(bin_path))
                paths_to_clean.append(str(bin_path))
            except Exception:
                paths_to_show.append("ME3 Installation")

        final_show = []
        for p in paths_to_show:
            try:
                p_obj = Path(p).resolve()
                if any(
                    p_obj != Path(other).resolve()
                    and p_obj.is_relative_to(Path(other).resolve())
                    for other in paths_to_show
                ):
                    continue
                p_str = str(p_obj)
            except Exception:
                p_str = str(p)
            if p_str not in final_show:
                final_show.append(p_str)

        paths_str = "\n".join(f" - {p}" for p in final_show)

        reply = QMessageBox.question(
            self.parent,
            tr("uninstall_me3_confirm_title"),
            tr("uninstall_me3_confirm", path=paths_str),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

        # Terminate any background me3 process to release file locks
        self.kill_me3_processes()

        # 0. Unhook active Qt QFileSystemWatcher paths to prevent access denied / change notification errors
        try:
            if (
                hasattr(self.config_manager, "file_watcher")
                and self.config_manager.file_watcher
            ):
                dirs = self.config_manager.file_watcher.directories()
                if dirs:
                    self.config_manager.file_watcher.removePaths(dirs)
                files = self.config_manager.file_watcher.files()
                if files:
                    self.config_manager.file_watcher.removePaths(files)
            if (
                hasattr(self.config_manager, "file_watcher_handler")
                and self.config_manager.file_watcher_handler
            ):
                fw = getattr(self.config_manager.file_watcher_handler, "watcher", None)
                if fw:
                    dirs = fw.directories()
                    if dirs:
                        fw.removePaths(dirs)
                    files = fw.files()
                    if files:
                        fw.removePaths(files)
        except Exception as e:
            log.warning("Could not unhook file watcher during uninstall: %s", e)

        # 1. Remove ME3 path from system/user PATH
        self._remove_me3_from_user_path(paths_to_clean)

        # Helper for recursive force deletion on Windows
        def _force_rmtree(path_to_remove: Path):
            if not path_to_remove or not path_to_remove.exists():
                return
            import stat

            def _onerror(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            try:
                shutil.rmtree(path_to_remove, onerror=_onerror)
            except Exception:
                try:
                    shutil.rmtree(path_to_remove, ignore_errors=True)
                except Exception as e:
                    log.warning("Failed to force remove %s: %s", path_to_remove, e)

        # 2. Official uninstallation (wait synchronously for completion)
        if sys.platform == "win32":
            if uninstaller_exe and uninstaller_exe.exists():
                try:
                    log.info(
                        "Running official uninstaller synchronously: %s",
                        uninstaller_exe,
                    )
                    proc = subprocess.Popen(
                        [str(uninstaller_exe), "/SILENT", "/SUPPRESSMSGBOXES"]
                    )
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        log.warning("Uninstaller timed out, continuing cleanup.")
                except Exception as e:
                    log.warning("Failed to run uninstaller %s: %s", uninstaller_exe, e)
            if official_win_base and official_win_base.exists():
                _force_rmtree(official_win_base)
        elif sys.platform == "linux":
            if official_linux_bin and official_linux_bin.exists():
                try:
                    official_linux_bin.unlink(missing_ok=True)
                except Exception as e:
                    log.warning("Failed to delete %s: %s", official_linux_bin, e)

        # 3. Custom uninstallation
        if custom_exists and custom_loc and custom_loc.exists():
            log.info("Removing custom ME3 directory: %s", custom_loc)
            _force_rmtree(custom_loc)

        # 4. Fallback check if binary exists directly
        try:
            bin_path = self.path_manager.get_me3_binary_path()
            exe_name = "me3.exe" if sys.platform == "win32" else "me3"
            exe_path = bin_path / exe_name
            if exe_path.exists():
                import stat

                try:
                    os.chmod(exe_path, stat.S_IWRITE)
                except Exception:
                    pass
                exe_path.unlink(missing_ok=True)
        except Exception as e:
            log.debug("Fallback binary cleanup: %s", e)

        # 5. Delete manager settings, profiles, and AppData directory (C:\Users\...\AppData\Local\garyttierney)
        log.info("Deleting manager settings, profiles, and app data.")
        if (
            hasattr(self.path_manager, "settings_manager")
            and self.path_manager.settings_manager
        ):
            try:
                self.path_manager.settings_manager.clear(auto_save=False)
            except Exception:
                pass

        if sys.platform == "win32":
            if base_appdata:
                _force_rmtree(base_appdata)
        else:
            xdg_config = (
                Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "me3"
            )
            if xdg_config.exists():
                _force_rmtree(xdg_config)
            xdg_data = (
                Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
                / "garyttierney"
            )
            if xdg_data.exists():
                _force_rmtree(xdg_data)

        # Refresh state and notify user
        try:
            if (
                hasattr(self.config_manager, "me3_info_manager")
                and self.config_manager.me3_info_manager
            ):
                self.config_manager.me3_info_manager.refresh_info()
            elif hasattr(self.config_manager, "refresh_me3_info"):
                self.config_manager.refresh_me3_info()
        except Exception as e:
            log.warning("Error refreshing me3_info after uninstall: %s", e)

        if hasattr(self.path_manager, "refresh_config_root"):
            try:
                self.path_manager.refresh_config_root()
            except Exception:
                pass

        if self.refresh_callback:
            try:
                self.refresh_callback()
            except Exception as e:
                log.warning("Error during refresh_callback after uninstall: %s", e)

        QMessageBox.information(
            self.parent, tr("uninstall_complete_title"), tr("uninstall_complete")
        )
        return True


class ME3CustomInstaller(QObject):
    """Handles downloading and installing ME3 portable distribution for Windows."""

    download_progress = Signal(int)
    install_finished = Signal(int, int, str)  # status_code, return_code, message

    def __init__(
        self,
        url: str,
        temp_path: str,
        path_manager,
        add_to_path: bool = False,
        install_path: Path | str | None = None,
    ):
        super().__init__()
        self.url = url
        self.temp_path = temp_path
        self.path_manager = path_manager
        self.add_to_path = add_to_path
        # Use explicit install_path if provided, otherwise fallback to PathManager
        self.install_path = (
            Path(install_path)
            if install_path
            else self.path_manager.get_me3_binary_path()
        )
        self._is_cancelled = False

    @staticmethod
    def _is_target_binary(file_path: str, target_files: list[str]) -> bool:
        normalized_path = file_path.replace("\\", "/")
        path_parts = normalized_path.split("/")
        if "bin" in path_parts:
            bin_index = path_parts.index("bin")
            if bin_index < len(path_parts) - 1 and path_parts[bin_index + 1]:
                return True
        return os.path.basename(file_path) in target_files

    def _emit_missing_exe_error(self, all_files: list[str]) -> None:
        files_list = "\n".join(all_files[:10])
        if len(all_files) > 10:
            files_list += f"\n... and {len(all_files) - 10} more files"
        self.install_finished.emit(
            Status.INVALID_DATA,
            -2,
            tr(
                "could_not_find_me3_exe",
                file_count=len(all_files),
                files_list=files_list,
            ),
        )

    def run(self):
        try:
            # Step 1: Download the ZIP file
            def cancel_action():
                self.install_finished.emit(
                    Status.CANCELLED, -1, tr("download_cancelled")
                )

            success = _download_file(
                self.url,
                self.temp_path,
                self.download_progress.emit,
                lambda: self._is_cancelled,
                cancel_action,
                0.5,  # First 50% for download
            )

            if not success:
                return

            # Step 2: Extract and install
            self.download_progress.emit(50)  # Download complete

            # Create installation directory
            os.makedirs(self.install_path, exist_ok=True)

            # Extract archive (ZIP on Windows, TAR.GZ on Linux)
            target_files = [
                "me3.exe",
                "me3",
                "me3_mod_host.dll",
                "me3_mod_host.so",
                "me3-launcher.exe",
                "me3-launcher",
            ]
            extracted_count = 0

            if self.temp_path.endswith((".zip", ".ZIP")):
                with zipfile.ZipFile(self.temp_path, "r") as zip_ref:
                    all_files = zip_ref.namelist()
                    bin_files = [
                        fp
                        for fp in all_files
                        if self._is_target_binary(fp, target_files)
                    ]

                    if not bin_files:
                        self._emit_missing_exe_error(all_files)
                        return

                    for file_path in bin_files:
                        try:
                            filename = os.path.basename(file_path)
                            if filename:
                                target_path = os.path.join(self.install_path, filename)
                                with (
                                    zip_ref.open(file_path) as source,
                                    open(target_path, "wb") as target,
                                ):
                                    target.write(source.read())
                                extracted_count += 1
                                if sys.platform != "win32" and (
                                    filename in ("me3", "me3-launcher")
                                    or not filename.endswith(
                                        (".so", ".dll", ".txt", ".md")
                                    )
                                ):
                                    os.chmod(target_path, 0o755)
                        except Exception as e:
                            log.warning("Failed to extract %s: %s", file_path, e)
                            continue

            elif self.temp_path.endswith((".tar.gz", ".tgz", ".tar")):
                with tarfile.open(self.temp_path, "r:*") as tar_ref:
                    members = tar_ref.getmembers()
                    all_files = [m.name for m in members if not m.isdir()]
                    bin_members = [
                        m
                        for m in members
                        if not m.isdir()
                        and self._is_target_binary(m.name, target_files)
                    ]

                    if not bin_members:
                        self._emit_missing_exe_error(all_files)
                        return

                    for m in bin_members:
                        try:
                            filename = os.path.basename(m.name)
                            if filename:
                                target_path = os.path.join(self.install_path, filename)
                                source_f = tar_ref.extractfile(m)
                                if source_f is not None:
                                    with open(target_path, "wb") as target:
                                        target.write(source_f.read())
                                    source_f.close()
                                    extracted_count += 1
                                    mode = m.mode
                                    if filename in ("me3", "me3-launcher") or (
                                        mode & 0o111
                                    ):
                                        os.chmod(target_path, 0o755)
                                    elif mode > 0:
                                        os.chmod(target_path, mode)
                        except Exception as e:
                            log.warning("Failed to extract %s: %s", m.name, e)
                            continue

            if extracted_count == 0:
                self.install_finished.emit(Status.FAILED, -2, tr("failed_extract"))
                return

            self.download_progress.emit(75)  # Extraction complete

            # Step 3: Add to user PATH if requested
            if self.add_to_path:
                if not self._add_to_user_path(str(self.install_path)):
                    self.install_finished.emit(
                        Status.PERMISSION_ERROR, -3, tr("add_user_path_failed")
                    )
                    return
            self.download_progress.emit(90)  # PATH update complete

            # Step 4: Refresh environment variables and current process PATH
            self._refresh_environment()
            self.download_progress.emit(100)  # Complete

            # Clean up temp file
            try:
                os.remove(self.temp_path)
            except (OSError, FileNotFoundError, PermissionError):
                pass  # Ignore file cleanup errors

            if self.add_to_path:
                msg = tr("install_add_path", install_path=str(self.install_path))
            else:
                msg = tr("install_no_path", install_path=str(self.install_path))
                if msg == "install_no_path":
                    msg = f"ME3 has been successfully installed to:\n{self.install_path}\n\nME3 was NOT added to your user PATH as requested. ME3 Manager will point to this binary directly for all commands."

            self.install_finished.emit(
                Status.SUCCESS,
                0,
                msg,
            )

        except (zipfile.BadZipFile, tarfile.ReadError):
            self.install_finished.emit(
                Status.INVALID_DATA, -2, tr("download_file_not_vaild")
            )
        except requests.RequestException as e:
            self.install_finished.emit(
                Status.NETWORK_ERROR, -1, tr("NETWORK_ERROR", e=e)
            )
        except Exception as e:
            self.install_finished.emit(Status.FAILED, -3, tr("ERROR_OCCURRED", e=e))

    def _add_to_user_path(self, new_path: str) -> bool:
        """Add the installation path to the user PATH environment variable."""
        if sys.platform != "win32":
            return self._add_to_linux_user_path(new_path)
        try:
            # Open the user Environment subkey in the registry
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS
            ) as key:
                # Get current PATH value
                try:
                    current_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current_path = ""

                # Split PATH into individual paths and clean them up
                paths = [p.strip() for p in current_path.split(";") if p.strip()]

                # UPDATED: Remove any existing ME3 paths (both old and new patterns)
                cleaned_paths = []
                for path in paths:
                    # Normalize path separators and check if it ends with me3\bin or garyttierney\me3\bin
                    normalized_path = path.replace("/", "\\").rstrip("\\").lower()
                    if not normalized_path.endswith(
                        ("\\me3\\bin", "\\garyttierney\\me3\\bin")
                    ):
                        cleaned_paths.append(path)
                    else:
                        log.debug("Removed existing ME3 path from user PATH: %s", path)

                # Add the new path if it's not already there
                if new_path not in cleaned_paths:
                    cleaned_paths.append(new_path)
                    log.debug("Added new ME3 path to user PATH: %s", new_path)

                # Set the new PATH value
                new_path_value = ";".join(cleaned_paths)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path_value)
                return True

        except Exception as e:
            log.error("Error updating user PATH: %s", e)
            return False

    def _add_to_linux_user_path(self, new_path: str) -> bool:
        """Add the installation path to Linux user shell configuration files."""
        try:
            home = Path.home()
            target_files = [home / ".bashrc", home / ".profile", home / ".zshrc"]
            existing = [f for f in target_files if f.exists()]
            if not existing:
                existing = [home / ".profile"]

            export_line = f'\n# Added by ME3 Manager\nexport PATH="$PATH:{new_path}"\n'
            updated_any = False
            for rc_file in existing:
                try:
                    content = ""
                    if rc_file.exists():
                        with open(rc_file, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    if new_path not in content:
                        with open(rc_file, "a", encoding="utf-8") as f:
                            f.write(export_line)
                    updated_any = True
                except Exception as e:
                    log.warning("Failed to update %s: %s", rc_file, e)
            return updated_any
        except Exception as e:
            log.error("Error updating Linux user PATH: %s", e)
            return False

    def _refresh_environment(self):
        """Refresh environment variables without requiring logout/restart."""
        try:
            if sys.platform == "win32":
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
                    None,
                )

                if result == 0:
                    log.warning("Failed to broadcast environment variable changes")
                else:
                    log.debug("Successfully broadcasted environment variable changes")

            # IMPORTANT: Also refresh the current process's environment
            self._refresh_current_process_path()

        except Exception as e:
            log.warning("Could not refresh environment variables: %s", e)

    def _refresh_current_process_path(self):
        """Refresh the PATH environment variable for the current process."""
        try:
            if sys.platform == "win32":
                # Read the updated user PATH from registry
                user_path = ""
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ
                    ) as key:
                        user_path, _ = winreg.QueryValueEx(key, "Path")
                except Exception:
                    user_path = ""
                system_path = os.environ.get("PATH", "")
                current_process_paths = [
                    p.strip() for p in system_path.split(";") if p.strip()
                ]
                cleaned_system_paths = []
                for path in current_process_paths:
                    normalized_path = path.replace("/", "\\").rstrip("\\").lower()
                    if not normalized_path.endswith(
                        ("\\me3\\bin", "\\garyttierney\\me3\\bin")
                    ):
                        cleaned_system_paths.append(path)

                if self.add_to_path and str(self.install_path) not in (
                    user_path.split(";") if user_path else []
                ):
                    cleaned_system_paths.insert(0, str(self.install_path))

                if user_path:
                    new_path = user_path + ";" + ";".join(cleaned_system_paths)
                else:
                    new_path = ";".join(cleaned_system_paths)
            else:
                # On Linux/macOS
                system_path = os.environ.get("PATH", "")
                current_process_paths = [
                    p.strip() for p in system_path.split(":") if p.strip()
                ]
                cleaned_paths = []
                norm_install = str(self.install_path).replace("\\", "/").rstrip("/")
                for path in current_process_paths:
                    norm = path.replace("\\", "/").rstrip("/")
                    if norm != norm_install and not norm.endswith(
                        ("/me3/bin", "/garyttierney/me3/bin")
                    ):
                        cleaned_paths.append(path)
                if self.add_to_path:
                    cleaned_paths.insert(0, str(self.install_path))
                new_path = ":".join(cleaned_paths)

            os.environ["PATH"] = new_path
            log.debug(
                "Updated current process PATH (add_to_path=%s), ME3 installation: %s",
                self.add_to_path,
                self.install_path,
            )
        except Exception as e:
            log.warning("Could not refresh current process PATH: %s", e)

    def cancel(self):
        self._is_cancelled = True
