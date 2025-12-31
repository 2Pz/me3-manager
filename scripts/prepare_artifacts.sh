#!/bin/bash
# Prepare and rename release artifacts for upload
#
# Usage: ./prepare_artifacts.sh <version>
# Example: ./prepare_artifacts.sh v1.3.0
#
# Expected input structure:
#   artifacts/
#   ├── me3-manager-linux-release/
#   │   └── Me3_Manager.AppImage
#   └── me3-manager-windows-release/
#       └── (windows build files)
#
# Output:
#   - Renames Linux AppImage to include version
#   - Lists all prepared artifacts

set -euo pipefail

VERSION="${1:-}"

if [ -z "$VERSION" ]; then
    echo "Error: Version argument required" >&2
    echo "Usage: $0 <version>" >&2
    exit 1
fi

# Strip 'v' prefix for file naming
VERSION_NO_V="${VERSION#v}"

echo "Preparing artifacts for version $VERSION..."

# Rename Linux AppImage if it exists
LINUX_DIR="artifacts/me3-manager-linux-release"
if [ -d "$LINUX_DIR" ]; then
    ORIGINAL="$LINUX_DIR/Me3_Manager.AppImage"
    RENAMED="$LINUX_DIR/Me3_Manager_${VERSION_NO_V}_Linux.AppImage"
    
    if [ -f "$ORIGINAL" ]; then
        mv "$ORIGINAL" "$RENAMED"
        echo "✅ Renamed Linux AppImage: $RENAMED"
    elif [ -f "$RENAMED" ]; then
        echo "ℹ️  Linux AppImage already renamed: $RENAMED"
    else
        echo "⚠️  Warning: Linux AppImage not found at $ORIGINAL" >&2
    fi
fi

# List all prepared artifacts
echo ""
echo "📦 Prepared artifacts:"
ls -la artifacts/*/
