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
if %errorlevel% equ 0 goto PYTHON_OK
echo [ERROR] Python not found in the PATH environment variable!
echo Please install Python 3 (be sure to check "Add Python to PATH" during installation).
if "%CI%"=="" pause
exit /b 1
:PYTHON_OK

:: 2. Create and configure virtual environment
if exist venv goto VENV_EXISTS
echo [1/4] Creating virtual environment venv...
python -m venv venv
goto VENV_END
:VENV_EXISTS
echo [1/4] Virtual environment venv already exists.
:VENV_END

echo [2/4] Installing dependencies and builder...
call venv\Scripts\activate.bat
venv\Scripts\python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: 3. Download MediaPipe model weights
if exist face_landmarker.task goto MODEL_EXISTS
echo Downloading face_landmarker.task AI model...
venv\Scripts\python -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
goto MODEL_END
:MODEL_EXISTS
echo The face_landmarker.task AI model is already downloaded.
:MODEL_END

:: 4. Compile project into a single .exe file with hidden console (--noconsole)
echo [3/4] Running PyInstaller...
:: Important: on Windows, semicolon (;) is used as a separator for --add-data
venv\Scripts\pyinstaller --noconfirm --clean --onefile --noconsole ^
    --name "Frown_Guard" ^
    --add-data "face_landmarker.task;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "mediapipe" ^
    --icon "frown-guard.ico" ^
    main.py

echo [4/4] Verifying build results...
if not exist dist\Frown_Guard.exe goto BUILD_ERROR
echo.
echo =======================================================
echo  Packaging for Windows completed successfully!
echo  Executable file: dist\Frown_Guard.exe
echo =======================================================
goto BUILD_END
:BUILD_ERROR
echo [ERROR] Packaging failed! Please check the compilation logs above.
:BUILD_END

if "%CI%"=="" pause
