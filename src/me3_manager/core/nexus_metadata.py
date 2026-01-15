"""
Persist Nexus-related metadata for installed mods.

Goals:
- Track which local mods correspond to a Nexus mod/file
- Enable update checks + upgrades later
- Keep storage local (never store user API keys remotely)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TrackedNexusMod:
    # Local identifier (we use the mod's path string as shown in the UI list)
    local_mod_path: str
    # Nexus identifiers
    game_domain: str
    mod_id: int
    file_id: int | None = None
    # Cached display values (optional)
    mod_name: str | None = None
    custom_name: str | None = None
    mod_version: str | None = None
    file_name: str | None = None
    file_version: str | None = None
    file_size_kb: int | None = None
    file_category: str | None = None
    file_uploaded_timestamp: int | None = None
    # Source/reference
    nexus_url: str | None = None
    installed_at: str | None = None  # ISO8601
    cached_at: str | None = None  # ISO8601 - last time we refreshed from Nexus
    # Cached mod details (optional, for richer UI + offline display)
    mod_author: str | None = None
    mod_endorsements: int | None = None
    # Keep both metrics; Nexus displays both "Unique DLs" and "Total DLs".
    mod_unique_downloads: int | None = None
    mod_total_downloads: int | None = None
    mod_picture_url: str | None = None
    mod_summary: str | None = None
    # User-specified mod root path (for mods with unknown structure)
    # This is a relative path within the extracted archive to use as the mod root
    mod_root_path: str | None = None
    # Update-check cache (set by "Check update" and automatic startup checks)
    update_available: bool | None = None
    update_latest_file_id: int | None = None
    update_latest_version: str | None = None
    update_checked_at: str | None = None  # ISO8601
    update_error: str | None = None

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()


class NexusMetadataManager:
    """
    Stores metadata under the shared ME3 profiles root:
      <me3_config_profiles_dir>/.me3_manager/<game_name>/metadata.json

    Legacy locations will be auto-migrated if found:
    - <mods_dir>/.me3_manager/<game_name>/metadata.json (older per-mods-dir format)
    - <mods_dir>/.me3_manager/nexus/metadata/*.json (old per-domain files)
    - <me3_config_profiles_dir>/.me3_manager/nexus/metadata/*.json
    - <me3_config_profiles_dir>/nexus/metadata/*.json
    """

    def __init__(
        self,
        storage_root: Path,
        game_name: str,
        *,
        legacy_roots: list[Path] | None = None,
    ):
        self.storage_root = Path(storage_root)
        self.game_name = str(game_name)
        self.legacy_roots = [Path(p) for p in (legacy_roots or [])]
        # In-memory cache for search results (never saved to disk)
        self._runtime_cache: dict[str, TrackedNexusMod] = {}

    def _legacy_base_dir(self) -> Path:
        # Kept for backward compatibility with older logic; not used directly.
        return self.storage_root / "nexus" / "metadata"

    def _game_dir(self) -> Path:
        safe_game = "".join(
            ch for ch in self.game_name if ch.isalnum() or ch in ("_", "-", " ")
        ).strip()
        safe_game = safe_game.replace(" ", "_") or "game"
        p = self.storage_root / ".me3_manager" / safe_game
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_dirs(self) -> None:
        """Ensure the metadata directory exists on disk."""
        try:
            self._game_dir()
        except Exception:
            pass

    def _metadata_file(self) -> Path:
        return self._game_dir() / "metadata.json"

    def _legacy_candidates_for(self, filename: str) -> list[Path]:
        candidates: list[Path] = []
        for root in self.legacy_roots:
            candidates.append(root / ".me3_manager" / "nexus" / "metadata" / filename)
            candidates.append(root / "nexus" / "metadata" / filename)
        return candidates

    def _legacy_domain_file_in_mods_dir(self, game_domain: str) -> Path:
        safe = "".join(
            ch for ch in str(game_domain).lower() if ch.isalnum() or ch in ("_", "-")
        )
        return (
            self.storage_root / ".me3_manager" / "nexus" / "metadata" / f"{safe}.json"
        )

    def load_game(self, game_domain: str) -> dict[str, TrackedNexusMod]:
        # Single file per game (ignore domain for file selection; store domain inside records)
        path = self._metadata_file()
        if not path.exists():
            # Migrate older per-mods-dir per-game file if found in any legacy roots.
            for root in self.legacy_roots:
                try:
                    safe_game = self._game_dir().name
                    old = Path(root) / ".me3_manager" / safe_game / "metadata.json"
                    if old.exists():
                        self.ensure_dirs()
                        old.replace(path)
                        break
                except Exception:
                    continue

            # Migrate old domain file for this game if present (mods_dir legacy)
            legacy_mods = self._legacy_domain_file_in_mods_dir(game_domain)
            if legacy_mods.exists():
                try:
                    self.ensure_dirs()
                    legacy_mods.replace(path)
                except Exception:
                    path = legacy_mods
            else:
                # Try config_root legacy locations
                for legacy in self._legacy_candidates_for(
                    f"{''.join(ch for ch in str(game_domain).lower() if ch.isalnum() or ch in ('_', '-'))}.json"
                ):
                    if not legacy.exists():
                        continue
                    try:
                        self.ensure_dirs()
                        legacy.replace(path)
                        break
                    except Exception:
                        path = legacy
                        break
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            log.warning("Failed to load Nexus metadata %s: %s", path, e)
            return {}

        if not isinstance(raw, dict):
            return {}

        result: dict[str, TrackedNexusMod] = {}
        dirty = False

        for local_path, data in raw.items():
            # Cleanup any legacy cache keys (starting with __cache__:) to prevent duplicates
            if str(local_path).startswith("__cache__:"):
                dirty = True
                continue

            if not isinstance(data, dict):
                continue
            try:
                result[local_path] = TrackedNexusMod(
                    local_mod_path=str(local_path),
                    game_domain=str(data.get("game_domain") or game_domain),
                    mod_id=int(data.get("mod_id") or 0),
                    file_id=(
                        int(data["file_id"])
                        if data.get("file_id") is not None
                        else None
                    ),
                    mod_name=data.get("mod_name"),
                    mod_version=data.get("mod_version"),
                    file_name=data.get("file_name"),
                    file_version=data.get("file_version"),
                    file_size_kb=(
                        int(data["file_size_kb"])
                        if data.get("file_size_kb") is not None
                        else None
                    ),
                    file_category=data.get("file_category"),
                    file_uploaded_timestamp=(
                        int(data["file_uploaded_timestamp"])
                        if data.get("file_uploaded_timestamp") is not None
                        else None
                    ),
                    nexus_url=data.get("nexus_url"),
                    installed_at=data.get("installed_at"),
                    cached_at=data.get("cached_at"),
                    mod_author=data.get("mod_author"),
                    mod_endorsements=(
                        int(data["mod_endorsements"])
                        if data.get("mod_endorsements") is not None
                        else None
                    ),
                    mod_unique_downloads=(
                        int(data["mod_unique_downloads"])
                        if data.get("mod_unique_downloads") is not None
                        else None
                    ),
                    mod_total_downloads=(
                        int(data["mod_total_downloads"])
                        if data.get("mod_total_downloads") is not None
                        else None
                    ),
                    mod_picture_url=data.get("mod_picture_url"),
                    mod_summary=data.get("mod_summary"),
                    mod_root_path=data.get("mod_root_path"),
                    update_available=(
                        bool(data["update_available"])
                        if data.get("update_available") is not None
                        else None
                    ),
                    update_latest_file_id=(
                        int(data["update_latest_file_id"])
                        if data.get("update_latest_file_id") is not None
                        else None
                    ),
                    update_latest_version=data.get("update_latest_version"),
                    update_checked_at=data.get("update_checked_at"),
                    update_error=data.get("update_error"),
                    custom_name=data.get("custom_name"),
                )
            except Exception:
                continue

        if dirty:
            # We found legacy cache entries, clean them up immediately
            self.save_game(game_domain, result)

        return result

    def remove_mod_metadata(self, local_mod_path: str) -> bool:
        """
        Remove metadata for a specific local mod path.
        Also removes any associated cache entry for the same mod ID to ensure clean removal.
        Returns True if metadata was found and removed, False otherwise.
        """
        # We don't necessarily know the game domain, but usually we're working within a specific game context.
        # Try finding it in the current game's file first.
        path = self._metadata_file()
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return False

        if not isinstance(raw, dict):
            return False

        # Check if the key exists
        if local_mod_path in raw:
            # capture mod details before deletion to clean up cache
            entry = raw[local_mod_path]
            mod_id = entry.get("mod_id")
            game_domain = entry.get("game_domain")

            del raw[local_mod_path]

            # Also remove corresponding runtime cache entry if it exists
            if mod_id and game_domain:
                cache_key = self.cache_key(str(game_domain), int(mod_id))
                if cache_key in self._runtime_cache:
                    del self._runtime_cache[cache_key]

            try:
                self.ensure_dirs()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(raw, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                log.warning(
                    "Failed to save Nexus metadata after removal %s: %s", path, e
                )
                return False

        return False

    def save_game(self, game_domain: str, items: dict[str, TrackedNexusMod]) -> None:
        path = self._metadata_file()

        # Only save items that are NOT cache keys
        payload = {
            k: asdict(v) for k, v in items.items() if not k.startswith("__cache__:")
        }

        try:
            self.ensure_dirs()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("Failed to save Nexus metadata %s: %s", path, e)

    def set_update_check_result(
        self,
        *,
        local_mod_path: str,
        update_available: bool,
        latest_file_id: int | None,
        latest_version: str | None,
        error: str | None = None,
    ) -> bool:
        """
        Persist a cached update-check result for an installed mod.
        Returns True if the mod was found and updated.
        """
        try:
            self.ensure_dirs()
            items = self.load_game("unknown")
            tracked = items.get(local_mod_path)
            if not tracked:
                return False

            tracked.update_checked_at = TrackedNexusMod.now_iso()
            tracked.update_error = error
            tracked.update_available = bool(update_available)

            if tracked.update_available:
                tracked.update_latest_file_id = (
                    int(latest_file_id) if latest_file_id else None
                )
                tracked.update_latest_version = latest_version
            else:
                tracked.update_latest_file_id = None
                tracked.update_latest_version = None

            # Save to this game's file (domain is stored inside record; file selection ignores it)
            self.save_game(tracked.game_domain or "unknown", items)
            return True
        except Exception:
            return False

    def set_update_check_error(self, *, local_mod_path: str, error: str) -> bool:
        """Persist an update-check error without overwriting existing availability state."""
        try:
            self.ensure_dirs()
            items = self.load_game("unknown")
            tracked = items.get(local_mod_path)
            if not tracked:
                return False
            tracked.update_checked_at = TrackedNexusMod.now_iso()
            tracked.update_error = error
            self.save_game(tracked.game_domain or "unknown", items)
            return True
        except Exception:
            return False

    def get_for_local_mod(
        self, game_domain: str, local_mod_path: str
    ) -> TrackedNexusMod | None:
        items = self.load_game(game_domain)
        return items.get(local_mod_path)

    def find_for_local_mod(self, local_mod_path: str) -> TrackedNexusMod | None:
        """Find a tracked mod by local path within this game's metadata file."""
        try:
            # We don't know the domain for sure; try loading by the current game's domain first,
            # then fall back to a best-effort load (empty domain).
            items = self.load_game("unknown")
            if local_mod_path in items:
                return items[local_mod_path]
        except Exception:
            return None
        return None

    @staticmethod
    def cache_key(game_domain: str, mod_id: int) -> str:
        return f"__cache__:{game_domain}:{int(mod_id)}"

    def _find_installed_mod_key(
        self, items: dict[str, TrackedNexusMod], game_domain: str, mod_id: int
    ) -> str | None:
        """Find the key of an installed mod by ID, skipping cache entries."""
        target_mod_id = int(mod_id)
        for key, mod in items.items():
            if key.startswith("__cache__:"):
                continue
            if mod.mod_id == target_mod_id and mod.game_domain == game_domain:
                return key
        return None

    def _invalidate_runtime_cache(self, game_domain: str, mod_id: int) -> None:
        """Remove a mod from the runtime cache if present."""
        cache_key = self.cache_key(game_domain, mod_id)
        self._runtime_cache.pop(cache_key, None)

    def get_cached_for_mod(
        self, game_domain: str, mod_id: int
    ) -> TrackedNexusMod | None:
        """
        Get metadata for a mod.
        Prioritizes an installed mod entry if one exists for this ID.
        Falls back to the temporary runtime cache entry.
        """
        items = self.load_game(game_domain)

        # Search for installed mod with this ID
        key = self._find_installed_mod_key(items, game_domain, mod_id)
        if key:
            return items[key]

        # Fallback to runtime cache key
        return self._runtime_cache.get(self.cache_key(game_domain, mod_id))

    def upsert_cache_for_mod(
        self,
        *,
        game_domain: str,
        mod_id: int,
        local_mod_path: str | None = None,
        mod_name: str | None = None,
        mod_version: str | None = None,
        mod_author: str | None = None,
        mod_endorsements: int | None = None,
        mod_unique_downloads: int | None = None,
        mod_total_downloads: int | None = None,
        mod_picture_url: str | None = None,
        mod_summary: str | None = None,
        file_id: int | None = None,
        file_name: str | None = None,
        file_version: str | None = None,
        file_size_kb: int | None = None,
        file_category: str | None = None,
        file_uploaded_timestamp: int | None = None,
        nexus_url: str | None = None,
        custom_name: str | None = None,
    ) -> None:
        """
        Update cached details for a mod.
        If local_mod_path is provided, it updates/creates the installed record (on disk).
        Otherwise:
          - If the mod is already installed (found by ID), update its record (on disk).
          - If not installed, update the runtime cache (in memory only).
        """
        self.ensure_dirs()
        items = self.load_game(game_domain)

        target_key = None
        existing = None

        if local_mod_path:
            target_key = local_mod_path
            existing = items.get(local_mod_path)
            # When explicitly providing path (e.g. after install), we treat it as installed
            is_installed_mod = True
        else:
            # Find existing installed record by ID
            target_key = self._find_installed_mod_key(items, game_domain, mod_id)
            existing = items.get(target_key) if target_key else None

            is_installed_mod = existing is not None

            if not is_installed_mod:
                # Use runtime cache
                cache_key = self.cache_key(game_domain, mod_id)
                target_key = cache_key
                existing = self._runtime_cache.get(cache_key)

        tracked = existing or TrackedNexusMod(
            local_mod_path=target_key,
            game_domain=game_domain,
            mod_id=int(mod_id),
        )
        prev_file_id = tracked.file_id

        # Ensure ID/Domain are set (in case of new object)
        tracked.game_domain = game_domain
        tracked.mod_id = int(mod_id)

        # If we are effectively installing/updating a real mod, ensure installed_at is set
        if is_installed_mod and not tracked.installed_at:
            tracked.installed_at = TrackedNexusMod.now_iso()

        # Always update cached_at for freshness
        tracked.cached_at = TrackedNexusMod.now_iso()

        if nexus_url:
            tracked.nexus_url = nexus_url

        # Preserve custom name if not explicitly cleared/set (it shouldn't be effectively cleared by update checks)
        if custom_name is not None:
            tracked.custom_name = custom_name
        # If we are updating an existing record but didn't pass a custom name, keep the old one
        elif existing and hasattr(existing, "custom_name"):
            tracked.custom_name = existing.custom_name

        # Mod fields
        if mod_name is not None:
            tracked.mod_name = mod_name
        if mod_version is not None:
            tracked.mod_version = mod_version
        if mod_author is not None:
            tracked.mod_author = mod_author
        if mod_endorsements is not None:
            tracked.mod_endorsements = mod_endorsements
        if mod_unique_downloads is not None:
            tracked.mod_unique_downloads = mod_unique_downloads
        if mod_total_downloads is not None:
            tracked.mod_total_downloads = mod_total_downloads
        if mod_picture_url is not None:
            tracked.mod_picture_url = mod_picture_url
        if mod_summary is not None:
            tracked.mod_summary = mod_summary

        # File fields
        if file_id is not None:
            tracked.file_id = int(file_id)
        if file_name is not None:
            tracked.file_name = file_name
        if file_version is not None:
            tracked.file_version = file_version
        if file_size_kb is not None:
            tracked.file_size_kb = int(file_size_kb)
        if file_category is not None:
            tracked.file_category = file_category
        if file_uploaded_timestamp is not None:
            tracked.file_uploaded_timestamp = int(file_uploaded_timestamp)

        # If we just installed/updated a file (file_id written), any previously cached
        # "update available" state should be cleared so the UI badge disappears.
        if (
            is_installed_mod
            and (file_id is not None)
            and (tracked.file_id != prev_file_id)
        ):
            tracked.update_available = False
            tracked.update_latest_file_id = None
            tracked.update_latest_version = None
            tracked.update_error = None
            tracked.update_checked_at = TrackedNexusMod.now_iso()

        if is_installed_mod:
            items[target_key] = tracked
            # Cleanup duplicate cache entry from runtime cache if we just promoted it
            self._invalidate_runtime_cache(game_domain, mod_id)

            self.save_game(game_domain, items)
        else:
            self._runtime_cache[target_key] = tracked

    def link_local_mod(
        self,
        *,
        game_domain: str,
        local_mod_path: str,
        mod_id: int,
        nexus_url: str | None = None,
        mod_name: str | None = None,
    ) -> None:
        items = self.load_game(game_domain)
        existing = items.get(local_mod_path)
        tracked = existing or TrackedNexusMod(
            local_mod_path=local_mod_path,
            game_domain=game_domain,
            mod_id=mod_id,
            installed_at=TrackedNexusMod.now_iso(),
            nexus_url=nexus_url,
            mod_name=mod_name,
        )
        tracked.game_domain = game_domain
        tracked.mod_id = int(mod_id)
        if nexus_url:
            tracked.nexus_url = nexus_url
        if mod_name:
            tracked.mod_name = mod_name
        if not tracked.installed_at:
            tracked.installed_at = TrackedNexusMod.now_iso()

        # Preserve custom name if re-linking
        if existing and existing.custom_name:
            tracked.custom_name = existing.custom_name

        # If we have enough info to display, treat this as cached too.

        if mod_name and not tracked.cached_at:
            tracked.cached_at = TrackedNexusMod.now_iso()

        items[local_mod_path] = tracked

        # Cleanup any cache duplicate from runtime cache
        self._invalidate_runtime_cache(game_domain, mod_id)

        self.save_game(game_domain, items)

    def set_mod_root_path(
        self,
        *,
        game_domain: str,
        mod_id: int,
        mod_root_path: str | None,
    ) -> None:
        """Set the user-specified folder path rule for a mod."""
        items = self.load_game(game_domain)
        # Try finding installed mod first
        target_key = self._find_installed_mod_key(items, game_domain, mod_id)

        if target_key:
            existing = items.get(target_key)
            if existing:
                existing.mod_root_path = mod_root_path
                items[target_key] = existing
                self.save_game(game_domain, items)
        else:
            # If not installed, we can't really save a "rule" persistently if we don't allow cache files.
            # But the user might be setting a rule BEFORE install.
            # In 'strict' mode, we have to decide. For now, let's allow saving this rule as a special case?
            # Or perhaps we should just allow it in runtime cache and hope they install soon?
            # User request: "strictly contain only installed mods".
            # So we should probably NOT save this to disk unless installed.

            # HOWEVER, `set_mod_root_path` is usually called during install wizard or similar.
            # Let's put it in runtime cache.
            cache_key = self.cache_key(game_domain, mod_id)
            existing = self._runtime_cache.get(cache_key)
            if existing:
                existing.mod_root_path = mod_root_path
                self._runtime_cache[cache_key] = existing
            else:
                tracked = TrackedNexusMod(
                    local_mod_path=cache_key,
                    game_domain=game_domain,
                    mod_id=int(mod_id),
                    mod_root_path=mod_root_path,
                )
                self._runtime_cache[cache_key] = tracked

    def get_mod_root_path(self, game_domain: str, mod_id: int) -> str | None:
        """Get the user-specified folder path rule for a mod."""
        cached = self.get_cached_for_mod(game_domain, mod_id)
        return cached.mod_root_path if cached else None

    def set_mod_custom_name(self, local_mod_path: str, name: str | None) -> None:
        """Set a user-defined custom name for a mod."""
        # Note: We use "unknown" or "local" game domain if not found, since we are working by local path
        try:
            items = self.load_game("unknown")
            if local_mod_path in items:
                items[local_mod_path].custom_name = name
                self.save_game(items[local_mod_path].game_domain or "unknown", items)
            else:
                # Create a new local-only entry
                items[local_mod_path] = TrackedNexusMod(
                    local_mod_path=local_mod_path,
                    game_domain="local",
                    mod_id=0,
                    custom_name=name,
                    installed_at=TrackedNexusMod.now_iso(),
                )
                self.save_game("local", items)
        except Exception as e:
            log.warning("Failed to set custom name for %s: %s", local_mod_path, e)
