@echo off
:: Script for automated packaging of the Frown Guard project into a single executable file (.exe) for Windows.
:: This script must be executed on Windows.

chcp 65001 >nul
:: Remove old compiled artifacts to avoid write conflicts
if exist dist\Frown_Guard.exe del /f /q dist\Frown_Guard.exe

echo =======================================================
echo  Frown Guard — Windows Executable Builder
echo =======================================================
echo.

:: 1. Verify Python 3 presence in PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in the PATH environment variable!
    echo Please install Python 3 (be sure to check "Add Python to PATH" during installation).
    if "%CI%"=="" pause
    exit /b 1
)

:: 2. Create and configure virtual environment
if not exist venv (
    echo [1/5] Creating virtual environment venv...
    python -m venv venv
) else (
    echo [1/5] Virtual environment venv already exists.
)

echo [2/5] Installing dependencies and builder...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: 3. Download MediaPipe model weights
if not exist face_landmarker.task (
    echo Downloading face_landmarker.task AI model...
    python -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
) else (
    echo The face_landmarker.task AI model is already downloaded.
)

:: 4. Generate professional multi-size Windows icon (.ico)
echo [3/5] Generating frown-guard.ico icon...
python -c "
from PIL import Image, ImageDraw
import os

# Create HD icon image
img = Image.new('RGBA', (256, 256), color=(198, 40, 40, 255))
draw = ImageDraw.Draw(img)

# Draw a frowning face
draw.ellipse([40, 40, 216, 216], fill=(255, 235, 59, 255), outline=(0, 0, 0, 255), width=4)
draw.ellipse([80, 90, 100, 110], fill=(0, 0, 0, 255))
draw.ellipse([156, 90, 176, 110], fill=(0, 0, 0, 255))
draw.arc([80, 140, 176, 190], start=180, end=360, fill=(0, 0, 0, 255), width=6)
draw.line([70, 75, 110, 85], fill=(0, 0, 0, 255), width=5)
draw.line([186, 75, 146, 85], fill=(0, 0, 0, 255), width=5)

# Save as authentic Windows ICO supporting all standard Explorer dimensions
img.save('frown-guard.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print('Multi-size icon frown-guard.ico successfully generated!')
"

:: 5. Compile project into a single .exe file with hidden console (--noconsole)
echo [4/5] Running PyInstaller...
:: Important: on Windows, semicolon (;) is used as a separator for --add-data
venv\Scripts\pyinstaller --noconfirm --clean --onefile --noconsole ^
    --name "Frown_Guard" ^
    --add-data "face_landmarker.task;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "mediapipe" ^
    --icon "frown-guard.ico" ^
    main.py

echo [5/5] Verifying build results...
if exist dist\Frown_Guard.exe (
    echo.
    echo =======================================================
    echo  Packaging for Windows completed successfully!
    echo  Executable file: dist\Frown_Guard.exe
    echo =======================================================
) else (
    echo [ERROR] Packaging failed! Please check the compilation logs above.
)

if "%CI%"=="" pause
