"""
Service for fetching and managing community profiles from GitHub.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

REPO_OWNER = "me3-manager"
REPO_NAME = "me3-profiles"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents"


@dataclass(frozen=True)
class CommunityProfile:
    name: str
    description: str
    author: str
    download_url: str
    size: int
    filename: str
    image_url: str | None = None


class CommunityService:
    def __init__(self):
        self._session = requests.Session()
        self._cache: dict[str, list[CommunityProfile]] = {}

    def fetch_profiles(
        self, game_name: str, force_refresh: bool = False
    ) -> list[CommunityProfile]:
        """
        Fetch list of .me3 profiles from the GitHub repository for a specific game.
        Parses metadata including description from the raw file content.
        """
        # Map game_name to folder name if needed (e.g. remove spaces, lower case)
        # For now assume simple lowercase match
        folder_name = "".join(c for c in game_name.lower() if c.isalnum())

        if not force_refresh and folder_name in self._cache:
            return self._cache[folder_name]

        try:
            # User has structured repo as me3-profiles/contents/game_name
            url = f"{GITHUB_API_URL}/contents/{folder_name}"

            log.info("Fetching community profiles from %s", url)
            resp = self._session.get(url, timeout=10)

            # Handle 404 (folder doesn't exist yet) gracefully
            if resp.status_code == 404:
                self._cache[folder_name] = []
                return []

            resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, list):
                log.warning("Unexpected GitHub API response format")
                return []

            # First pass: Identify all profiles and potential images
            profile_files = []
            image_map = {}  # stemmed_name -> download_url

            for item in data:
                if not isinstance(item, dict):
                    continue

                name = item.get("name", "")
                lower_name = name.lower()
                download_url = item.get("download_url")

                if not download_url:
                    continue

                if lower_name.endswith(".me3"):
                    profile_files.append(item)
                elif lower_name.endswith((".jpg", ".jpeg", ".png", ".webp")):
                    # Store image url keyed by the file stem (filename without extension)
                    stem = Path(name).stem.lower()
                    image_map[stem] = download_url

            profiles = []
            for item in profile_files:
                name = item.get("name", "")
                download_url = item.get("download_url")

                # Fetch raw content for description
                description = ""

                try:
                    # Quick fetch of the small .me3 file
                    raw_resp = self._session.get(download_url, timeout=5)
                    if raw_resp.status_code == 200:
                        import tomllib

                        content = raw_resp.content.decode("utf-8")
                        profile_data = tomllib.loads(content)

                        if "game" in profile_data and isinstance(
                            profile_data["game"], dict
                        ):
                            description = profile_data["game"].get("description", "")
                        else:
                            description = profile_data.get("description", "")
                except Exception as e:
                    log.warning("Failed to parse profile %s: %s", name, e)
                    description = ""

                # Check for matching image file as fallback
                stem = Path(name).stem.lower()
                final_image_url = image_map.get(stem)

                profiles.append(
                    CommunityProfile(
                        name=name,
                        description=description or "No description provided.",
                        author=REPO_OWNER,
                        download_url=download_url,
                        size=item.get("size", 0),
                        filename=name,
                        image_url=final_image_url,
                    )
                )

            self._cache[folder_name] = profiles
            return profiles

        except Exception as e:
            log.error("Failed to fetch community profiles: %s", e)
            return []

    def download_profile(self, profile: CommunityProfile, destination: Path) -> bool:
        """Download a profile to the specified path."""
        try:
            log.info("Downloading profile %s to %s", profile.name, destination)
            with self._session.get(profile.download_url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(destination, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            log.error("Failed to download profile %s: %s", profile.name, e)
            return False
