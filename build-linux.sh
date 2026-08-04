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

echo "Generating PyInstaller spec file..."
# Generate spec file so we can patch it
pyi-makespec \
	--name me3-manager \
	--onefile \
	--copy-metadata me3-manager \
	--collect-all patoolib \
	--collect-data certifi \
	--add-data resources:resources \
	--optimize 2 \
	--strip \
	src/me3_manager/main.py

echo "Patching spec file to exclude libxkbcommon..."
# Exclude libxkbcommon.so.0 to prevent Linux keyboard crashes on modern distros
python3 -c "
with open('me3-manager.spec', 'r') as f:
    content = f.read()
patch = \"\n# Exclude libxkbcommon to prevent keyboard crashes on Linux\na.binaries = [x for x in a.binaries if 'libxkbcommon.so.0' not in x[0]]\n\"
content = content.replace('pyz = PYZ(a.pure)', patch + 'pyz = PYZ(a.pure)')
with open('me3-manager.spec', 'w') as f:
    f.write(content)
"

echo "Checking for libxcb-cursor.so.0 on this build machine..."
xcb_cursor_path=$(ldconfig -p | grep 'libxcb-cursor\.so\.0' | awk '{print $NF}' | head -n1)
if [ -z "$xcb_cursor_path" ]; then
	echo "ERROR: libxcb-cursor.so.0 not found on this build machine."
	echo "Install it first, e.g.: sudo apt install libxcb-cursor0"
	exit 1
fi
echo "Found libxcb-cursor.so.0 at $xcb_cursor_path"

echo "Patching spec file to bundle libxcb-cursor.so.0..."
python3 -c "
with open('me3-manager.spec', 'r') as f:
    content = f.read()
patch = \"\n# Bundle libxcb-cursor.so.0 explicitly: Qt 6.5+ dlopens it at runtime\n# for cursor theme loading in the xcb platform plugin, so PyInstaller's\n# linker-based dependency analysis never discovers it on its own.\na.binaries += [('libxcb-cursor.so.0', '$xcb_cursor_path', 'BINARY')]\n\"
content = content.replace('pyz = PYZ(a.pure)', patch + 'pyz = PYZ(a.pure)')
with open('me3-manager.spec', 'w') as f:
    f.write(content)
"

echo "Building with PyInstaller..."
pyinstaller --clean --noconfirm \
	--distpath "dist/linux-$version" \
	me3-manager.spec