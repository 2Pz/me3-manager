#!/bin/sh

set -e

# Package me3-manager binary as AppImage using appimagetool

# Get version from pyproject.toml
version=$(grep --max-count=1 '^version\s*=' pyproject.toml | cut -d '"' -f2)

# Download appimagetool if it doesn't exist
# FIXME: Pin a specific version of appimagetool
ait_url=https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
if [ ! -f appimagetool-x86_64.appimage ]; then
	echo "Downloading appimagetool..."
	curl -fL "$ait_url" -o appimagetool-x86_64.appimage
fi

# AppDir staging folder
appdir=build/AppDir/

echo "Cleaning $appdir..."
rm -rf -- $appdir

mkdir $appdir

# Change dir so paths below are relative to $appdir
cd $appdir

# Create directory structure
mkdir -p usr/bin/
mkdir -p usr/share/applications/
mkdir -p usr/share/icons/hicolor/256x256/apps/

# Install binary
cp ../../dist/linux-"$version"/me3-manager usr/bin/
chmod +x usr/bin/me3-manager

# Install desktop file
cp ../../resources/linux/me3-manager.desktop usr/share/applications/

# Install icon
cp ../../resources/icon/icon.png usr/share/icons/hicolor/256x256/apps/me3-manager.png

# Create symlinks in AppDir root
ln -s usr/bin/me3-manager AppRun
ln -s usr/share/applications/me3-manager.desktop .
ln -s usr/share/icons/hicolor/256x256/apps/me3-manager.png .
ln -s usr/share/icons/hicolor/256x256/apps/me3-manager.png .DirIcon

# Return to repo dir
cd -

echo "Creating Appimage..."
chmod +x appimagetool-x86_64.appimage
./appimagetool-x86_64.appimage --appimage-extract-and-run $appdir dist/linux-"$version"/Me3_Manager.AppImage

echo "AppImage created: dist/linux-$version/Me3_Manager.AppImage"
