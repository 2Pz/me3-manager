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
        Updated to handle the bullet-point format with indented values.
        """
        info = {}
        if not output:
            return info

        # For older me3 versions (XML-like format)
        version_match = re.search(r'version="([^"]+)"', output)
        if version_match:
            info['version'] = version_match.group(1)

        commit_match = re.search(r'commit_id="([^"]+)"', output)
        if commit_match:
            info['commit_id'] = commit_match.group(1)

        # For newer format with bullet points and indentation
        # Profile directory: handles both direct format and indented format
        profile_dir_patterns = [
            r'^\s*Profile directory:\s*(.+)',  # Original pattern
            r'Profile directory:\s*(.+)',      # Direct after bullet
        ]
        for pattern in profile_dir_patterns:
            profile_dir_match = re.search(pattern, output, re.MULTILINE)
            if profile_dir_match:
                info['profile_directory'] = profile_dir_match.group(1).strip()
                break

        # Logs directory: handles both formats
        logs_dir_patterns = [
            r'^\s*Logs directory:\s*(.+)',     # Original pattern
            r'Logs directory:\s*(.+)',         # Direct after spaces/indentation
        ]
        for pattern in logs_dir_patterns:
            logs_dir_match = re.search(pattern, output, re.MULTILINE)
            if logs_dir_match:
                info['logs_directory'] = logs_dir_match.group(1).strip()
                break

        # Installation prefix: handles both formats
        install_prefix_patterns = [
            r'^\s*Installation prefix:\s*(.+)',  # Original pattern
            r'Installation prefix:\s*(.+)',       # Direct format
        ]
        for pattern in install_prefix_patterns:
            install_prefix_match = re.search(pattern, output, re.MULTILINE)
            if install_prefix_match:
                info['installation_prefix'] = install_prefix_match.group(1).strip()
                break

        # Steam status: Updated to handle the new format
        # Look for "● Steam" section followed by "Status: ..."
        steam_section_match = re.search(r'● Steam\s*\n\s*Status:\s*(.+)', output, re.MULTILINE)
        if steam_section_match:
            info['steam_status'] = steam_section_match.group(1).strip()
        else:
            # Fallback to old format
            steam_status_match = re.search(r'Steam.*?Status:\s*(.+)', output, re.DOTALL)
            if steam_status_match:
                info['steam_status'] = steam_status_match.group(1).strip()

        # Steam path: Try to find it in the old format (may not exist in new format)
        steam_path_match = re.search(r'Steam.*?Path:\s*(.+)', output, re.DOTALL)
        if steam_path_match:
            info['steam_path'] = steam_path_match.group(1).strip()

        # Installation status: New field in the bullet format
        install_status_match = re.search(r'Status:\s*(.+)', output)
        if install_status_match:
            # Only capture if it's in the Installation section, not Steam section
            lines = output.split('\n')
            for i, line in enumerate(lines):
                if 'Status:' in line and any('Installation' in prev_line for prev_line in lines[max(0, i-3):i]):
                    info['installation_status'] = install_status_match.group(1).strip()
                    break

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
        if not info:
            return False
        
        steam_status = info.get('steam_status', '').lower()
        return steam_status in ['found', 'detected', 'available']

    def is_steam_not_found(self) -> bool:
        """Check if Steam is explicitly not found by ME3."""
        info = self.get_me3_info()
        if not info:
            return True
            
        steam_status = info.get('steam_status', '').lower()
        return steam_status in ['not found', 'missing', 'unavailable']

    def get_installation_status(self) -> Optional[str]:
        """Get the installation status."""
        info = self.get_me3_info()
        return info.get('installation_status') if info else None

    def refresh_info(self):
        """Clear cached info to force refresh on next access."""
        self._info_cache = None
        self._is_installed = None
