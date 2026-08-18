#!/bin/bash

# Скрипт автоматической сборки проекта Frown Guard в формат AppImage.
# Скрипт устанавливает PyInstaller, компилирует приложение в standalone-директорию,
# формирует структуру AppDir, скачивает appimagetool и собирает единый переносимый файл .AppImage.

# Останавливать выполнение при любой ошибке
set -e

# Удаляем старые скомпилированные артефакты, чтобы избежать ошибок блокировки файлов (Text file busy)
rm -f Frown_Guard-x86_64.AppImage

echo "=== [1/6] Подготовка окружения и зависимостей ==="

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "Ошибка: виртуальное окружение 'venv' не найдено. Сначала запустите настройку проекта."
    exit 1
fi

# Проверяем модель MediaPipe
if [ ! -f "face_landmarker.task" ]; then
    echo "Скачивание модели face_landmarker.task..."
    venv/bin/python3 -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', 'face_landmarker.task')"
fi

# Устанавливаем PyInstaller в venv
echo "Установка PyInstaller..."
venv/bin/pip install --upgrade pip
venv/bin/pip install pyinstaller

echo "=== [2/6] Генерация кастомной иконки приложения ==="
# Генерируем красивую иконку приложения (красный круг со смайликом) средствами Pillow
venv/bin/python3 -c "
from PIL import Image, ImageDraw, ImageFont
import os

# Создаем базовое изображение 256x256 с красным Material-фоном
img = Image.new('RGBA', (256, 256), color=(198, 40, 40, 255))
draw = ImageDraw.Draw(img)

# Рисуем контур недовольного лица
# Желтый круг для смайлика
draw.ellipse([40, 40, 216, 216], fill=(255, 235, 59, 255), outline=(0, 0, 0, 255), width=4)
# Глаза
draw.ellipse([80, 90, 100, 110], fill=(0, 0, 0, 255))
draw.ellipse([156, 90, 176, 110], fill=(0, 0, 0, 255))
# Грустный рот (дуга)
draw.arc([80, 140, 176, 190], start=180, end=360, fill=(0, 0, 0, 255), width=6)
# Брови домиком
draw.line([70, 75, 110, 85], fill=(0, 0, 0, 255), width=5)
draw.line([186, 75, 146, 85], fill=(0, 0, 0, 255), width=5)

img.save('frown-guard.png')
print('Иконка frown-guard.png успешно сгенерирована!')
"

echo "=== [3/6] Сборка исполняемой папки через PyInstaller ==="
# Компилируем приложение. Опция --collect-all крайне важна для mediapipe,
# так как она собирает все бинарные библиотеки (.so) и метаданные моделей.
echo "Запуск PyInstaller..."
venv/bin/pyinstaller --noconfirm --clean --onedir \
    --name "frown-guard" \
    --add-data "face_landmarker.task:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "mediapipe" \
    main.py

echo "=== [4/6] Формирование структуры AppDir ==="
# Очищаем старые сборки
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# 1. Копируем результат PyInstaller в AppDir/usr/bin/
cp -r dist/frown-guard/* AppDir/usr/bin/

# 2. Создаем пусковой скрипт AppRun в корне AppDir
cat << 'EOF' > AppDir/AppRun
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:$PATH"
export LD_LIBRARY_PATH="${HERE}/usr/bin:$LD_LIBRARY_PATH"
exec "${HERE}/usr/bin/frown-guard" "$@"
EOF
chmod +x AppDir/AppRun

# 3. Создаем ярлык Desktop Entry
cat << 'EOF' > AppDir/frown-guard.desktop
[Desktop Entry]
Name=Frown Guard
Comment=Контроль мимики лица и морщин на лбу по веб-камере
Exec=frown-guard
Icon=frown-guard
Type=Application
Terminal=false
Categories=Utility;
EOF

# 4. Копируем иконку в структуру ярлыков и в корень AppDir
cp frown-guard.png AppDir/usr/share/icons/hicolor/256x256/apps/frown-guard.png
cp frown-guard.png AppDir/frown-guard.png
cp AppDir/frown-guard.desktop AppDir/usr/share/applications/frown-guard.desktop

echo "=== [5/6] Скачивание appimagetool ==="
# Скачиваем утилиту для сборки AppImage
if [ ! -f "appimagetool" ]; then
    echo "Загрузка appimagetool..."
    wget -q --show-progress -O appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
fi

echo "=== [6/6] Компиляция финального файла AppImage ==="
# Собираем AppImage.
# Флаг ARCH=x86_64 обязателен. Флаг --appimage-extract-and-run позволяет запустить appimagetool
# без потребности в монтировании через FUSE (крайне полезно для контейнеров и CI).
export ARCH=x86_64
./appimagetool --appimage-extract-and-run AppDir Frown_Guard-x86_64.AppImage

echo ""
echo "======================================================="
echo " Сборка завершена успешно!"
echo " Исполняемый файл: Frown_Guard-x86_64.AppImage"
echo " Запустите его командой: ./Frown_Guard-x86_64.AppImage"
echo "======================================================="
