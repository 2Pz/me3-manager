#!/bin/bash
# PyInstaller build script for Me3_Manager
# Install PyInstaller first: pip install pyinstaller

# Create spec file for directory-based distribution
cat > Me3_Manager.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
import os

block_cipher = None

# Collect data files - include the entire resources folder
datas = [('resources', 'resources')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['encodings'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Me3_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
EOF

# Build with PyInstaller
echo "Building with PyInstaller..."
pyinstaller Me3_Manager.spec --clean --noconfirm

# Get version from pyproject.toml
VERSION=$(grep --max-count=1 '^version\s*=' pyproject.toml | cut -d '"' -f2)

# Create build directory structure
BUILD_DIR="build/Me3_Manager_${VERSION}"
mkdir -p "${BUILD_DIR}"

# Copy the single executable file to build directory
cp dist/Me3_Manager "${BUILD_DIR}/"

# Ensure resources folder is properly copied
if [ -d "resources" ]; then
    echo "Copying resources folder..."
    cp -r resources "${BUILD_DIR}/"
else
    echo "Warning: resources folder not found in current directory"
fi

echo "Build complete!"
echo "Distribution location: ${BUILD_DIR}/"
echo "Executable: ${BUILD_DIR}/Me3_Manager"
echo "Resources: ${BUILD_DIR}/resources/"

# List contents for verification
echo -e "\nContents of build directory:"
ls -la "${BUILD_DIR}/"

if [ -d "${BUILD_DIR}/resources" ]; then
    echo -e "\nContents of resources directory:"
    ls -la "${BUILD_DIR}/resources/"
    
    if [ -d "${BUILD_DIR}/resources/icon" ]; then
        echo -e "\nContents of resources/icon directory:"
        ls -la "${BUILD_DIR}/resources/icon/"
    fi
fi
