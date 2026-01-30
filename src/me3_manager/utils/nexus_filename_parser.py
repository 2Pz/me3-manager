"""
Nexus Mods filename parser.

Parses Nexus download filenames to extract mod metadata.

Filename format: {MOD_NAME}-{MOD_ID}-{VERSION}-{TIMESTAMP}.{ext}
Example: StormControl.dll-146-1-0-2-1766187862.zip
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NexusFilenameInfo:
    """Parsed metadata from a Nexus Mods filename."""

    mod_name: str
    mod_id: int
    version: str  # Converted from "1-5-2" to "1.5.2"
    uploaded_timestamp: int


# Regex pattern to match Nexus filename format
# Format: {MOD_NAME}-{MOD_ID}-{VERSION_PARTS}-{TIMESTAMP}.ext
# MOD_NAME can contain anything except the pattern that follows
# MOD_ID is digits
# VERSION is one or more dash-separated numbers (e.g., "1-5-2")
# TIMESTAMP is a Unix timestamp (10 digits typically)
_NEXUS_FILENAME_PATTERN = re.compile(
    r"^(.+?)-(\d+)-([\d]+(?:-[\d]+)*)-(\d{10,})$", re.IGNORECASE
)

# Simpler pattern without version (some mods might not have version in filename)
_NEXUS_FILENAME_NO_VERSION_PATTERN = re.compile(
    r"^(.+?)-(\d+)-(\d{10,})$", re.IGNORECASE
)


def parse_nexus_filename(filename: str) -> NexusFilenameInfo | None:
    """
    Parse a Nexus Mods filename to extract metadata.

    Args:
        filename: The filename (with or without path/extension) to parse.
                  Example: "StormControl.dll-146-1-0-2-1766187862.zip"

    Returns:
        NexusFilenameInfo if parsing succeeds, None otherwise.
    """
    if not filename:
        return None

    # Remove path and extension
    name = Path(filename).stem

    # Try full pattern first (with version)
    match = _NEXUS_FILENAME_PATTERN.match(name)
    if match:
        mod_name = match.group(1).strip()
        mod_id = int(match.group(2))
        version_raw = match.group(3)
        timestamp = int(match.group(4))

        # Convert version from "1-5-2" to "1.5.2"
        version = version_raw.replace("-", ".")

        return NexusFilenameInfo(
            mod_name=mod_name,
            mod_id=mod_id,
            version=version,
            uploaded_timestamp=timestamp,
        )

    # Try pattern without version
    match = _NEXUS_FILENAME_NO_VERSION_PATTERN.match(name)
    if match:
        mod_name = match.group(1).strip()
        mod_id = int(match.group(2))
        timestamp = int(match.group(3))

        return NexusFilenameInfo(
            mod_name=mod_name,
            mod_id=mod_id,
            version="",
            uploaded_timestamp=timestamp,
        )

    return None
