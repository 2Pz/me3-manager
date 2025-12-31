#!/bin/bash
# Extract changelog section for a specific version from CHANGELOG.md
#
# Usage: ./extract_changelog.sh <version> [changelog_file]
# Example: ./extract_changelog.sh v1.3.0
#          ./extract_changelog.sh v1.3.0 ./CHANGELOG.md
#
# Output: Prints the changelog section to stdout, saves to VERSION_changelog.txt

set -euo pipefail

VERSION="${1:-}"
CHANGELOG_FILE="${2:-CHANGELOG.md}"

if [ -z "$VERSION" ]; then
    echo "Error: Version argument required" >&2
    echo "Usage: $0 <version> [changelog_file]" >&2
    exit 1
fi

if [ ! -f "$CHANGELOG_FILE" ]; then
    echo "Error: Changelog file not found: $CHANGELOG_FILE" >&2
    exit 1
fi

# Extract the section for this version (from "## 📦 Release X.Y.Z" to next "---")
changelog=$(sed -n '/^## 📦 Release '"$VERSION"'/,/^---$/p' "$CHANGELOG_FILE" | head -n -1)

# Fallback: If extraction fails, try to get the first release section
if [ -z "$changelog" ]; then
    changelog=$(sed -n '/^## 📦 Release/,/^---$/p' "$CHANGELOG_FILE" | head -n -1 | head -100)
fi

# Output to stdout
echo "$changelog"
