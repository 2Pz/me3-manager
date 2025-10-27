"""Service for checking me3-manager app updates from GitHub releases."""

import logging
import re

import requests

log = logging.getLogger(__name__)


class AppUpdateChecker:
    """Check for me3-manager updates from GitHub releases."""

    GITHUB_API_URL = "https://api.github.com/repos/2Pz/me3-manager/releases/latest"

    def __init__(self, current_version: str):
        """
        Initialize the update checker.

        Args:
            current_version: Current app version (e.g., "1.1.9" or "v1.1.9")
        """
        self.current_version = self._normalize_version(current_version)

    @staticmethod
    def _normalize_version(version: str) -> str:
        """
        Normalize version string by removing 'v' prefix.

        Args:
            version: Version string (e.g., "1.1.9" or "v1.1.9")

        Returns:
            Normalized version without 'v' prefix
        """
        if not version:
            return ""
        return version.lstrip("v")

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        """
        Parse version string into tuple of integers for comparison.

        Args:
            version: Version string (e.g., "1.1.9")

        Returns:
            Tuple of version numbers (e.g., (1, 1, 9))
        """
        try:
            # Extract version numbers using regex
            match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
            if match:
                return tuple(int(x) for x in match.groups())
        except (ValueError, AttributeError):
            pass
        return (0, 0, 0)

    def check_for_updates(self) -> dict:
        """
        Check for available updates from GitHub releases.

        Returns:
            Dictionary with update information:
            {
                "update_available": bool,
                "latest_version": str,
                "current_version": str,
                "download_url": str,
                "error": str or None
            }
        """
        result = {
            "update_available": False,
            "latest_version": None,
            "current_version": self.current_version,
            "download_url": "https://www.nexusmods.com/eldenringnightreign/mods/213?tab=files",
            "error": None,
        }

        try:
            response = requests.get(self.GITHUB_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            tag_name = data.get("tag_name")
            if not tag_name:
                result["error"] = "No tag_name found in GitHub response"
                return result

            # Normalize the latest version
            latest_version = self._normalize_version(tag_name)
            result["latest_version"] = latest_version

            # Compare versions
            current_tuple = self._parse_version(self.current_version)
            latest_tuple = self._parse_version(latest_version)

            if latest_tuple > current_tuple:
                result["update_available"] = True
                log.info(
                    "Update available: %s -> %s", self.current_version, latest_version
                )
            else:
                log.debug(
                    "No update available. Current: %s, Latest: %s",
                    self.current_version,
                    latest_version,
                )

        except requests.RequestException as e:
            result["error"] = f"Network error: {e}"
            log.error("Failed to check for updates: %s", e)
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            log.error("Unexpected error checking for updates: %s", e)

        return result
