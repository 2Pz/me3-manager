#!/bin/bash

APPDIR="$(pwd)"
chmod +x "$APPDIR/appimagetool-x86_64.appimage"

ARCH=x86_64 "$APPDIR/appimagetool-x86_64.appimage" .

# Rename the generated AppImage
if [ -f "Me3_Manager-x86_64.AppImage" ]; then
    mv "Me3_Manager-x86_64.AppImage" "Me3_Manager.AppImage"
    echo "✅ Build complete! AppImage created: Me3_Manager.AppImage"
else
    echo "❌ Build failed: AppImage not found."
fi
