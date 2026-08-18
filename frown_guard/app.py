import os
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any

import cv2
from PIL import Image, ImageTk

from frown_guard.detector import FaceFrownDetector
from frown_guard.overlay import FrownWarningOverlay

class FrownGuardApp:
    """
    Основное графическое приложение Frown Guard.
    Предоставляет панель управления с темной темой, живым видеопотоком,
    калибровкой, регулировкой чувствительности и управлением оверлеем.
    """
    CONFIG_FILE = "config.json"
    
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Frown Guard — Контроль мимики")
        self.root.geometry("946x774")
        self.root.resizable(True, True)
        
        # Настройка цветовой палитры (современная темная тема)
        self.colors = {
            "bg": "#121212",         # Основной фон
            "card": "#1E1E1E",       # Фон панелей и карт
            "text": "#E0E0E0",       # Основной текст
            "text_muted": "#888888", # Заглушенный текст
            "accent": "#00ADB5",     # Акцентный бирюзовый
            "accent_hover": "#00F5FF",
            "alert": "#FF5722",      # Оранжево-красный при хмурости
            "success": "#4CAF50",    # Зеленый при спокойном лице
            "border": "#2D2D2D"      # Разделители
        }
        
        self.root.configure(bg=self.colors["bg"])
        
        # Переменные конфигурации (загружаются из файла или устанавливаются по умолчанию)
        self.relaxed_score = 1.20
        self.frowned_score = 0.85
        self.sensitivity = 50.0
        self.overlay_opacity = 0.9
        self.show_video_preview = True
        self.camera_index = 0
        self.poll_fps = 30.0
        self.debounce_time = 0.5
        
        self.load_config()
        
        # Инициализация детектора и оверлея
        self.detector = FaceFrownDetector()
        self.detector.set_calibration(self.relaxed_score, self.frowned_score)
        self.detector.sensitivity = self.sensitivity
        
        self.overlay = FrownWarningOverlay(self.root)
        self.overlay.set_opacity(self.overlay_opacity)
        
        # Мьютекс для безопасного многопоточного доступа к объекту VideoCapture
        self.cap_lock = threading.Lock()
        
        # Поток для захвата видео и очередь для кадров
        self.video_queue: queue.Queue = queue.Queue(maxsize=2)
        self.is_running = True
        self.cap: Optional[cv2.VideoCapture] = None
        self.video_thread: Optional[threading.Thread] = None
        
        # Флаги запросов калибровки из GUI
        self.calibrate_relaxed_requested = False
        self.calibrate_frowned_requested = False
        self.last_combined_score = 1.0  # Буфер для хранения текущего значения детектора
        self.frowning_start_time: Optional[float] = None
        
        # Оформление стилей ttk (с поддержкой темной темы для Combobox)
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure(".", background=self.colors["bg"], foreground=self.colors["text"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        
        # Настройка внутренних отступов (padding) и стрелочки для комфортного отображения Combobox
        self.style.configure('TCombobox', 
            padding=(10, 6),  # Отступы: 10px слева/справа, 6px сверху/снизу
            arrowsize=14      # Пропорциональный размер стрелочки выбора
        )
        
        # Настройка цветов выпадающего списка Combobox для устранения невидимого/белого текста в Linux GTK
        self.style.map('TCombobox', 
            fieldbackground=[('readonly', self.colors["card"])],
            background=[('readonly', self.colors["card"])],
            foreground=[('readonly', self.colors["text"])],
            selectbackground=[('readonly', self.colors["accent"])],
            selectforeground=[('readonly', self.colors["bg"])]
        )
        
        # Настройка выпадающего списка (listbox) внутри Combobox
        self.root.option_add('*TCombobox*Listbox.background', self.colors["card"])
        self.root.option_add('*TCombobox*Listbox.foreground', self.colors["text"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.colors["accent"])
        self.root.option_add('*TCombobox*Listbox.selectForeground', self.colors["bg"])
        
        # Построение интерфейса
        self.create_widgets()
        
        # Запуск фонового видеопотока
        self.start_video_stream()
        
        # Запуск опроса очереди обработанных кадров
        self.poll_queue()
        
        # Корректное закрытие приложения
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def load_config(self) -> None:
        """Загружает калибровочные параметры из файла конфигурации JSON."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.relaxed_score = config.get("relaxed_score", 1.20)
                    self.frowned_score = config.get("frowned_score", 0.85)
                    self.sensitivity = config.get("sensitivity", 50.0)
                    self.overlay_opacity = config.get("overlay_opacity", 0.9)
                    self.camera_index = config.get("camera_index", 0)
                    self.poll_fps = config.get("poll_fps", 30.0)
                    self.debounce_time = config.get("debounce_time", 0.5)
            except Exception as e:
                print(f"Не удалось загрузить config.json: {e}")
                
    def save_config(self) -> None:
        """Сохраняет текущие параметры в JSON."""
        try:
            config = {
                "relaxed_score": self.relaxed_score,
                "frowned_score": self.frowned_score,
                "sensitivity": self.sensitivity,
                "overlay_opacity": self.overlay_opacity,
                "camera_index": self.camera_index,
                "poll_fps": self.poll_fps,
                "debounce_time": self.debounce_time
            }
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Не удалось сохранить config.json: {e}")

    def create_widgets(self) -> None:
        """Создает стильные виджеты интерфейса на основе Grid-верстки."""
        # Главный контейнер с отступами
        main_container = tk.Frame(self.root, bg=self.colors["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Левая часть — Видеопоток
        self.video_frame = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        self.video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Заголовок видео
        video_title = tk.Label(
            self.video_frame, 
            text="Камера контроля мимики", 
            font=("Helvetica", 12, "bold"), 
            bg=self.colors["card"], 
            fg=self.colors["text"]
        )
        video_title.pack(fill=tk.X, pady=10)
        
        # Область вывода видео
        self.video_label = tk.Label(self.video_frame, bg=self.colors["bg"])
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Правая часть — Панель управления и калибровки
        control_frame = tk.Frame(main_container, bg=self.colors["bg"], width=320)
        control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        control_frame.pack_propagate(False)
        
        # 1. Секция состояния (Карточка)
        status_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        status_card.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(status_card, text="ТЕКУЩЕЕ СОСТОЯНИЕ", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"]).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.status_text_label = tk.Label(status_card, text="Поиск лица...", font=("Helvetica", 16, "bold"), bg=self.colors["card"], fg=self.colors["accent"])
        self.status_text_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Прогресс-бар уровня хмурости
        progress_bg = tk.Frame(status_card, bg=self.colors["bg"], height=16)
        progress_bg.pack(fill=tk.X, padx=15, pady=(0, 15))
        progress_bg.pack_propagate(False)
        
        self.frown_bar = tk.Frame(progress_bg, bg=self.colors["accent"])
        self.frown_bar.place(x=0, y=0, relwidth=0.0, relheight=1.0)
        
        # Линия-порог срабатывания (поверх прогресс-бара)
        self.threshold_line = tk.Frame(progress_bg, bg=self.colors["text_muted"], width=2)
        self.threshold_line.place(relx=0.5, y=0, relheight=1.0)
        
        self.metrics_label = tk.Label(status_card, text="Метрика: 0.00 | Порог: 0.00", font=("Courier", 10), bg=self.colors["card"], fg=self.colors["text_muted"])
        self.metrics_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # 2. Секция калибровки (Карточка)
        calib_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        calib_card.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(calib_card, text="ИНДИВИДУАЛЬНАЯ КАЛИБРОВКА", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"]).pack(anchor="w", padx=15, pady=(10, 5))
        
        calib_desc = tk.Label(
            calib_card, 
            text="Нажмите 'Спокойное лицо' смотря прямо расслабленно. Затем нахмурьтесь и нажмите 'Нахмуренное лицо'.", 
            font=("Helvetica", 9), 
            bg=self.colors["card"], 
            fg=self.colors["text_muted"], 
            justify=tk.LEFT,
            wraplength=280
        )
        calib_desc.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Кнопки калибровки с плоским стилем и hover-эффектом
        self.btn_cal_relaxed = tk.Button(
            calib_card, 
            text="😊 Спокойное лицо", 
            font=("Helvetica", 11, "bold"),
            bg="#2E7D32", fg="white", 
            activebackground="#1B5E20", activeforeground="white",
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=8,
            command=self.request_calibrate_relaxed
        )
        self.btn_cal_relaxed.pack(fill=tk.X, padx=15, pady=(0, 10), ipady=6)
        
        self.btn_cal_frowned = tk.Button(
            calib_card, 
            text="😡 Нахмуренное лицо", 
            font=("Helvetica", 11, "bold"),
            bg="#C62828", fg="white", 
            activebackground="#B71C1C", activeforeground="white",
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=8,
            command=self.request_calibrate_frowned
        )
        self.btn_cal_frowned.pack(fill=tk.X, padx=15, pady=(0, 15), ipady=6)
        
        # 3. Секция настроек (Карточка)
        settings_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        settings_card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(settings_card, text="ТОНКАЯ НАСТРОЙКА", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"]).pack(anchor="w", padx=15, pady=(10, 5))
        
        # Выбор камеры
        tk.Label(settings_card, text="Активная камера:", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="w", padx=15, pady=(5, 2))
        
        self.available_cams = self.scan_cameras()
        cam_options = [f"{name} [ID: {i}]" for i, name in self.available_cams.items()]
        
        self.cam_combobox = ttk.Combobox(
            settings_card, 
            values=cam_options, 
            state="readonly",
            font=("Helvetica", 10)
        )
        current_text = ""
        for opt in cam_options:
            if f"[ID: {self.camera_index}]" in opt:
                current_text = opt
                break
        if current_text:
            self.cam_combobox.set(current_text)
        else:
            first_opt = cam_options[0] if cam_options else "Основная камера [ID: 0]"
            self.cam_combobox.set(first_opt)
            try:
                self.camera_index = int(first_opt.split("[ID: ")[-1].replace("]", ""))
            except Exception:
                self.camera_index = 0
            
        self.cam_combobox.pack(fill=tk.X, padx=15, pady=(0, 10))
        self.cam_combobox.bind("<<ComboboxSelected>>", self.on_camera_change)
        
        # Слайдер Чувствительности
        self.sens_label = tk.Label(settings_card, text=f"Чувствительность: {self.sensitivity:.0f}%", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.sens_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        # Кастомный слайдер через Tkinter.Scale
        self.sens_slider = tk.Scale(
            settings_card, 
            from_=1.0, to=99.0, 
            orient=tk.HORIZONTAL, 
            bg=self.colors["card"], 
            fg=self.colors["text"],
            troughcolor=self.colors["bg"], 
            activebackground=self.colors["accent"],
            highlightthickness=0, 
            bd=0, 
            showvalue=False,
            command=self.on_sensitivity_change
        )
        self.sens_slider.set(self.sensitivity)
        self.sens_slider.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # Слайдер Прозрачности оверлея
        self.opacity_label = tk.Label(settings_card, text=f"Прозрачность баннера: {self.overlay_opacity*100:.0f}%", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.opacity_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        self.opacity_slider = tk.Scale(
            settings_card, 
            from_=20.0, to=100.0, 
            orient=tk.HORIZONTAL, 
            bg=self.colors["card"], 
            fg=self.colors["text"],
            troughcolor=self.colors["bg"], 
            activebackground=self.colors["accent"],
            highlightthickness=0, 
            bd=0, 
            showvalue=False,
            command=self.on_opacity_change
        )
        self.opacity_slider.set(self.overlay_opacity * 100.0)
        self.opacity_slider.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # Слайдер Частоты опроса (кадров в секунду)
        self.fps_label = tk.Label(settings_card, text=f"Частота опроса: {self.poll_fps:.0f} кадр/сек", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.fps_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        self.fps_slider = tk.Scale(
            settings_card, 
            from_=2.0, to=30.0, 
            orient=tk.HORIZONTAL, 
            bg=self.colors["card"], 
            fg=self.colors["text"],
            troughcolor=self.colors["bg"], 
            activebackground=self.colors["accent"],
            highlightthickness=0, 
            bd=0, 
            showvalue=False,
            command=self.on_fps_change
        )
        self.fps_slider.set(self.poll_fps)
        self.fps_slider.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # Слайдер Задержки срабатывания (debounce)
        self.debounce_label = tk.Label(settings_card, text=f"Задержка баннера: {self.debounce_time:.1f} сек", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.debounce_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        self.debounce_slider = tk.Scale(
            settings_card, 
            from_=0.0, to=3.0, 
            resolution=0.1,
            orient=tk.HORIZONTAL, 
            bg=self.colors["card"], 
            fg=self.colors["text"],
            troughcolor=self.colors["bg"], 
            activebackground=self.colors["accent"],
            highlightthickness=0, 
            bd=0, 
            showvalue=False,
            command=self.on_debounce_change
        )
        self.debounce_slider.set(self.debounce_time)
        self.debounce_slider.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # Кнопка Сброса/Сохранения
        btn_reset = tk.Button(
            settings_card,
            text="🔄 Сбросить калибровку",
            font=("Helvetica", 10),
            bg="#424242", fg="white",
            activebackground="#212121", activeforeground="white",
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=12,
            command=self.reset_calibration
        )
        btn_reset.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(25, 20), ipady=6)

    def request_calibrate_relaxed(self) -> None:
        """Отправляет запрос на калибровку спокойного лица."""
        self.calibrate_relaxed_requested = True
        
    def request_calibrate_frowned(self) -> None:
        """Отправляет запрос на калибровку нахмуренного лица."""
        self.calibrate_frowned_requested = True
        
    def reset_calibration(self) -> None:
        """Сбрасывает калибровочные значения к заводским."""
        self.relaxed_score = 1.20
        self.frowned_score = 0.85
        self.detector.set_calibration(self.relaxed_score, self.frowned_score)
        self.save_config()
        messagebox.showinfo("Сброс", "Калибровочные данные сброшены к стандартным значениям.")
        
    def on_sensitivity_change(self, value: str) -> None:
        """Вызывается при изменении чувствительности слайдером."""
        val = float(value)
        self.sensitivity = val
        self.detector.sensitivity = val
        self.sens_label.configure(text=f"Чувствительность: {val:.0f}%")
        self.save_config()
        
    def on_opacity_change(self, value: str) -> None:
        """Вызывается при изменении прозрачности оверлея."""
        val = float(value) / 100.0
        self.overlay_opacity = val
        self.overlay.set_opacity(val)
        self.opacity_label.configure(text=f"Прозрачность баннера: {val*100:.0f}%")
        self.save_config()
        
    def on_fps_change(self, value: str) -> None:
        """Вызывается при изменении частоты опроса."""
        val = float(value)
        self.poll_fps = val
        self.fps_label.configure(text=f"Частота опроса: {val:.0f} кадр/сек")
        self.save_config()
        
    def on_debounce_change(self, value: str) -> None:
        """Вызывается при изменении задержки появления баннера."""
        val = float(value)
        self.debounce_time = val
        self.debounce_label.configure(text=f"Задержка баннера: {val:.1f} сек")
        self.save_config()
        
    def scan_cameras(self) -> Dict[int, str]:
        """
        Сканирует доступные веб-камеры в системе.
        Возвращает словарь {индекс: "Имя веб-камеры"}.
        """
        cameras = {}
        # Опрашиваем первые 8 индексов в системе
        for i in range(8):
            device_name = ""
            # Попытка получить имя на Linux через sysfs
            name_file = f"/sys/class/video4linux/video{i}/name"
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r", encoding="utf-8") as f:
                        device_name = f.read().strip()
                        # Очищаем имя от повторений
                        if ":" in device_name:
                            device_name = device_name.split(":")[0].strip()
                except Exception:
                    pass
            
            # Если имя не найдено (или мы на другой ОС)
            if not device_name:
                device_name = f"Камера {i}"
                
            # Проверяем работоспособность камеры
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Пробуем считать реальный кадр.
                # Это отсеивает чисто сервисные каналы метаданных в Linux (v4l2), 
                # которые открываются, но не выдают видео.
                ret, _ = cap.read()
                if ret:
                    cameras[i] = device_name
                cap.release()
                
        # Если из-за занятости другими приложениями ни одна камера не прошла проверку через read(),
        # делаем мягкую проверку (просто по существованию устройства в v4l2)
        if not cameras:
            for i in range(5):
                name_file = f"/sys/class/video4linux/video{i}/name"
                if os.path.exists(name_file):
                    try:
                        with open(name_file, "r", encoding="utf-8") as f:
                            name = f.read().strip().split(":")[0].strip()
                            if "metadata" not in name.lower() and "association" not in name.lower():
                                cameras[i] = name
                    except Exception:
                        pass
                        
        # Если список всё ещё пуст, даем дефолтный индекс 0
        if not cameras:
            cameras[0] = "Основная камера"
            
        return cameras
        
    def on_camera_change(self, event: Any) -> None:
        """Обрабатывает выбор новой камеры из списка."""
        selected_str = self.cam_combobox.get()
        # Извлекаем ID из строки формата "Название камеры [ID: X]"
        try:
            parts = selected_str.split("[ID: ")
            new_index = int(parts[-1].replace("]", "").strip())
        except Exception:
            new_index = 0
            
        if new_index == self.camera_index and self.cap is not None:
            return
            
        self.camera_index = new_index
        self.save_config()
        
        self.status_text_label.configure(text="Переключение камеры...", fg=self.colors["accent"])
        
        # Переключаем камеру в фоновом потоке, чтобы GUI не зависал
        threading.Thread(target=self._switch_camera_resource, daemon=True).start()
        
    def _switch_camera_resource(self) -> None:
        """Безопасно переподключает захват камеры в фоновом потоке."""
        # Открываем новую камеру ВНЕ лока, так как это долгая операция на уровне ОС
        new_cap = cv2.VideoCapture(self.camera_index)
        
        with self.cap_lock:
            old_cap = self.cap
            self.cap = None  # Фоновый рабочий поток временно будет спать
            
            if old_cap is not None:
                old_cap.release()
                
            if new_cap.isOpened():
                self.cap = new_cap
                success = True
            else:
                new_cap.release()
                success = False
                
        if not success:
            # Пытаемся вернуться на первую доступную рабочую камеру
            fallback_index = 0
            if self.available_cams:
                fallback_index = list(self.available_cams.keys())[0]
                
            fallback_cap = cv2.VideoCapture(fallback_index)
            
            with self.cap_lock:
                if fallback_cap.isOpened():
                    self.cap = fallback_cap
                    self.camera_index = fallback_index
                    self.save_config()
                    # Ищем текст комбобокса, соответствующий fallback_index
                    for opt in self.cam_combobox["values"]:
                        if f"[ID: {fallback_index}]" in opt:
                            self.root.after(0, lambda o=opt: self.cam_combobox.set(o))
                            break
                else:
                    fallback_cap.release()
            
            self.root.after(0, lambda: messagebox.showerror(
                "Ошибка камеры", 
                f"Не удалось подключиться к Камере {self.camera_index}."
            ))

    def start_video_stream(self) -> None:
        """Инициализирует веб-камеру и запускает фоновый поток обработки."""
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            messagebox.showerror("Ошибка камеры", "Не удалось получить доступ к веб-камере.\nПроверьте подключение камеры.")
            self.status_text_label.configure(text="Камера не найдена", fg=self.colors["alert"])
            return
            
        # Запускаем фоновый поток обработки
        self.video_thread = threading.Thread(target=self.capture_and_process, daemon=True)
        self.video_thread.start()
        
    def capture_and_process(self) -> None:
        """
        Фоновый цикл:
        1. Читает кадры с камеры.
        2. Прогоняет через детектор MediaPipe.
        3. Рисует визуальные ориентиры.
        4. Конвертирует в ImageTk и передает в GUI поток.
        """
        while self.is_running:
            with self.cap_lock:
                if self.cap is None or not self.cap.isOpened():
                    cap_is_valid = False
                else:
                    cap_is_valid = True
                    # Считываем кадр внутри лока, чтобы гарантировать, что ресурс не освободят посреди операции
                    ret, frame = self.cap.read()
                    
            if not cap_is_valid:
                time.sleep(0.1)
                continue
                
            if not ret:
                time.sleep(0.01)
                continue
                
            # Отражаем кадр горизонтально для зеркального эффекта
            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape
            
            # Конвертируем из BGR в RGB для MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Обработка через наш FaceFrownDetector
            metrics, landmarks = self.detector.process_frame(frame_rgb)
            
            # Отрисовка ориентиров на кадре для наглядности (если предпросмотр включен)
            if self.show_video_preview and landmarks is not None:
                # Извлекаем координаты ключевых точек для отрисовки
                try:
                    p_r_brow = landmarks[self.detector.RIGHT_EYEBROW_INNER]
                    p_l_brow = landmarks[self.detector.LEFT_EYEBROW_INNER]
                    p_r_eye = landmarks[self.detector.RIGHT_EYE_INNER]
                    p_l_eye = landmarks[self.detector.LEFT_EYE_INNER]
                    
                    # Переводим из относительных координат в пиксельные
                    px_r_brow = (int(p_r_brow.x * w), int(p_r_brow.y * h))
                    px_l_brow = (int(p_l_brow.x * w), int(p_l_brow.y * h))
                    px_r_eye = (int(p_r_eye.x * w), int(p_r_eye.y * h))
                    px_l_eye = (int(p_l_eye.x * w), int(p_l_eye.y * h))
                    
                    # Цвет отрисовки меняется в зависимости от того, хмурится ли пользователь
                    color_marker = (50, 220, 50) if not (metrics and metrics["is_frowning"]) else (50, 50, 255)
                    
                    # Рисуем точки глаз и бровей
                    cv2.circle(frame_rgb, px_r_brow, 4, color_marker, -1)
                    cv2.circle(frame_rgb, px_l_brow, 4, color_marker, -1)
                    cv2.circle(frame_rgb, px_r_eye, 4, (255, 100, 0), -1)
                    cv2.circle(frame_rgb, px_l_eye, 4, (255, 100, 0), -1)
                    
                    # Рисуем линии контроля
                    cv2.line(frame_rgb, px_r_brow, px_l_brow, color_marker, 2)
                    cv2.line(frame_rgb, px_r_brow, px_r_eye, (0, 180, 255), 1)
                    cv2.line(frame_rgb, px_l_brow, px_l_eye, (0, 180, 255), 1)
                    
                except Exception as draw_err:
                    print(f"Ошибка рисования маркеров: {draw_err}")
            
            # Подготовка кадра для GUI
            pil_img = None
            if self.show_video_preview:
                # Масштабируем кадр, чтобы он красиво умещался в панель видео
                # Максимальный размер 540x400
                max_w, max_h = 540, 400
                scale = min(max_w / w, max_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
                
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
                pil_img = Image.fromarray(frame_resized)
                
            # Передаем кадр и метрики в очередь
            try:
                # Очищаем очередь, если она полная, чтобы не было задержек (лага) видео
                if self.video_queue.full():
                    try:
                        self.video_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.video_queue.put_nowait((pil_img, metrics))
            except Exception:
                pass
                
            # Рассчитываем динамическую паузу на основе выбранной частоты опроса (от 2 до 30 кадров/сек)
            sleep_time = 1.0 / max(2.0, self.poll_fps)
            time.sleep(sleep_time)

    def poll_queue(self) -> None:
        """
        Регулярный опрос очереди в потоке GUI.
        Обновляет изображение на экране, прогресс-бары, текст и статус оверлея.
        """
        if not self.is_running:
            return
            
        latest_item = None
        # Забираем самый последний кадр из очереди, чтобы видео было плавным и без задержек
        while not self.video_queue.empty():
            try:
                latest_item = self.video_queue.get_nowait()
            except queue.Empty:
                break
                
        if latest_item is not None:
            pil_img, metrics = latest_item
            
            # 1. Обновляем картинку веб-камеры
            if self.show_video_preview and pil_img is not None:
                try:
                    img_tk = ImageTk.PhotoImage(image=pil_img)
                    self.video_label.configure(image=img_tk)
                    self.video_label.image = img_tk  # Сохраняем ссылку на объект!
                except Exception as tk_img_err:
                    print(f"Ошибка вывода кадра в Tkinter: {tk_img_err}")
            
            # 2. Обновляем метрики и интерфейс контроля
            if metrics is not None:
                frown_pct = metrics["frown_level_pct"]
                threshold_pct = metrics["threshold_pct"]
                is_frowning = metrics["is_frowning"]
                score = metrics["combined_score"]
                
                # Буферизуем текущий балл для калибровки
                self.last_combined_score = score
                
                # Обновляем прогресс-бар уровня хмурости
                self.frown_bar.place(relwidth=frown_pct / 100.0)
                
                # Позиционируем линию порога
                self.threshold_line.place(relx=threshold_pct / 100.0)
                
                # Текст, цвета и задержка появления (debounce)
                if is_frowning:
                    if self.frowning_start_time is None:
                        self.frowning_start_time = time.time()
                        
                    elapsed = time.time() - self.frowning_start_time
                    
                    if elapsed >= self.debounce_time:
                        self.status_text_label.configure(text="ХМУРИТЕСЬ! 😡", fg=self.colors["alert"])
                        self.frown_bar.configure(bg=self.colors["alert"])
                        # Показываем оверлей
                        self.overlay.show_warning()
                    else:
                        # Хмурится, но задержка еще не прошла
                        self.status_text_label.configure(text="Внимание... ⏳", fg="#FFC107")  # Янтарный предупреждающий
                        self.frown_bar.configure(bg="#FFC107")
                        self.overlay.hide_warning()
                else:
                    self.frowning_start_time = None
                    self.status_text_label.configure(text="Все отлично! 😊", fg=self.colors["success"])
                    self.frown_bar.configure(bg=self.colors["success"])
                    # Скрываем оверлей
                    self.overlay.hide_warning()
                    
                # Подпись с численными данными
                self.metrics_label.configure(
                    text=f"Метрика: {score:.3f} | Порог: {self.detector.relaxed_score - (self.detector.relaxed_score - self.detector.frowned_score) * (threshold_pct / 100.0):.3f}\n"
                         f"Хмурость: {frown_pct:.1f}% / Порог: {threshold_pct:.1f}%"
                )
                
                # Выполняем калибровку в безопасном GUI-потоке, если были нажаты кнопки
                if self.calibrate_relaxed_requested:
                    self.calibrate_relaxed_requested = False
                    self.relaxed_score = self.last_combined_score
                    self.detector.set_calibration(self.relaxed_score, self.frowned_score)
                    self.save_config()
                    messagebox.showinfo("Калибровка", f"Спокойное лицо успешно откалибровано!\nЗначение: {self.relaxed_score:.3f}")
                    
                if self.calibrate_frowned_requested:
                    self.calibrate_frowned_requested = False
                    self.frowned_score = self.last_combined_score
                    self.detector.set_calibration(self.relaxed_score, self.frowned_score)
                    self.save_config()
                    messagebox.showinfo("Калибровка", f"Нахмуренное лицо успешно откалибровано!\nЗначение: {self.frowned_score:.3f}")
            else:
                # Если лицо не найдено в кадре
                self.frowning_start_time = None
                self.status_text_label.configure(text="Лицо не обнаружено 👤", fg=self.colors["text_muted"])
                self.frown_bar.place(relwidth=0.0)
                self.overlay.hide_warning()
                
        # Назначаем следующий вызов poll_queue через 15 мс (примерно 60 FPS опроса)
        self.root.after(15, self.poll_queue)
        
    def on_closing(self) -> None:
        """Очищает ресурсы при выходе из приложения."""
        self.is_running = False
        
        # Освобождаем оверлей
        try:
            self.overlay.destroy()
        except Exception:
            pass
            
        # Останавливаем камеру под защитой лока
        with self.cap_lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            
        # Закрываем детектор
        try:
            self.detector.close()
        except Exception:
            pass
            
        # Закрываем Tkinter
        self.root.destroy()
