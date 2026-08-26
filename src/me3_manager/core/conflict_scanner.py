"""
Conflict Scanner for ME3 Manager.
Detects file-level overlaps across enabled mods for FromSoftware games.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from me3_manager.utils.path_utils import PathUtils

log = logging.getLogger(__name__)

# Files to ignore during conflict scanning
IGNORED_FILENAMES = {
    ".nexus_metadata.json",
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    "me3.toml",
    ".gitignore",
    ".git",
}

IGNORED_EXTENSIONS = {
    ".bak",
    ".tmp",
    ".old",
}


def categorize_relative_path(rel_path: str) -> str:
    """
    Categorizes a relative mod file path directly by its folder name (e.g. 'chr', 'event', 'parts')
    or 'regulation.bin'.

    Args:
        rel_path: Relative path using forward slashes (e.g. 'chr/c0000.chrbnd.dcx')

    Returns:
        Folder name like 'chr', 'event', 'parts', 'msg', 'regulation.bin', etc.
    """
    normalized = rel_path.lower().replace("\\", "/")
    parts = normalized.split("/")

    # Check regulation
    if parts[0] == "regulation.bin" or parts[0].startswith("regulation.bin"):
        return "regulation.bin"

    if len(parts) > 1 and parts[0]:
        return parts[0]

    return "other"


@dataclass
class ModFileRecord:
    """Information about a single file provided by a mod."""

    mod_name: str
    mod_path: str  # String representation of mod folder/entry
    relative_path: str  # Original case relative path (e.g. 'chr/c0000.chrbnd.dcx')
    full_path: Path
    priority_rank: int  # 0 is highest priority (winner)
    size_bytes: int
    mtime: float


@dataclass
class FileConflict:
    """Represents a conflict on a single relative file path between two or more mods."""

    relative_path: str  # e.g. 'chr/c0000.chrbnd.dcx'
    category: str  # Folder name e.g. 'chr', 'regulation.bin', 'parts'
    winning_mod_name: str
    winning_mod_path: str
    winning_file_path: Path
    winning_file_size: int
    winning_file_mtime: float
    winning_priority_rank: int
    overwritten_records: list[ModFileRecord] = field(default_factory=list)

    @property
    def total_mods_involved(self) -> int:
        return 1 + len(self.overwritten_records)

    @property
    def mod_folders(self) -> list[tuple[str, Path]]:
        """Returns list of (mod_name, folder_path) for all mods involved in this conflict."""
        return [(self.winning_mod_name, self.winning_file_path.parent)] + [
            (rec.mod_name, rec.full_path.parent) for rec in self.overwritten_records
        ]


@dataclass
class ModConflictSummary:
    """Summary of conflicts for a specific mod."""

    mod_name: str
    mod_path: str
    priority_rank: int
    overwrites_count: int = 0  # Number of files where this mod wins over others
    overwritten_by_count: int = 0  # Number of files where this mod is shadowed/loses
    conflicting_files: list[FileConflict] = field(default_factory=list)


@dataclass
class ConflictScanResult:
    """Complete scan results across all enabled mods for a game profile."""

    game_name: str
    has_conflicts: bool
    total_conflicts: int
    conflicts: list[FileConflict] = field(default_factory=list)
    conflicts_by_category: dict[str, list[FileConflict]] = field(default_factory=dict)
    conflicts_by_mod: dict[str, ModConflictSummary] = field(default_factory=dict)
    winning_mods_count: dict[str, int] = field(default_factory=dict)
    overwritten_mods_count: dict[str, int] = field(default_factory=dict)


class ConflictScannerService:
    """
    Service for scanning and detecting file conflicts across enabled mods.
    Maintains a lightweight timestamp cache for high-performance rescanning.
    """

    def __init__(self):
        # Cache mapping: mod_dir_path -> (mtime, list[ModFileRecord])
        self._dir_cache: dict[
            str, tuple[float, list[tuple[str, Path, int, float]]]
        ] = {}

    def clear_cache(self):
        """Clears the file scan cache."""
        self._dir_cache.clear()

    def _scan_mod_directory(
        self, mod_name: str, mod_path_str: str, mod_dir: Path, priority_rank: int
    ) -> list[ModFileRecord]:
        """
        Recursively scans a mod directory for asset files with timestamp caching.
        """
        if not mod_dir.is_dir():
            return []

        try:
            current_mtime = mod_dir.stat().st_mtime
        except Exception:
            current_mtime = 0.0

        dir_key = str(mod_dir.resolve())
        cached_entry = self._dir_cache.get(dir_key)

        file_tuples: list[tuple[str, Path, int, float]] = []

        if cached_entry and cached_entry[0] == current_mtime:
            file_tuples = cached_entry[1]
        else:
            file_tuples = []
            for root, _dirs, files in os.walk(mod_dir):
                root_path = Path(root)
                for file_name in files:
                    lower_name = file_name.lower()
                    if lower_name in IGNORED_FILENAMES:
                        continue
                    if any(lower_name.endswith(ext) for ext in IGNORED_EXTENSIONS):
                        continue

                    full_path = root_path / file_name
                    try:
                        rel_path = full_path.relative_to(mod_dir).as_posix()
                        stat = full_path.stat()
                        file_tuples.append(
                            (rel_path, full_path, stat.st_size, stat.st_mtime)
                        )
                    except Exception as e:
                        log.debug("Error scanning file %s: %s", full_path, e)

            self._dir_cache[dir_key] = (current_mtime, file_tuples)

        # Build ModFileRecords with priority rank
        records: list[ModFileRecord] = []
        for rel_path, full_path, size_bytes, mtime in file_tuples:
            records.append(
                ModFileRecord(
                    mod_name=mod_name,
                    mod_path=mod_path_str,
                    relative_path=rel_path,
                    full_path=full_path,
                    priority_rank=priority_rank,
                    size_bytes=size_bytes,
                    mtime=mtime,
                )
            )

        return records

    def scan_entries(
        self,
        mod_entries: list[tuple[str, str, Path, int]],
        game_name: str = "",
    ) -> ConflictScanResult:
        """
        Scan a list of mod entries for conflicts.

        Args:
            mod_entries: List of (mod_name, mod_path_str, mod_dir_path, priority_rank)
                         where priority_rank=0 is highest priority (winner).
            game_name: Optional name of the game for display.

        Returns:
            ConflictScanResult containing detected conflicts.
        """
        # Map: lowercase_relative_path -> list[ModFileRecord]
        file_map: dict[str, list[ModFileRecord]] = {}

        for mod_name, mod_path_str, mod_dir, priority_rank in mod_entries:
            records = self._scan_mod_directory(
                mod_name, mod_path_str, mod_dir, priority_rank
            )
            for record in records:
                key = record.relative_path.lower().replace("\\", "/")
                if key not in file_map:
                    file_map[key] = []
                file_map[key].append(record)

        conflicts: list[FileConflict] = []
        conflicts_by_category: dict[str, list[FileConflict]] = defaultdict(list)

        mod_summaries: dict[str, ModConflictSummary] = {}
        for mod_name, mod_path_str, _, priority_rank in mod_entries:
            mod_summaries[mod_path_str] = ModConflictSummary(
                mod_name=mod_name,
                mod_path=mod_path_str,
                priority_rank=priority_rank,
            )

        winning_mods_count: dict[str, int] = {}
        overwritten_mods_count: dict[str, int] = {}

        for _key, records in file_map.items():
            if len(records) > 1:
                # Multiple mods provide this file -> Conflict!
                sorted_records = sorted(records, key=lambda r: r.priority_rank)
                winner = sorted_records[0]
                losers = sorted_records[1:]

                category = categorize_relative_path(winner.relative_path)

                conflict = FileConflict(
                    relative_path=winner.relative_path,
                    category=category,
                    winning_mod_name=winner.mod_name,
                    winning_mod_path=winner.mod_path,
                    winning_file_path=winner.full_path,
                    winning_file_size=winner.size_bytes,
                    winning_file_mtime=winner.mtime,
                    winning_priority_rank=winner.priority_rank,
                    overwritten_records=losers,
                )

                conflicts.append(conflict)
                conflicts_by_category[category].append(conflict)

                # Update mod summaries
                winner_summary = mod_summaries.get(winner.mod_path)
                if winner_summary:
                    winner_summary.overwrites_count += 1
                    winner_summary.conflicting_files.append(conflict)

                winning_mods_count[winner.mod_name] = (
                    winning_mods_count.get(winner.mod_name, 0) + 1
                )

                for loser in losers:
                    loser_summary = mod_summaries.get(loser.mod_path)
                    if loser_summary:
                        loser_summary.overwritten_by_count += 1
                        loser_summary.conflicting_files.append(conflict)
                    overwritten_mods_count[loser.mod_name] = (
                        overwritten_mods_count.get(loser.mod_name, 0) + 1
                    )

        # Sort conflicts: regulation.bin first, then alphabetical folder, then other
        def _sort_key(c: FileConflict):
            if c.category == "regulation.bin":
                return (0, c.relative_path.lower())
            elif c.category == "other":
                return (2, c.relative_path.lower())
            else:
                return (1, c.category, c.relative_path.lower())

        conflicts.sort(key=_sort_key)

        return ConflictScanResult(
            game_name=game_name,
            has_conflicts=len(conflicts) > 0,
            total_conflicts=len(conflicts),
            conflicts=conflicts,
            conflicts_by_category=dict(conflicts_by_category),
            conflicts_by_mod=mod_summaries,
            winning_mods_count=winning_mods_count,
            overwritten_mods_count=overwritten_mods_count,
        )

    def scan_game_profile(
        self,
        game_name: str,
        config_manager: Any,
        mod_infos: dict[str, Any] | None = None,
    ) -> ConflictScanResult:
        """
        Scans enabled mods for a specific game and active profile.

        Args:
            game_name: Name of the game (e.g. 'Elden Ring')
            config_manager: ConfigFacade instance
            mod_infos: Optional dict of ModInfo objects (if already loaded)

        Returns:
            ConflictScanResult containing all detected conflicts.
        """
        mods_dir = config_manager.get_mods_dir(game_name)
        if not mods_dir or not mods_dir.is_dir():
            return ConflictScanResult(
                game_name=game_name,
                has_conflicts=False,
                total_conflicts=0,
            )

        profile_path = config_manager.get_profile_path(game_name)
        config_data = config_manager._parse_toml_config(profile_path)
        packages = config_data.get("packages", [])

        # Build load order priority mapping:
        load_order_map: dict[str, int] = {}
        for rank, pkg in enumerate(packages):
            if isinstance(pkg, dict):
                pkg_id = pkg.get("id", "")
                pkg_path = pkg.get("path") or pkg.get("source") or ""
                if pkg_id:
                    load_order_map[pkg_id.lower()] = rank
                if pkg_path:
                    load_order_map[PathUtils.normalize(pkg_path).lower()] = rank

        # Collect enabled mods
        mod_entries: list[tuple[str, str, Path, int]] = []

        if mod_infos:
            for mod_path_str, mod_info in mod_infos.items():
                if (
                    getattr(mod_info, "status", None)
                    and str(mod_info.status.value) != "enabled"
                ):
                    continue

                mod_type = getattr(mod_info, "mod_type", None)
                if mod_type and getattr(mod_type, "value", str(mod_type)) == "dll":
                    continue

                p = Path(mod_path_str)
                if not p.is_absolute():
                    p = mods_dir / p

                if p.is_dir():
                    norm_path = PathUtils.normalize(mod_path_str).lower()
                    mod_name_key = mod_info.name.lower()
                    rank = load_order_map.get(
                        mod_name_key, load_order_map.get(norm_path, 9999)
                    )
                    mod_entries.append((mod_info.name, mod_path_str, p, rank))
        else:
            for rank, pkg in enumerate(packages):
                if isinstance(pkg, dict) and pkg.get("enabled", True) is not False:
                    pkg_id = pkg.get("id", "mod")
                    pkg_path = pkg.get("path") or pkg.get("source") or pkg_id
                    p = Path(pkg_path)
                    if not p.is_absolute():
                        p = mods_dir / p
                    if p.is_dir():
                        mod_entries.append((pkg_id, pkg_path, p, rank))

        # Sort mod entries by priority rank
        mod_entries.sort(key=lambda item: item[3])

        # Normalize priority ranks from 0 to N
        normalized_entries: list[tuple[str, str, Path, int]] = []
        for idx, (name, path_str, path_obj, _) in enumerate(mod_entries):
            normalized_entries.append((name, path_str, path_obj, idx))

        return self.scan_entries(normalized_entries, game_name=game_name)
