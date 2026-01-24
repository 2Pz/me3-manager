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


@dataclass(frozen=True)
class CommunityProfile:
    name: str
    description: str
    author: str
    download_url: str  # For folder profiles, this is the tree URL or base folder URL
    size: int
    filename: str
    image_url: str | None = None
    is_folder: bool = False
    files: list[dict] | None = None  # List of file objects for folder profiles


class CommunityService:
    def __init__(self):
        self._session = requests.Session()
        self._cache: dict[str, list[CommunityProfile]] = {}

    def fetch_profiles(
        self, game_name: str, force_refresh: bool = False
    ) -> list[CommunityProfile]:
        """
        Fetch list of .me3 profiles from the GitHub repository for a specific game.
        Uses Git Trees API to support both flat files and folder-based profiles.
        """
        # Map game_name to folder name
        game_folder = "".join(c for c in game_name.lower() if c.isalnum())
        cache_key = game_folder

        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # fetch the recursive tree
            # https://api.github.com/repos/me3-manager/me3-profiles/git/trees/main?recursive=1
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/main?recursive=1"

            log.info("Fetching community profiles tree from %s", url)
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()

            tree_data = resp.json()
            if "tree" not in tree_data:
                return []

            # Filter for items in contents/{game_folder}/
            base_path = f"contents/{game_folder}/"

            # Organize by folders to detect "Folder Profiles"
            # Map: folder_path -> list of files in that folder
            folder_contents: dict[str, list[dict]] = {}
            # List of standalone .me3 files in the root of game folder
            standalone_profiles: list[dict] = []

            for item in tree_data["tree"]:
                path = item.get("path", "")
                if not path.startswith(base_path):
                    continue

                rel_path = path[len(base_path) :]  # path relative to game folder

                if "/" not in rel_path:
                    # Item is directly in game folder
                    if rel_path.lower().endswith(".me3"):
                        standalone_profiles.append(item)
                else:
                    # Item is in a subfolder
                    top_folder = rel_path.split("/")[0]
                    if top_folder not in folder_contents:
                        folder_contents[top_folder] = []
                    folder_contents[top_folder].append(item)

            profiles = []

            # Process Standalone Profiles
            for item in standalone_profiles:
                profiles.append(self._create_profile_from_item(item, game_folder))

            # Process Folder Profiles
            for folder_name, items in folder_contents.items():
                # Check if this folder contains a .me3 file
                me3_files = [i for i in items if i["path"].endswith(".me3")]
                if not me3_files:
                    continue

                # Use the first .me3 file found as the primary profile
                # Usually there should only be one per profile folder
                main_profile_item = me3_files[0]

                # Check for image
                image_url = None
                images = [
                    i
                    for i in items
                    if i["path"].lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                ]
                if images:
                    # Construct raw content URL for the image
                    image_path = images[0]["path"]
                    image_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{image_path}"

                profile = self._create_profile_from_item(
                    main_profile_item,
                    game_folder,
                    is_folder=True,
                    folder_name=folder_name,
                    folder_items=items,
                    image_url=image_url,
                )
                profiles.append(profile)

            self._cache[cache_key] = profiles
            return profiles

        except Exception as e:
            log.error("Failed to fetch community profiles: %s", e)
            return []

    def _create_profile_from_item(
        self,
        item: dict,
        game_folder: str,
        is_folder: bool = False,
        folder_name: str | None = None,
        folder_items: list[dict] | None = None,
        image_url: str | None = None,
    ) -> CommunityProfile:
        """Helper to create CommunityProfile object and fetch description."""
        path = item["path"]
        name = Path(path).name

        # Construct raw download URL for the .me3 file to read description
        # API "url" is for the blob API, we want raw content
        raw_url = (
            f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{path}"
        )

        description = "No description provided."
        try:
            # fetch description (fast, small file)
            resp = self._session.get(raw_url, timeout=5)
            if resp.status_code == 200:
                import tomllib

                data = tomllib.loads(resp.text)
                if "game" in data and isinstance(data["game"], dict):
                    description = data["game"].get("description", description)
                else:
                    description = data.get("description", description)
        except Exception:
            pass

        return CommunityProfile(
            name=folder_name if is_folder else name,
            description=description,
            author=REPO_OWNER,
            download_url=raw_url,  # For folder, this is the main .me3 file URL, but we use 'files' for download
            size=item.get("size", 0),  # Size of the .me3 file
            filename=folder_name if is_folder else name,
            image_url=image_url,
            is_folder=is_folder,
            files=folder_items,
        )

    def download_profile(
        self, profile: CommunityProfile, destination_dir: Path
    ) -> Path | None:
        """
        Download profile to the destination directory.
        Returns the path to the downloaded .me3 file (or folder containing it).
        """
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)

            if profile.is_folder and profile.files:
                # Download all files in the folder
                log.info("Downloading folder profile %s...", profile.name)

                # Base path for the profile's folder in the repo
                # folder_items have full paths like 'contents/game/Folder/file.ext'
                # We want to download them into destination_dir/Folder/file.ext

                main_me3_path = None

                for item in profile.files:
                    file_path = item["path"]
                    # Calculate relative path from the game folder root?
                    # Actually, we want to mirror the structure inside the profile folder.

                    # item['path'] is e.g. "contents/eldenring/MyMod/script.py"
                    # We want to extract "MyMod/script.py" or just "script.py" if destination is the mod folder?
                    # The UI usually passes a temp dir as destination.

                    # Let's flatten one level?
                    # If profile.name is "MyMod", we expect files to be in "contents/eldenring/MyMod/..."
                    # We should put them in destination_dir (which might be "Downloads/MyMod")

                    full_git_path = Path(file_path)
                    # Get the part after the game folder
                    # e.g. "contents/eldenring/MyMod/script.py" -> "MyMod/script.py"
                    # But if we want to support nested folders inside the profile folder, we need to be careful.

                    # Simplified: We know the file structure relative to the root of the repo.
                    # We want to strip standard prefix "contents/{game_folder}/"
                    # But safer to just use the filename relative to the profile folder root.

                    parts = list(full_git_path.parts)
                    # Find where the profile folder starts.
                    # parts: ['contents', 'eldenring', 'MyMod', 'script.py']
                    # We want 'script.py'

                    try:
                        # Index of profile folder name
                        idx = parts.index(profile.name)
                        rel_path = Path(*parts[idx + 1 :])
                    except ValueError:
                        # Fallback
                        rel_path = Path(full_git_path.name)

                    target_file = destination_dir / profile.name / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{file_path}"

                    log.debug("Downloading %s to %s", raw_url, target_file)

                    with self._session.get(raw_url, stream=True, timeout=10) as r:
                        r.raise_for_status()
                        with open(target_file, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)

                    if file_path.endswith(".me3"):
                        main_me3_path = target_file

                return main_me3_path

            else:
                # Single file download
                target_file = destination_dir / profile.filename
                log.info("Downloading profile %s to %s", profile.name, target_file)

                with self._session.get(
                    profile.download_url, stream=True, timeout=10
                ) as r:
                    r.raise_for_status()
                    with open(target_file, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                return target_file

        except Exception as e:
            log.error("Failed to download profile %s: %s", profile.name, e)
            return None
