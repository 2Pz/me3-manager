#!/bin/sh

set -e

# Build me3-manager as a standalone (one-file) binary for Linux
#
# Usage with uv:
#     uv sync --dev
#     uv run ./build-linux.sh
#
# Usage with pip (activate venv first):
#     pip install -r requirements-dev.txt
#     ./build-linux.sh

# pyinstaller does not cross-compile. Build results will be wrong on other OSes.
if [ "$(uname)" != Linux ]; then
	echo "This script only works on Linux."
	exit 1
fi

# Get version from pyproject.toml
version=$(grep --max-count=1 '^version\s*=' pyproject.toml | cut -d '"' -f2)

echo "Building with PyInstaller..."

# Don't need to generate spec file first with pyi-makespec. We can pass the same
# arguments directly to pyinstaller; it will generate the spec file then build.
pyinstaller --clean --noconfirm \
	--name me3-manager \
	--onefile \
	--copy-metadata me3-manager \
	--collect-all patoolib \
	--collect-data certifi \
	--add-data resources:resources \
	--optimize 2 \
	--strip \
	--distpath "dist/linux-$version" \
	src/me3_manager/main.py
