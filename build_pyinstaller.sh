#!/bin/bash
# PyInstaller build script for Me3_Manager
# Install PyInstaller first: pip install pyinstaller

# Create spec file for better control
cat > Me3_Manager.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect data files
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
)
EOF

# Build with PyInstaller
echo "Building with PyInstaller..."
pyinstaller Me3_Manager.spec --clean --noconfirm

# Copy to build directory structure similar to cx_Freeze
mkdir -p build/Me3_Manager_$(cat version.py | grep VERSION | cut -d'"' -f2)
cp dist/Me3_Manager build/Me3_Manager_$(cat version.py | grep VERSION | cut -d'"' -f2)/

echo "Build complete!"
echo "Executable location: build/Me3_Manager_$(cat version.py | grep VERSION | cut -d'"' -f2)/Me3_Manager"