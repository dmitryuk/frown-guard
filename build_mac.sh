#!/bin/bash

# Script for automated packaging of the Frown Guard project into macOS App Bundle (.app) and Disk Image (.dmg) formats.
# The script must be executed directly on macOS.

# Stop execution on any error
set -e

# Remove old compiled artifacts to avoid file replacement conflicts
rm -f Frown_Guard.dmg

echo "=== [1/5] Preparing environment and dependencies ==="

# Verify that the script is running on macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "Error: This script is designed to run exclusively on macOS!"
    echo "To build for Linux, use ./build_appimage.sh"
    exit 1
fi

# Verify Python 3 installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed on this system. Please install it (e.g., via Homebrew: brew install python)."
    exit 1
fi

# Create a virtual environment if it does not exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment venv..."
    python3 -m venv venv
fi

# Activate environment and install main dependencies
echo "Upgrading pip and installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install pyinstaller

# Verify the MediaPipe model file
if [ ! -f "face_landmarker.task" ]; then
    echo "Downloading face_landmarker.task model..."
    venv/bin/python3 -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
fi

echo "=== [2/5] Generating application icon ==="
# Generate a beautiful application icon using Pillow
venv/bin/python3 -c "
from PIL import Image, ImageDraw
import os

img = Image.new('RGBA', (256, 256), color=(198, 40, 40, 255))
draw = ImageDraw.Draw(img)

# Draw a frowning face
draw.ellipse([40, 40, 216, 216], fill=(255, 235, 59, 255), outline=(0, 0, 0, 255), width=4)
draw.ellipse([80, 90, 100, 110], fill=(0, 0, 0, 255))
draw.ellipse([156, 90, 176, 110], fill=(0, 0, 0, 255))
draw.arc([80, 140, 176, 190], start=180, end=360, fill=(0, 0, 0, 255), width=6)
draw.line([70, 75, 110, 85], fill=(0, 0, 0, 255), width=5)
draw.line([186, 75, 146, 85], fill=(0, 0, 0, 255), width=5)

img.save('frown-guard.png')
print('Icon frown-guard.png successfully generated!')
"

echo "=== [3/5] Compiling macOS App Bundle (.app) ==="
# Run PyInstaller with the --windowed (or -w) flag to create a windowed .app bundle
echo "Running PyInstaller..."
venv/bin/pyinstaller --noconfirm --clean --windowed \
    --name "Frown Guard" \
    --add-data "face_landmarker.task:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "mediapipe" \
    --icon "frown-guard.png" \
    main.py

echo "=== [4/5] Injecting macOS Sandbox Camera Permissions ==="
APP_PATH="dist/Frown Guard.app"
if [ -d "$APP_PATH" ]; then
    echo "Successfully compiled package: $APP_PATH"
    # Inject NSCameraUsageDescription dynamically into Info.plist using python's built-in plistlib
    venv/bin/python3 -c "
import plistlib
plist_path = 'dist/Frown Guard.app/Contents/Info.plist'
try:
    with open(plist_path, 'rb') as f:
        pl = plistlib.load(f)
    pl['NSCameraUsageDescription'] = 'This application requires access to the webcam to monitor facial expressions and scowling in real-time.'
    pl['CFBundleDisplayName'] = 'Frown Guard'
    pl['CFBundleName'] = 'Frown Guard'
    pl['CFBundleIdentifier'] = 'com.frown.guard'
    with open(plist_path, 'wb') as f:
        plistlib.dump(pl, f)
    print('Info.plist camera permissions successfully injected!')
except Exception as e:
    print('Error injecting Info.plist:', e)
"
else
    echo "Error: Failed to find the built application in dist/"
    exit 1
fi

echo "=== [5/5] Creating Apple Disk Image installer (.dmg) ==="
# Create a standard .dmg file using the built-in hdiutil utility
echo "Generating Frown_Guard.dmg..."
rm -f Frown_Guard.dmg
hdiutil create -volname "Frown Guard Installer" -srcfolder "dist/Frown Guard.app" -ov -format UDZO "Frown_Guard.dmg"

echo ""
echo "======================================================="
echo " Packaging for macOS completed successfully!"
echo " Executable bundle: dist/Frown Guard.app"
echo " Installer file: Frown_Guard.dmg"
echo "======================================================="
