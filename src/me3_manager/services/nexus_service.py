"""
Nexus Mods API integration (API-key auth only for now).

Designed to be SSO-ready later without forcing a refactor:
- Auth concerns are isolated (API key today, SSO token later)
- All requests go through a single client with AUP headers
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from me3_manager import __version__

log = logging.getLogger(__name__)


NEXUS_API_BASE_URL = "https://api.nexusmods.com/v1"


class NexusError(RuntimeError):
    pass


@dataclass(frozen=True)
class NexusUser:
    user_id: int | None
    name: str | None
    email: str | None
    profile_url: str | None = None


@dataclass(frozen=True)
class NexusMod:
    game_domain: str
    mod_id: int
    name: str | None
    summary: str | None
    author: str | None
    version: str | None
    picture_url: str | None
    endorsement_count: int | None
    unique_downloads: int | None
    total_downloads: int | None


@dataclass(frozen=True)
class NexusModFile:
    file_id: int
    name: str | None
    version: str | None
    size_kb: int | None
    category_name: str | None
    category_id: int | None
    is_primary: bool | None
    uploaded_timestamp: int | None


@dataclass(frozen=True)
class NexusDownloadLink:
    url: str
    short_name: str | None = None


def _safe_int(val) -> int | None:
    try:
        if val is None:
            return None
        if isinstance(val, str):
            # Nexus sometimes returns numbers as strings; handle common separators.
            cleaned = val.strip().replace(",", "").replace("_", "").replace(" ", "")
            if cleaned == "":
                return None
            return int(cleaned)
        return int(val)
    except Exception:
        return None


def _deep_get(d: dict, *keys: str):
    """Best-effort lookup across common nesting containers."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d:
            return d.get(k)
    for container_key in ("stats", "stat", "statistics", "mod", "data"):
        sub = d.get(container_key)
        if isinstance(sub, dict):
            for k in keys:
                if k in sub:
                    return sub.get(k)
    return None


def _extract_download_counts(payload: dict) -> tuple[int | None, int | None]:
    """
    Return (unique_downloads, total_downloads) from a mod payload.
    Handles a few real-world shapes:
    - flat keys
    - nested stats dict
    - downloads dict { unique: x, total: y }
    """
    if not isinstance(payload, dict):
        return None, None

    unique = _safe_int(
        _deep_get(
            payload,
            "unique_downloads",
            "unique_dls",
            "uniqueDownloads",
            "mod_unique_downloads",
        )
    )
    total = _safe_int(
        _deep_get(
            payload,
            "total_downloads",
            "total_dls",
            "totalDownloads",
            "total_downloads_count",
            "mod_downloads",
        )
    )

    dl = payload.get("downloads")
    if isinstance(dl, dict):
        unique = unique or _safe_int(dl.get("unique") or dl.get("unique_downloads"))
        total = total or _safe_int(dl.get("total") or dl.get("total_downloads"))

    return unique, total


