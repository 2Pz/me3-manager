#!/bin/bash

APPDIR="$(pwd)"
chmod +x "$APPDIR/appimagetool-x86_64.appimage"

ARCH=x86_64 "$APPDIR/appimagetool-x86_64.appimage" .

echo "✅ Build complete! Check the current directory for the generated AppImage."
