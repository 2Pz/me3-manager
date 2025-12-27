#!/usr/bin/env python3
"""Script to bump version in pyproject.toml."""

import sys
from pathlib import Path

import tomlkit


def bump_version(new_version: str) -> None:
    """Update version in pyproject.toml.

    Args:
        new_version: New version string (e.g., "1.2.3" or "v1.2.3")
    """
    # Remove 'v' prefix if present
    new_version = new_version.lstrip("v")

    # Path to pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    # Read current content
    content = pyproject_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(content)

    # Update version
    old_version = doc["project"]["version"]  # type: ignore[index]
    doc["project"]["version"] = new_version  # type: ignore[index]

    # Write back
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    print(f"Version updated: {old_version} -> {new_version}")


if __name__ == "__main__":
    # Check for help first
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print("Usage: bump_version.py <new_version>")
        print()
        print("Examples:")
        print("  bump_version.py 1.2.4")
        print("  bump_version.py v1.2.4")
        sys.exit(0)

    if len(sys.argv) != 2:
        print("Usage: bump_version.py <new_version>")
        sys.exit(1)

    bump_version(sys.argv[1])
