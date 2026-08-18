#!/bin/bash

# Скрипт автоматической сборки проекта Frown Guard в формат macOS App Bundle (.app) и Disk Image (.dmg).
# Скрипт должен запускаться непосредственно на операционной системе macOS.

# Останавливать выполнение при любой ошибке
set -e

# Удаляем старые скомпилированные артефакты, чтобы избежать конфликтов при перезаписи
rm -f Frown_Guard.dmg

echo "=== [1/5] Подготовка окружения и зависимостей ==="

# Проверяем, что запуск происходит на macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "Ошибка: Данный скрипт предназначен для запуска исключительно на операционной системе macOS!"
    echo "Для сборки под Linux используйте ./build_appimage.sh"
    exit 1
fi

# Проверка наличия Python 3
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python 3 не установлен в системе. Пожалуйста, установите его (например, через Homebrew: brew install python)."
    exit 1
fi

# Создаем виртуальное окружение, если его нет
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения venv..."
    python3 -m venv venv
fi

# Активируем окружение и устанавливаем основные зависимости
echo "Обновление pip и установка зависимостей..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install pyinstaller

# Проверяем наличие модели MediaPipe
if [ ! -f "face_landmarker.task" ]; then
    echo "Скачивание модели face_landmarker.task..."
    venv/bin/python3 -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
fi

echo "=== [2/5] Генерация иконки приложения ==="
# Генерируем красивую иконку приложения средствами Pillow
venv/bin/python3 -c "
from PIL import Image, ImageDraw
import os

img = Image.new('RGBA', (256, 256), color=(198, 40, 40, 255))
draw = ImageDraw.Draw(img)

# Рисуем недовольный смайлик
draw.ellipse([40, 40, 216, 216], fill=(255, 235, 59, 255), outline=(0, 0, 0, 255), width=4)
draw.ellipse([80, 90, 100, 110], fill=(0, 0, 0, 255))
draw.ellipse([156, 90, 176, 110], fill=(0, 0, 0, 255))
draw.arc([80, 140, 176, 190], start=180, end=360, fill=(0, 0, 0, 255), width=6)
draw.line([70, 75, 110, 85], fill=(0, 0, 0, 255), width=5)
draw.line([186, 75, 146, 85], fill=(0, 0, 0, 255), width=5)

img.save('frown-guard.png')
print('Иконка frown-guard.png успешно сгенерирована!')
"

echo "=== [3/5] Компиляция macOS App Bundle (.app) ==="
# Запускаем PyInstaller с флагом --windowed (или -w) для создания оконного .app
# Флаг --info-plist внедряет mac_info.plist с разрешением NSCameraUsageDescription
echo "Запуск компилятора PyInstaller..."
venv/bin/pyinstaller --noconfirm --clean --windowed \
    --name "Frown Guard" \
    --add-data "face_landmarker.task:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "mediapipe" \
    --info-plist "mac_info.plist" \
    --icon "frown-guard.png" \
    main.py

echo "=== [4/5] Проверка структуры собранного пакета ==="
APP_PATH="dist/Frown Guard.app"
if [ -d "$APP_PATH" ]; then
    echo "Успешно скомпилирован пакет: $APP_PATH"
else
    echo "Ошибка: Не удалось найти собранное приложение в dist/"
    exit 1
fi

echo "=== [5/5] Создание установщика Apple Disk Image (.dmg) ==="
# Собираем стандартный .dmg файл с помощью встроенной утилиты hdiutil
echo "Генерация Frown_Guard.dmg..."
rm -f Frown_Guard.dmg
hdiutil create -volname "Frown Guard Installer" -srcfolder "dist/Frown Guard.app" -ov -format UDZO "Frown_Guard.dmg"

echo ""
echo "======================================================="
echo " Сборка под macOS успешно завершена!"
echo " Исполняемый пакет: dist/Frown Guard.app"
echo " Файл установщика: Frown_Guard.dmg"
echo "======================================================="
