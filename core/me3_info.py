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
        Uses the same approach as the UI terminal for maximum compatibility.
        """
        if sys.platform == "linux":
            if os.environ.get('FLATPAK_ID'):
                return ["flatpak-spawn", "--host"] + cmd

            # Use the same shell detection logic as the UI terminal
            user_shell = os.environ.get("SHELL", "/bin/bash")
            if not Path(user_shell).exists():
                user_shell = "/bin/bash"
            
            # If bash doesn't exist, fall back to sh
            if not Path(user_shell).exists():
                user_shell = "/bin/sh"
            
            # Final fallback to just 'sh' (should be in PATH)
            if not Path(user_shell).exists():
                user_shell = "sh"

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

    def get_me3_config_paths(self) -> List[Path]:
        """Get ME3 configuration search paths from 'me3 info' output."""
        info = self.get_me3_info()
        if not info:
            return []
        
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
                return []

            # Parse configuration search paths
            config_paths = []
            lines = result.stdout.split('\n')
            in_config_section = False
            
            for line in lines:
                if '● Configuration search paths' in line:
                    in_config_section = True
                    continue
                elif line.startswith('●') and in_config_section:
                    # New section started, stop parsing
                    break
                elif in_config_section and ':' in line:
                    # Extract path after the number and colon
                    path_match = re.search(r'\d+:\s*(.+)', line.strip())
                    if path_match:
                        path_str = path_match.group(1).strip()
                        config_paths.append(Path(path_str))
            
            return config_paths

        except Exception as e:
            print(f"Error getting ME3 config paths: {e}")
            return []

    def get_primary_config_path(self) -> Optional[Path]:
        """
        Get the primary ME3 config path for creation when me3.toml not found.
        Windows: uses path 0 (first path)
        Linux: uses path 1 (second path, typically user config directory)
        """
        paths = self.get_me3_config_paths()
        if not paths:
            return None
        
        if sys.platform == "win32":
            # Windows: use first path (index 0)
            return paths[0] if len(paths) > 0 else None
        else:
            # Linux/Unix: use second path (index 1) if available, fallback to first
            return paths[1] if len(paths) > 1 else (paths[0] if len(paths) > 0 else None)

    def create_default_config(self) -> bool:
        """
        Create a default me3.toml file in the appropriate location.
        Returns True if successful, False otherwise.
        """
        config_path = self.get_config_creation_path()
        if not config_path:
            return False
        
        try:
            # Ensure the directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create default config content
            default_config = """# ME3 Configuration File
# This file was automatically created

[general]
# Add your configuration options here
"""
            
            # Write the config file
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            
            return True
            
        except Exception as e:
            print(f"Error creating config file at {config_path}: {e}")
            return False

    def refresh_info(self):
        """Clear cached info to force refresh on next access."""
        self._info_cache = None
        self._is_installed = None
