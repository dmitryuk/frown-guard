#!/bin/bash

# Script for automated packaging of the Frown Guard project into AppImage format.
# The script installs PyInstaller, compiles the application into a standalone directory,
# formats the AppDir structure, downloads appimagetool, and packages it into a single portable .AppImage file.

# Stop execution on any error
set -e

# Remove old compiled artifacts to avoid file locking errors (Text file busy)
rm -f dist/Frown_Guard-x86_64.AppImage

echo "=== [1/6] Preparing environment and dependencies ==="

# Verify and prepare the virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment venv..."
    python3 -m venv venv
fi

# Install/upgrade dependencies
echo "Installing/upgrading dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install pyinstaller

# Verify the MediaPipe model file
if [ ! -f "face_landmarker.task" ]; then
    echo "Downloading face_landmarker.task model..."
    venv/bin/python3 -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
fi

echo "=== [2/5] Packaging executable folder with PyInstaller ==="
# Compile the application. The --collect-all option is critical for mediapipe,
# as it gathers all binary libraries (.so) and model metadata.
echo "Running PyInstaller..."
venv/bin/pyinstaller --noconfirm --clean --onedir \
    --name "frown-guard" \
    --add-data "face_landmarker.task:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "mediapipe" \
    main.py

echo "=== [3/5] Creating AppDir structure ==="
# Clean old builds
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# 1. Copy PyInstaller output to AppDir/usr/bin/
cp -r dist/frown-guard/* AppDir/usr/bin/

# 2. Create the AppRun startup script in the AppDir root
cat << 'EOF' > AppDir/AppRun
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:$PATH"
export LD_LIBRARY_PATH="${HERE}/usr/bin:$LD_LIBRARY_PATH"
exec "${HERE}/usr/bin/frown-guard" "$@"
EOF
chmod +x AppDir/AppRun

# 3. Create the Desktop Entry shortcut
cat << 'EOF' > AppDir/frown-guard.desktop
[Desktop Entry]
Name=Frown Guard
Comment=Monitor facial expressions and forehead wrinkles via webcam
Exec=frown-guard
Icon=frown-guard
Type=Application
Terminal=false
Categories=Utility;
EOF

# 4. Copy the icon into the shortcut structure and the AppDir root
cp frown-guard.png AppDir/usr/share/icons/hicolor/256x256/apps/frown-guard.png
cp frown-guard.png AppDir/frown-guard.png
cp AppDir/frown-guard.desktop AppDir/usr/share/applications/frown-guard.desktop

echo "=== [4/5] Downloading appimagetool ==="
# Download the AppImage build utility
if [ ! -f "appimagetool" ]; then
    echo "Downloading appimagetool..."
    wget -q --show-progress -O appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
fi

echo "=== [5/5] Compiling final AppImage file ==="
# Package the AppImage.
# The ARCH=x86_64 flag is required. The --appimage-extract-and-run flag allows running appimagetool
# without requiring FUSE mounting (extremely useful in containers and CI).
export ARCH=x86_64
mkdir -p dist
./appimagetool --appimage-extract-and-run AppDir dist/Frown_Guard-x86_64.AppImage

echo ""
echo "======================================================="
echo " Packaging completed successfully!"
echo " Executable file: dist/Frown_Guard-x86_64.AppImage"
echo " Run it with the command: ./dist/Frown_Guard-x86_64.AppImage"
echo "======================================================="
