@echo off
:: Скрипт автоматической сборки проекта Frown Guard в один исполняемый файл (.exe) для Windows.
:: Этот скрипт должен запускаться на операционной системе Windows.

chcp 65001 >nul
echo =======================================================
echo  Frown Guard — Сборщик исполняемого файла для Windows
echo =======================================================
echo.

:: 1. Проверка наличия Python 3 в PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден в переменной окружения PATH!
    echo Пожалуйста, установите Python 3 (обязательно отметьте галочку "Add Python to PATH" при установке).
    pause
    exit /b 1
)

:: 2. Создание и настройка виртуального окружения
if not exist venv (
    echo [1/5] Создание виртуального окружения venv...
    python -m venv venv
) else (
    echo [1/5] Виртуальное окружение venv уже существует.
)

echo [2/5] Установка зависимостей и компилятора...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: 3. Скачивание весов модели MediaPipe
if not exist face_landmarker.task (
    echo Скачивание модели ИИ face_landmarker.task...
    python -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
) else (
    echo Модель ИИ face_landmarker.task уже загружена.
)

:: 4. Генерация профессиональной мульти-размерной Windows-иконки (.ico)
echo [3/5] Генерация иконки frown-guard.ico...
python -c "
from PIL import Image, ImageDraw
import os

# Создаем HD-картинку иконки
img = Image.new('RGBA', (256, 256), color=(198, 40, 40, 255))
draw = ImageDraw.Draw(img)

# Рисуем недовольный смайлик
draw.ellipse([40, 40, 216, 216], fill=(255, 235, 59, 255), outline=(0, 0, 0, 255), width=4)
draw.ellipse([80, 90, 100, 110], fill=(0, 0, 0, 255))
draw.ellipse([156, 90, 176, 110], fill=(0, 0, 0, 255))
draw.arc([80, 140, 176, 190], start=180, end=360, fill=(0, 0, 0, 255), width=6)
draw.line([70, 75, 110, 85], fill=(0, 0, 0, 255), width=5)
draw.line([186, 75, 146, 85], fill=(0, 0, 0, 255), width=5)

# Сохраняем как настоящий Windows ICO с поддержкой всех стандартных разрешений проводника
img.save('frown-guard.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print('Мульти-размерная иконка frown-guard.ico успешно сгенерирована!')
"

:: 5. Компиляция проекта в один .exe файл с скрытой консолью (--noconsole)
echo [4/5] Запуск компилятора PyInstaller...
:: Важно: в Windows для --add-data используется разделитель точка с запятой (;)
venv\Scripts\pyinstaller --noconfirm --clean --onefile --noconsole ^
    --name "Frown_Guard" ^
    --add-data "face_landmarker.task;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "mediapipe" ^
    --icon "frown-guard.ico" ^
    main.py

echo [5/5] Проверка результата сборки...
if exist dist\Frown_Guard.exe (
    echo.
    echo =======================================================
    echo  Сборка под Windows успешно завершена!
    echo  Исполняемый файл: dist\Frown_Guard.exe
    echo =======================================================
) else (
    echo [ОШИБКА] Сборка завершилась неудачно! Проверьте логи компиляции выше.
)

pause
