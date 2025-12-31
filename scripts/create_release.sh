#!/bin/bash
# Create GitHub release with artifacts
#
# Usage: ./create_release.sh <version> <changelog_content>
# Example: ./create_release.sh v1.3.0 "$(cat changelog.txt)"
#
# Environment variables:
#   GITHUB_TOKEN or GH_TOKEN: GitHub token for authentication
#
# Expected artifact structure:
#   artifacts/
#   ├── me3-manager-linux-release/
#   │   └── Me3_Manager.AppImage
#   └── me3-manager-windows-release/
#       └── (windows build files)

set -euo pipefail

VERSION="${1:-}"
CHANGELOG_CONTENT="${2:-}"

if [ -z "$VERSION" ]; then
    echo "Error: Version argument required" >&2
    echo "Usage: $0 <version> <changelog_content>" >&2
    exit 1
fi

# Strip 'v' prefix for file naming
VERSION_NO_V="${VERSION#v}"

# Get commit SHA for tagging
COMMIT=$(git rev-parse --verify HEAD)

# Delete existing release if it exists (draft or otherwise)
if gh release view "$VERSION" >/dev/null 2>&1; then
    echo "Deleting existing release $VERSION..."
    gh release delete "$VERSION" --yes
fi

# Build artifact list
ARTIFACTS=()

# Add Linux AppImage if exists
LINUX_ARTIFACT="artifacts/me3-manager-linux-release/Me3_Manager_${VERSION_NO_V}_Linux.AppImage"
if [ -f "$LINUX_ARTIFACT" ]; then
    ARTIFACTS+=("$LINUX_ARTIFACT")
else
    echo "Warning: Linux artifact not found at $LINUX_ARTIFACT" >&2
fi

# Package and add Windows artifacts if they exist
if [ -d "artifacts/me3-manager-windows-release" ]; then
    WINDOWS_ZIP="Me3_Manager_${VERSION_NO_V}_Windows.zip"
    
    # Create zip of Windows files
    (cd "artifacts/me3-manager-windows-release" && zip -r "../../$WINDOWS_ZIP" .)
    
    ARTIFACTS+=("$WINDOWS_ZIP")
fi

if [ ${#ARTIFACTS[@]} -eq 0 ]; then
    echo "Error: No artifacts found to upload" >&2
    exit 1
fi

# Create the draft release
echo "Creating draft release $VERSION with ${#ARTIFACTS[@]} artifact(s)..."
gh release create \
    --target "$COMMIT" \
    --title "$VERSION" \
    --notes "$CHANGELOG_CONTENT" \
    --draft \
    "$VERSION" \
    "${ARTIFACTS[@]}"

echo "✅ Release $VERSION created successfully!"
