import logging

import requests

log = logging.getLogger(__name__)


class Me3Service:
    """
    Thin service for ME3 version information and release assets from GitHub.
    """

    REPO_API_BASE = "https://api.github.com/repos/garyttierney/me3/releases"

    def fetch_latest_release(self) -> dict | None:
        try:
            resp = requests.get(f"{self.REPO_API_BASE}/latest", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return None

    def fetch_all_releases(self, per_page: int = 30) -> list[dict]:
        """Fetch all non-draft releases from GitHub (up to *per_page*)."""
        try:
            resp = requests.get(
                self.REPO_API_BASE,
                params={"per_page": per_page},
                timeout=15,
            )
            resp.raise_for_status()
            releases = resp.json()
            # Filter out drafts and versions older than v0.6.0
            min_ver = (0, 6, 0)
            result = []
            for r in releases:
                if r.get("draft", False):
                    continue
                tag = r.get("tag_name", "")
                ver = self._parse_version(tag)
                if ver >= min_ver:
                    result.append(r)
            return result
        except requests.RequestException as e:
            log.error("Failed to fetch all releases: %s", e)
            return []

    @staticmethod
    def _parse_version(tag: str) -> tuple[int, ...]:
        """Convert version tag (e.g. 'v0.10.0') to integer tuple for comparison."""
        clean = tag.lstrip("vV").split("-")[0]
        try:
            return tuple(int(p) for p in clean.split(".") if p.isdigit())
        except (ValueError, AttributeError):
            return (0, 0, 0)

    def fetch_release_by_tag(self, tag: str) -> dict | None:
        """Fetch a specific release by its tag name (e.g. 'v0.12.1')."""
        try:
            resp = requests.get(f"{self.REPO_API_BASE}/tags/{tag}", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.error("Failed to fetch release for tag %s: %s", tag, e)
            return None

    def get_asset_url(self, release: dict | None, name: str) -> str | None:
        if not release:
            return None
        for asset in release.get("assets", []) or []:
            if asset.get("name") == name:
                return asset.get("browser_download_url")
        return None

    def get_latest_version_tag(self, release: dict | None) -> str | None:
        if not release:
            return None
        return release.get("tag_name")
