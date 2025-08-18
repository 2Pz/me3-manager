#!/bin/bash

# Simple AppImage builder for Me3_Manager
set -e

echo "Building Me3_Manager AppImage..."

# Create directory structure
mkdir -p usr/bin
mkdir -p usr/share/applications
mkdir -p usr/share/icons/hicolor/256x256/apps

# Copy binary from dist folder
cp ../dist/Me3_Manager usr/bin/
chmod +x usr/bin/Me3_Manager

# Copy icon to the required locations (avoid copying to same location)
cp Me3_Manager.png usr/share/icons/hicolor/256x256/apps/

# Create .desktop file
cat > usr/share/applications/Me3_Manager.desktop << EOF
[Desktop Entry]
Type=Application
Name=Me3_Manager
Comment=Mass Effect 3 Manager
Exec=Me3_Manager
Icon=Me3_Manager
Categories=Game;Utility;
Terminal=false
EOF

# Copy .desktop file to root
cp usr/share/applications/Me3_Manager.desktop ./

# Create AppRun
cat > AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
cd "$(dirname "$ARGV0")" || cd "$HOME"
exec "${HERE}/usr/bin/Me3_Manager" "$@"
EOF

chmod +x AppRun

# Build AppImage
echo "Creating AppImage..."
chmod +x appimagetool-x86_64.appimage
./appimagetool-x86_64.appimage . Me3_Manager.AppImage

# Clean up
echo "Cleaning up..."
rm -rf usr/
rm -f Me3_Manager.desktop
rm -f AppRun

echo "Done! Me3_Manager.AppImage created successfully."
