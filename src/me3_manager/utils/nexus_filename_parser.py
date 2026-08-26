"""
Nexus Mods filename parser.

Parses Nexus download filenames to extract mod metadata.
Classic:  StormControl.dll-146-1-0-2-1766187862.zip
Premium:  SoulsChat 9461 0.0.9 2026-07-17T21-39Z i2m9p03PP.zip
"""

from __future__ import annotations

from calendar import timegm
from dataclasses import dataclass
from pathlib import Path
from time import strptime


@dataclass
class NexusFilenameInfo:
    """Parsed metadata from a Nexus Mods filename."""

    mod_name: str
    mod_id: int
    version: str
    uploaded_timestamp: int


def _iso_to_epoch(ts: str) -> int:
    """Convert Nexus ISO timestamp (dashes instead of colons) to epoch."""
    ts = ts.rstrip("Zz")
    if "T" not in ts:
        return 0
    date_part, time_part = ts.split("T", 1)
    time_part = time_part.replace("-", ":")
    n_parts = len(time_part.split(":"))
    fmt = ["%Y-%m-%dT%H", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"][min(n_parts, 3) - 1]
    try:
        return timegm(strptime(f"{date_part}T{time_part}", fmt))
    except (ValueError, OverflowError):
        return 0


def parse_nexus_filename(filename: str) -> NexusFilenameInfo | None:
    """Parse a Nexus Mods filename to extract metadata."""
    if not filename:
        return None

    name = Path(filename).stem

    # Classic: {NAME}-{ID}-[{VERSION}-]{TIMESTAMP}
    parts = name.split("-")
    if len(parts) >= 3 and parts[-1].isdigit() and len(parts[-1]) >= 10:
        name_parts: list[str] = []
        mod_id_idx = None
        for i, part in enumerate(parts[:-1]):
            if part.isdigit() and name_parts:
                mod_id_idx = i
                break
            name_parts.append(part)
        if mod_id_idx is not None and name_parts:
            return NexusFilenameInfo(
                mod_name="-".join(name_parts),
                mod_id=int(parts[mod_id_idx]),
                version=".".join(parts[mod_id_idx + 1 : -1]),
                uploaded_timestamp=int(parts[-1]),
            )

    # Premium: {NAME} {ID} {VERSION} {ISO_TS} {UID}
    parts = name.rsplit(maxsplit=4)
    if len(parts) == 5 and parts[1].isdigit() and "T" in parts[3]:
        return NexusFilenameInfo(
            mod_name=parts[0],
            mod_id=int(parts[1]),
            version=parts[2].replace("-", "."),
            uploaded_timestamp=_iso_to_epoch(parts[3]),
        )

    return None
