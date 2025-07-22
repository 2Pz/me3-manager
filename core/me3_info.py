import subprocess
import sys
import re
import os
from typing import Optional, Dict, List
from pathlib import Path

class ME3InfoManager:
    """
    Manages ME3 installation information and paths using 'me3 info' command.
    UPDATED to be fully cross-platform and compatible with me3 v0.7.0+ output.
    """

    def __init__(self):
        self._info_cache: Optional[Dict[str, str]] = None
        self._is_installed: Optional[bool] = None

    def _prepare_command(self, cmd: List[str]) -> List[str]:
        """
        Prepares a command for execution, handling platform specifics.
        """
        if sys.platform == "linux":
            if os.environ.get('FLATPAK_ID'):
                return ["flatpak-spawn", "--host"] + cmd

            user_shell = os.environ.get("SHELL", "/bin/bash")
            if not Path(user_shell).exists():
                user_shell = "/bin/bash"

            command_str = " ".join(cmd)
            return [user_shell, "-l", "-c", command_str]

        return cmd

    def is_me3_installed(self) -> bool:
        """Check if ME3 is installed and accessible."""
        if self._is_installed is not None:
            return self._is_installed

        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            command = self._prepare_command(["me3", "--version"])
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0 and result.stdout:
                self._is_installed = True
            else:
                self._is_installed = False

        except (FileNotFoundError, subprocess.TimeoutExpired, UnicodeDecodeError):
            self._is_installed = False

        return self._is_installed

    def get_me3_info(self) -> Optional[Dict[str, str]]:
        """Get ME3 installation information using 'me3 info' command."""
        if not self.is_me3_installed():
            return None

        if self._info_cache is not None:
            return self._info_cache

        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            command = self._prepare_command(["me3", "info"])
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                timeout=15,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode != 0 or not result.stdout:
                print(f"Failed to get 'me3 info'. Exit code: {result.returncode}, Stderr: {result.stderr}")
                return None

            info = self._parse_me3_info(result.stdout)
            self._info_cache = info
            return info

        except (FileNotFoundError, subprocess.TimeoutExpired, UnicodeDecodeError) as e:
            print(f"Error getting ME3 info: {e}")
            return None

    def _parse_me3_info(self, output: str) -> Dict[str, str]:
        """
        Parse the output of 'me3 info', compatible with both old and new formats.
        """
        info = {}
        if not output:
            return info

        # For older me3 versions
        version_match = re.search(r'version="([^"]+)"', output)
        if version_match:
            info['version'] = version_match.group(1)

        commit_match = re.search(r'commit_id="([^"]+)"', output)
        if commit_match:
            info['commit_id'] = commit_match.group(1)

        # For new (v0.7.0+) and old versions. Handles optional indentation.
        profile_dir_match = re.search(r'^\s*Profile directory:\s*(.+)', output, re.MULTILINE)
        if profile_dir_match:
            info['profile_directory'] = profile_dir_match.group(1).strip()

        logs_dir_match = re.search(r'^\s*Logs directory:\s*(.+)', output, re.MULTILINE)
        if logs_dir_match:
            info['logs_directory'] = logs_dir_match.group(1).strip()

        install_prefix_match = re.search(r'^\s*Installation prefix:\s*(.+)', output, re.MULTILINE)
        if install_prefix_match:
            info['installation_prefix'] = install_prefix_match.group(1).strip()

        # Works for both versions due to re.DOTALL
        steam_status_match = re.search(r'Steam.*?Status:\s*(.+)', output, re.DOTALL)
        if steam_status_match:
            info['steam_status'] = steam_status_match.group(1).strip()

        # Works for older versions, fails gracefully on new ones
        steam_path_match = re.search(r'Steam.*?Path:\s*(.+)', output, re.DOTALL)
        if steam_path_match:
            info['steam_path'] = steam_path_match.group(1).strip()

        return info

    def get_profile_directory(self) -> Optional[Path]:
        """Get the ME3 profile directory path."""
        info = self.get_me3_info()
        if info and 'profile_directory' in info:
            return Path(info['profile_directory'])
        return None

    def get_logs_directory(self) -> Optional[Path]:
        """Get the ME3 logs directory path."""
        info = self.get_me3_info()
        if info and 'logs_directory' in info:
            return Path(info['logs_directory'])
        return None

    def get_steam_path(self) -> Optional[Path]:
        """Get the Steam installation path if provided."""
        info = self.get_me3_info()
        if info and 'steam_path' in info and info['steam_path'] != '<none>':
            return Path(info['steam_path'])
        return None

    def get_installation_prefix(self) -> Optional[Path]:
        """Get the ME3 installation prefix path."""
        info = self.get_me3_info()
        if info and 'installation_prefix' in info:
            return Path(info['installation_prefix'])
        return None

    def get_version(self) -> Optional[str]:
        """Get the ME3 version, using 'me3 info' with a fallback to '--version'."""
        info = self.get_me3_info()
        if info and 'version' in info:
            return info['version']

        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            command = self._prepare_command(["me3", "--version"])
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )

            if result.stdout:
                version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    return version_match.group(1)
                return result.stdout.strip().split('\n')[0]

        except Exception as e:
            print(f"Error getting version from --version command: {e}")

        return None

    def is_steam_found(self) -> bool:
        """Check if Steam is found by ME3."""
        info = self.get_me3_info()
        return info is not None and info.get('steam_status', '').lower() == 'found'

    def refresh_info(self):
        """Clear cached info to force refresh on next access."""
        self._info_cache = None
        self._is_installed = None
