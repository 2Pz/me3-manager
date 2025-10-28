import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QFileInfo, QProcessEnvironment, QUrl
from PySide6.QtGui import QDesktopServices


class PlatformUtils:
    """
    Centralized platform utilities.
    - Qt-based open of files/directories
    - Cross-platform command preparation (Flatpak-aware)
    """

    @staticmethod
    def is_flatpak() -> bool:
        """Detect if running inside Flatpak sandbox."""
        try:
            if sys.platform != "linux":
                return False
            if os.environ.get("FLATPAK_ID"):
                return True
            if os.path.exists("/.flatpak-info"):
                return True
            if "/app/" in os.environ.get("PATH", ""):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def prepare_command(cmd: list[str]) -> list[str]:
        """
        Prepare an external command for execution, adding necessary wrappers
        on Linux/Flatpak. Keeps behavior minimal to avoid surprises.
        """
        # Resolve me3 executable explicitly on Windows in case PATH is not updated
        try:
            if sys.platform == "win32" and isinstance(cmd, list) and cmd:
                if str(cmd[0]).lower() == "me3":
                    resolved = PlatformUtils._find_me3_executable_windows()
                    if resolved:
                        cmd = [resolved] + list(cmd[1:])
        except Exception:
            # Best-effort; fall through to default behavior
            pass

        # Resolve me3 executable explicitly on Linux where PATH may be minimal (e.g., SteamOS Game Mode)
        try:
            if sys.platform == "linux" and isinstance(cmd, list) and cmd:
                if str(cmd[0]).lower() == "me3":
                    resolved = PlatformUtils._find_me3_executable_linux()
                    if resolved:
                        cmd = [resolved] + list(cmd[1:])
        except Exception:
            # Best-effort; fall through to default behavior
            pass

        if sys.platform == "linux" and PlatformUtils.is_flatpak():
            return ["flatpak-spawn", "--host"] + cmd
        return cmd

    @staticmethod
    def _find_me3_executable_windows() -> str | None:
        """
        Best-effort resolution of me3.exe on Windows without requiring elevation.
        - Prefer shutil.which("me3") if available in current PATH
        - Check Windows App Paths registry (HKCU/HKLM) for me3.exe
        - Fall back to common per-user install path under LOCALAPPDATA
        - Fall back to HOME-based path if LOCALAPPDATA is unavailable
        Returns absolute path to me3.exe or None if not found.
        """
        try:
            if sys.platform != "win32":
                return None

            # 1) Check current PATH first
            me3_path = shutil.which("me3")
            if me3_path and Path(me3_path).is_file():
                return me3_path

            # 1.5) Check Windows "App Paths" registry keys
            try:
                import importlib

                winreg = importlib.import_module("winreg")  # type: ignore
                for root in (
                    winreg.HKEY_CURRENT_USER,
                    winreg.HKEY_LOCAL_MACHINE,
                ):
                    try:
                        with winreg.OpenKey(
                            root,
                            r"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\me3.exe",
                            0,
                            winreg.KEY_READ,
                        ) as key:
                            try:
                                exe_path, _ = winreg.QueryValueEx(key, None)
                                if exe_path and Path(exe_path).is_file():
                                    return str(Path(exe_path))
                            except FileNotFoundError:
                                pass
                    except OSError:
                        continue
            except Exception:
                # Ignore registry probing failures and continue
                pass

            # 2) Check known per-user installation location
            localappdata = os.environ.get("LOCALAPPDATA")
            candidates: list[Path] = []
            if localappdata:
                candidates.append(
                    Path(localappdata) / "garyttierney" / "me3" / "bin" / "me3.exe"
                )
                # Also consider default installer path under Local\\Programs
                candidates.append(
                    Path(localappdata)
                    / "Programs"
                    / "garyttierney"
                    / "me3"
                    / "bin"
                    / "me3.exe"
                )

            # 3) Fallback based on HOME path
            home = Path.home()
            if str(home):
                candidates.append(
                    home
                    / "AppData"
                    / "Local"
                    / "garyttierney"
                    / "me3"
                    / "bin"
                    / "me3.exe"
                )

            for candidate in candidates:
                try:
                    if candidate and candidate.is_file():
                        return str(candidate)
                except Exception:
                    continue
        except Exception:
            return None
        return None

    @staticmethod
    def _find_me3_executable_linux() -> str | None:
        """
        Best-effort resolution of me3 on Linux (incl. Steam Deck Game Mode),
        avoiding reliance on PATH.
        Search order:
          1) PATH via shutil.which
          2) XDG config-based bin (…/me3/bin/me3)
          3) ~/.local/bin/me3
          4) Common system bins (/usr/local/bin, /usr/bin)
          5) XDG data-based layout (…/garyttierney/me3/bin/me3)
        Returns absolute path or None.
        """
        try:
            if sys.platform != "linux":
                return None

            me3_path = shutil.which("me3")
            if me3_path and Path(me3_path).is_file():
                return me3_path

            candidates: list[Path] = []

            # XDG config based bin
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                candidates.append(Path(xdg_config) / "me3" / "bin" / "me3")
            candidates.append(Path.home() / ".config" / "me3" / "bin" / "me3")

            # Local user bin
            candidates.append(Path.home() / ".local" / "bin" / "me3")

            # System bins
            for p in ("/usr/local/bin/me3", "/usr/bin/me3"):
                candidates.append(Path(p))

            # XDG data based layout
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                candidates.append(
                    Path(xdg_data) / "garyttierney" / "me3" / "bin" / "me3"
                )
            candidates.append(
                Path.home()
                / ".local"
                / "share"
                / "garyttierney"
                / "me3"
                / "bin"
                / "me3"
            )

            for candidate in candidates:
                try:
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        return str(candidate)
                except Exception:
                    continue
        except Exception:
            return None
        return None

    @staticmethod
    def open_path(path: str, run_file: bool = False) -> bool:
        """
        Open a file or its containing directory using Qt services.

        Args:
            path: Target filesystem path
            run_file: If True, open the file; else open its directory

        Returns:
            True if the request was accepted by the desktop services
        """
        try:
            info = QFileInfo(path)
            if not run_file:
                # Open the containing directory
                target = (
                    info.absolutePath() if info.exists() else QFileInfo(path).path()
                )
            else:
                target = info.absoluteFilePath()

            # Prefer fallback in PyInstaller/Flatpak where Qt may lie about success
            if sys.platform == "linux" and (
                PlatformUtils._is_pyinstaller() or PlatformUtils.is_flatpak()
            ):
                if PlatformUtils._fallback_open_local(target):
                    return True
                url = QUrl.fromLocalFile(target)
                return QDesktopServices.openUrl(url)
            else:
                url = QUrl.fromLocalFile(target)
                if QDesktopServices.openUrl(url):
                    return True
                return PlatformUtils._fallback_open_local(target)
        except Exception:
            return False

    @staticmethod
    def open_dir(dir_path: str) -> bool:
        """
        Open a directory using Qt services. Accepts any path and resolves to a directory.
        """
        try:
            info = QFileInfo(dir_path)
            # If it's a file, use its parent directory; otherwise the directory itself
            target_dir = (
                info.absolutePath() if not info.isDir() else info.absoluteFilePath()
            )
            # Normalize using QDir
            target_dir = QDir.cleanPath(target_dir)
            # Prefer fallback in PyInstaller/Flatpak where Qt may lie about success
            if sys.platform == "linux" and (
                PlatformUtils._is_pyinstaller() or PlatformUtils.is_flatpak()
            ):
                if PlatformUtils._fallback_open_local(target_dir):
                    return True
                url = QUrl.fromLocalFile(target_dir)
                return QDesktopServices.openUrl(url)
            else:
                url = QUrl.fromLocalFile(target_dir)
                if QDesktopServices.openUrl(url):
                    return True
                return PlatformUtils._fallback_open_local(target_dir)
        except Exception:
            return False

    @staticmethod
    def open_url(url_str: str) -> bool:
        """
        Open an external URL using Qt services.
        Returns True if the desktop service accepted the request.
        """
        try:
            url = QUrl(url_str)
            if QDesktopServices.openUrl(url):
                return True
            # Best-effort textual URL fallback
            return PlatformUtils._fallback_open_textual(url_str)
        except Exception:
            return False

    # -------- QProcess helpers --------
    @staticmethod
    def prepare_string_command_for_qprocess(command: str) -> tuple[str, list[str]]:
        """
        Build a (program, args) tuple for QProcess to execute a string command consistently.
        - Windows: cmd /c <command>
        - Linux (Flatpak): bash -c "flatpak-spawn --host bash -l -c '<command>'"
        - Linux (non-Flatpak): bash -l -c <command>
        """
        if sys.platform == "win32":
            return "cmd", ["/c", command]

        if PlatformUtils.is_flatpak():
            full = f"flatpak-spawn --host bash -l -c {shlex.quote(command)}"
            return "bash", ["-c", full]

        return "bash", ["-l", "-c", command]

    @staticmethod
    def prepare_list_command_for_qprocess(
        args_list: list[str],
    ) -> tuple[str, list[str]]:
        """
        Build a (program, args) for QProcess when given an argv-style command.
        - Windows: run program directly with args
        - Linux Flatpak + program == me3: wrap via flatpak-spawn and login shell
        - Linux otherwise: run via bash -l -c to keep login env
        """
        if not args_list:
            return "", []

        program = args_list[0]
        rest = args_list[1:]

        if sys.platform == "win32":
            # Resolve me3.exe explicitly if needed
            try:
                if str(program).lower() == "me3":
                    resolved = PlatformUtils._find_me3_executable_windows()
                    if resolved:
                        program = resolved
            except Exception:
                pass
            return program, rest

        # Resolve me3 explicitly on Linux
        try:
            if str(program).lower() == "me3":
                resolved = PlatformUtils._find_me3_executable_linux()
                if resolved:
                    program = resolved
        except Exception:
            pass

        # On Flatpak, ensure we spawn on host when invoking me3 (absolute or bare)
        if PlatformUtils.is_flatpak() and os.path.basename(str(program)) == "me3":
            shell_command = " ".join(
                [shlex.quote(program)] + [shlex.quote(a) for a in rest]
            )
            full = f"flatpak-spawn --host bash -l -c {shlex.quote(shell_command)}"
            return "bash", ["-c", full]

        # Non-flatpak: use login shell to maintain environment
        shell_command = " ".join(
            [shlex.quote(program)] + [shlex.quote(a) for a in rest]
        )
        return "bash", ["-l", "-c", shell_command]

    # -------- Fallback helpers --------
    @staticmethod
    def _is_pyinstaller() -> bool:
        """Detect PyInstaller onefile/onedir runtime."""
        return bool(getattr(sys, "_MEIPASS", None)) or os.environ.get(
            "PYINSTALLER_BOOTLOADER"
        )

    @staticmethod
    def _sanitized_env_for_desktop_open() -> dict:
        """Return an environment safe for launching host desktop apps."""
        env = os.environ.copy()
        # PyInstaller/Qt variables that can break system apps
        for key in (
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
            "QT_PLUGIN_PATH",
            "QT_QPA_PLATFORM_PLUGIN_PATH",
            "PYTHONHOME",
            "PYTHONPATH",
            "PYINSTALLER_BOOTLOADER",
        ):
            env.pop(key, None)

        # Ensure XDG_DATA_DIRS is sane for icon/mime resolution
        env.setdefault("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
        return env

    @staticmethod
    def sanitized_env_for_subprocess() -> dict:
        """
        Return an environment safe for launching external host processes.
        This strips PyInstaller/Qt variables (e.g., LD_LIBRARY_PATH) that can
        cause symbol conflicts with system binaries (e.g., libreadline).
        """
        return PlatformUtils._sanitized_env_for_desktop_open()

    @staticmethod
    def build_qprocess_environment() -> QProcessEnvironment:
        """
        Build a sanitized QProcessEnvironment to avoid leaking PyInstaller/Qt
        runtime variables into child processes.
        """
        env_dict = PlatformUtils.sanitized_env_for_subprocess()
        qenv = QProcessEnvironment()
        for k, v in env_dict.items():
            if v is not None:
                qenv.insert(str(k), str(v))
        return qenv

    @staticmethod
    def _fallback_open_local(target: str) -> bool:
        """
        Try to open a local path using common desktop tools with a sanitized env.
        Uses flatpak-spawn --host when inside Flatpak.
        """
        if not target:
            return False

        # Build both URI and plain path variants
        file_uri = QUrl.fromLocalFile(target).toString()
        candidates: list[list[str]] = []
        # Prefer xdg-open; fall back to gio/kde/gnome variants
        for exe in ("xdg-open", "/usr/bin/xdg-open"):
            if shutil.which(exe) or os.path.exists(exe):
                candidates.append([exe, file_uri])
                candidates.append([exe, target])
                break
        for exe in ("gio", "/usr/bin/gio"):
            if shutil.which(exe) or os.path.exists(exe):
                candidates.append([exe, "open", file_uri])
                candidates.append([exe, "open", target])
                break
        for exe in ("kde-open5", "/usr/bin/kde-open5", "kde-open", "/usr/bin/kde-open"):
            if shutil.which(exe) or os.path.exists(exe):
                candidates.append([exe, target])
                break
        for exe in ("gnome-open", "/usr/bin/gnome-open"):
            if shutil.which(exe) or os.path.exists(exe):
                candidates.append([exe, target])
                break

        if not candidates:
            return False

        env = PlatformUtils._sanitized_env_for_desktop_open()
        for cmd in candidates:
            try:
                final_cmd = cmd
                if sys.platform == "linux" and PlatformUtils.is_flatpak():
                    final_cmd = ["flatpak-spawn", "--host"] + cmd
                subprocess.Popen(
                    final_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    start_new_session=True,
                )
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _fallback_open_textual(url_or_text: str) -> bool:
        """
        Fallback for non-file URLs using xdg-open/gio where possible.
        """
        if not url_or_text:
            return False
        env = PlatformUtils._sanitized_env_for_desktop_open()
        candidates: list[list[str]] = []
        if shutil.which("xdg-open"):
            candidates.append(["xdg-open", url_or_text])
        if shutil.which("gio"):
            candidates.append(["gio", "open", url_or_text])

        for cmd in candidates:
            try:
                final_cmd = cmd
                if sys.platform == "linux" and PlatformUtils.is_flatpak():
                    final_cmd = ["flatpak-spawn", "--host"] + cmd
                subprocess.Popen(
                    final_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    start_new_session=True,
                )
                return True
            except Exception:
                continue
        return False