def _parse_size_kb(obj: dict) -> int | None:
    """
    Files endpoint has historically used different keys/units.
    Prefer explicit KB/bytes fields; otherwise apply a conservative heuristic.
    """
    if not isinstance(obj, dict):
        return None
    if obj.get("size_kb") is not None:
        return _safe_int(obj.get("size_kb"))
    if obj.get("size_in_kb") is not None:
        return _safe_int(obj.get("size_in_kb"))
    if obj.get("size_in_bytes") is not None:
        b = _safe_int(obj.get("size_in_bytes"))
        return (b // 1024) if b is not None else None
    if obj.get("size") is not None:
        n = _safe_int(obj.get("size"))
        if n is None:
            return None
        # Heuristic:
        # - Nexus sometimes returns `size` in BYTES (even when < 1MB).
        # - If the number is "large enough", assume bytes.
        # - If it's very small (e.g. 236), assume KB.
        if n >= 50_000:
            return n // 1024
        if n >= 8_192 and (n % 1024 == 0):
            return n // 1024
        return n  # treat as KB
    return None


def _safe_str(val) -> str | None:
    if val is None:
        return None
    try:
        s = str(val)
        return s if s else None
    except Exception:
        return None


def _first_url(obj) -> str | None:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in ("url", "thumbnail", "thumb", "image", "href"):
            if isinstance(obj.get(k), str):
                return obj.get(k)
    return None


class NexusService:
    """
    Thin Nexus API client with download helper.
    """

    def __init__(self, api_key: str | None, *, app_name: str = "me3-manager"):
        self._api_key = (api_key or "").strip()
        self._app_name = app_name
        self._app_version = str(__version__)
        self._session = requests.Session()

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, api_key: str | None) -> None:
        self._api_key = (api_key or "").strip()

    def _headers(self) -> dict[str, str]:
        # Per Nexus AUP request metadata requirements:
        # https://help.nexusmods.com/article/114-api-acceptable-use-policy
        headers = {
            "Accept": "application/json",
            "Application-Name": self._app_name,
            "Application-Version": self._app_version,
        }
        if self._api_key:
            headers["apikey"] = self._api_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        timeout: float = 20,
    ) -> dict:
        url = f"{NEXUS_API_BASE_URL}{path}"
        try:
            resp = self._session.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                data=data,
                timeout=timeout,
            )
        except requests.RequestException as e:
            raise NexusError(f"Network error: {e}") from e

        if resp.status_code in (401, 403):
            raise NexusError("Unauthorized: invalid or missing Nexus API key.")

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Provide a compact, user-friendly error message.
            msg = None
            try:
                j = resp.json()
                if isinstance(j, dict):
                    msg = j.get("message") or j.get("error")
            except Exception:
                msg = None
            raise NexusError(
                msg or f"HTTP {resp.status_code}: {resp.text[:200]}"
            ) from e

        try:
            j = resp.json()
            return j if isinstance(j, dict) else {"data": j}
        except Exception as e:
            raise NexusError("Invalid JSON response from Nexus API.") from e

    # --- Auth ---

    def validate_user(self) -> NexusUser:
        """Validate user and get profile info including avatar from GraphQL."""
        j = self._request("GET", "/users/validate")
        user_id = _safe_int(j.get("user_id") or j.get("id"))
        name = _safe_str(j.get("name"))
        email = _safe_str(j.get("email"))

        # Try to get avatar from GraphQL API v2
        avatar_url = self._get_user_avatar(user_id)

        return NexusUser(
            user_id=user_id,
            name=name,
            email=email,
            profile_url=avatar_url,
        )

    def _get_user_avatar(self, user_id: int | None = None) -> str | None:
        """Fetch user's avatar from Nexus GraphQL API v2."""
        if not user_id:
            return None

        graphql_url = "https://api.nexusmods.com/v2/graphql"
        # Try to query user by ID
        query = """
        query GetUser($userId: Int!) {
            user(id: $userId) {
                memberId
                name
                avatar
            }
        }
        """
        try:
            log.debug("Fetching user avatar from GraphQL API for user_id=%s", user_id)
            resp = self._session.post(
                graphql_url,
                json={"query": query, "variables": {"userId": user_id}},
                timeout=10,
            )
            log.debug("GraphQL response status: %s", resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                log.debug("GraphQL response data: %s", data)

                # Check for errors
                if "errors" in data:
                    log.debug("GraphQL errors: %s", data["errors"])
                    return None

                user_data = data.get("data", {}).get("user", {})
                if user_data:
                    avatar = _safe_str(user_data.get("avatar"))
                    log.debug("Avatar URL from GraphQL: %s", avatar)
                    return avatar
                else:
                    log.debug("No user data in response")
            else:
                log.debug("GraphQL error response: %s", resp.text[:500])
        except Exception as e:
            log.debug("Failed to fetch avatar from GraphQL: %s", e)
        return None

    # --- Mod Search (GraphQL v2) ---

    def search_mods_by_name(
        self, game_domain: str, query: str, *, count: int = 10
    ) -> list[NexusMod]:
        """
        Search mods by name using Nexus GraphQL v2 API.

        Args:
            game_domain: Game domain (e.g., "eldenring")
            query: Search query (mod name)
            count: Max results to return (default 10)

        Returns:
            List of NexusMod objects matching the search
        """
        graphql_url = "https://api.nexusmods.com/v2/graphql"
        # Build inline query - filters must be arrays
        gql_query = f"""
        query SearchMods {{
            mods(filter: {{
                name: [{{ value: "{query}", op: WILDCARD }}]
                gameDomainName: [{{ value: "{game_domain}", op: EQUALS }}]
            }}, count: {count}) {{
                nodes {{
                    modId
                    name
                    summary
                    version
                    author
                    pictureUrl
                    downloads
                    endorsements
                }}
            }}
        }}
        """

        try:
            log.debug("Searching mods: domain=%s, query=%s", game_domain, query)
            resp = self._session.post(
                graphql_url,
                json={"query": gql_query},
                timeout=20,
            )
            if resp.status_code != 200:
                log.debug("GraphQL search error: %s", resp.text[:500])
                return []

            data = resp.json()
            log.debug("GraphQL response: %s", str(data)[:1000])
            if "errors" in data:
                log.debug("GraphQL errors: %s", data["errors"])
                return []

            nodes = data.get("data", {}).get("mods", {}).get("nodes", [])
            results = []
            for node in nodes:
                results.append(
                    NexusMod(
                        game_domain=game_domain,
                        mod_id=node.get("modId"),
                        name=_safe_str(node.get("name")),
                        summary=_safe_str(node.get("summary")),
                        author=_safe_str(node.get("author")),
                        version=_safe_str(node.get("version")),
                        picture_url=_safe_str(node.get("pictureUrl")),
                        endorsement_count=_safe_int(node.get("endorsements")),
                        unique_downloads=None,
                        total_downloads=_safe_int(node.get("downloads")),
                    )
                )
            log.debug("Found %d mods", len(results))
            return results

        except Exception as e:
            log.debug("Failed to search mods: %s", e)
            return []

    def _get_game_id(self, game_domain: str) -> int | None:
        """Map game domain to numeric game ID for GraphQL v2."""
        # Common games - add more as needed
        GAME_IDS = {
            "eldenring": 4333,
            "eldenringnightreign": 7698,
            "nightreign": 7698,
            "darksouls3": 496,
            "sekiro": 2763,
            "armoredcore6": 5235,
            "darksoulsremastered": 2014,
            "darksouls": 162,
            "darksouls2": 261,
            "demonssouls": 4428,
            # Add more as needed
        }
        return GAME_IDS.get(game_domain.lower())

    # --- Mod info ---

    def get_mod(self, game_domain: str, mod_id: int) -> NexusMod:
        j = self._request("GET", f"/games/{game_domain}/mods/{mod_id}")
        # Different API revisions sometimes vary key names; be defensive.
        unique, total = _extract_download_counts(j)
        return NexusMod(
            game_domain=game_domain,
            mod_id=mod_id,
            name=_safe_str(j.get("name")),
            summary=_safe_str(j.get("summary")),
            author=_safe_str(j.get("author")),
            version=_safe_str(j.get("version")),
            picture_url=_safe_str(j.get("picture_url") or _first_url(j.get("picture"))),
            endorsement_count=_safe_int(
                _deep_get(j, "endorsement_count", "endorsements", "endorsementCount")
            ),
            unique_downloads=unique,
            total_downloads=total,
        )

    def get_mod_files(self, game_domain: str, mod_id: int) -> list[NexusModFile]:
        j = self._request("GET", f"/games/{game_domain}/mods/{mod_id}/files")
        items = j.get("files") if isinstance(j, dict) else None
        if items is None and isinstance(j.get("data"), list):
            items = j.get("data")
        if not isinstance(items, list):
            items = []

        files: list[NexusModFile] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            files.append(
                NexusModFile(
                    file_id=int(it.get("file_id") or it.get("id") or 0),
                    name=_safe_str(it.get("name")),
                    version=_safe_str(it.get("version")),
                    size_kb=_parse_size_kb(it),
                    category_name=_safe_str(
                        it.get("category_name") or it.get("category")
                    ),
                    category_id=_safe_int(
                        it.get("category_id") or it.get("categoryId")
                    ),
                    is_primary=it.get("is_primary"),
                    uploaded_timestamp=_safe_int(it.get("uploaded_timestamp")),
                )
            )

        return files

    def pick_latest_main_file(
        self, files: Iterable[NexusModFile]
    ) -> NexusModFile | None:
        """
        Heuristic 'latest' file selection:
        - Prefer primary file
        - Prefer MAIN category
        - Then newest uploaded_timestamp, then greatest file_id
        """
        fs = list(files)
        if not fs:
            return None

        def is_main(f: NexusModFile) -> bool:
            try:
                if f.category_id == 1:
                    return True
            except Exception:
                pass
            return (f.category_name or "").strip().upper() == "MAIN"

        def score(f: NexusModFile) -> tuple:
            # Prefer MAIN category for downloads as requested.
            main = 1 if is_main(f) else 0
            primary = 1 if f.is_primary else 0
            ts = f.uploaded_timestamp or 0
            fid = f.file_id or 0
            return (main, primary, ts, fid)

        return sorted(fs, key=score, reverse=True)[0]

    # --- Downloads ---

    def get_download_links(
        self, game_domain: str, mod_id: int, file_id: int
    ) -> list[NexusDownloadLink]:
        """
        Nexus has historically exposed this endpoint in slightly different forms
        across docs/versions (GET vs POST, with/without .json suffix).
        We try a small set of compatible variants to avoid "Not Found".
        """
        last_err: Exception | None = None
        candidates = [
            (
                "POST",
                f"/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link",
            ),
            (
                "GET",
                f"/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link",
            ),
            (
                "POST",
                f"/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json",
            ),
            (
                "GET",
                f"/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json",
            ),
        ]

        j: dict | None = None
        for method, path in candidates:
            try:
                j = self._request(method, path, data={})
                break
            except Exception as e:
                last_err = e
                continue

        if j is None:
            raise NexusError(
                str(last_err) if last_err else "Failed to request download link."
            )

        data = j.get("data")
        if data is None and isinstance(j.get("links"), list):
            data = j.get("links")
        if not isinstance(data, list):
            data = []
        links: list[NexusDownloadLink] = []
        for it in data:
            if not isinstance(it, dict):
                continue
            url = _safe_str(it.get("URI") or it.get("url") or it.get("uri"))
            if not url:
                continue
            links.append(
                NexusDownloadLink(url=url, short_name=_safe_str(it.get("short_name")))
            )
        return links

    def download_to_file(
        self,
        url: str,
        destination: Path,
        *,
        on_progress: Callable[[int, int | None], None] | None = None,
        check_cancel: Callable[[], bool] | None = None,
        timeout: float = 60,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._session.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            total = _safe_int(resp.headers.get("Content-Length"))
            downloaded = 0
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if check_cancel and check_cancel():
                        raise NexusError("Download cancelled by user.")
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)

    # --- Query parsing ---

    _NEXUS_MOD_URL_RE = re.compile(r"^/([^/]+)/mods/(\d+)(?:/|$)")

    def parse_mod_query(
        self, query: str, *, fallback_game_domain: str | None
    ) -> tuple[str, int]:
        """
        Accepts:
        - Mod ID: "123"
        - Mod URL: "https://www.nexusmods.com/eldenring/mods/123?tab=files"
        Returns: (game_domain, mod_id)
        """
        q = (query or "").strip()
        if not q:
            raise NexusError("Empty search query.")

        if q.isdigit():
            if not fallback_game_domain:
                raise NexusError("No game domain available for this game.")
            return fallback_game_domain, int(q)

        # Try parse as URL
        try:
            u = urlparse(q)
            m = self._NEXUS_MOD_URL_RE.match(u.path or "")
            if m:
                return m.group(1), int(m.group(2))
        except Exception:
            pass

        raise NexusError("Enter a Nexus mod ID (e.g. 123) or a Nexus mod link.")
