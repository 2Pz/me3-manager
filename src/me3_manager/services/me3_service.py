import requests


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
