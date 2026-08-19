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
from frown_guard.translations import TRANSLATIONS

class FrownGuardApp:
    """
    The main Frown Guard GUI control center.
    Provides a dark-themed dashboard featuring a live camera preview feed, 
    individual user calibration buttons, sensitivity customization, and overlay management.
    """
    CONFIG_FILE = "config.json"
    
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Frown Guard — Expression Control")
        self.root.geometry("946x774")
        self.root.resizable(True, True)
        
        # Configure color palette (modern dark Material theme)
        self.colors = {
            "bg": "#121212",         # Main background
            "card": "#1E1E1E",       # Card and panel background
            "text": "#E0E0E0",       # Primary body text
            "text_muted": "#888888", # Secondary muted text
            "accent": "#00ADB5",     # Teal accent color
            "accent_hover": "#00F5FF",
            "alert": "#FF5722",      # Orange-red alert color on frown
            "success": "#4CAF50",    # Green color when relaxed
            "border": "#2D2D2D"      # Structural grid dividers
        }
        
        self.root.configure(bg=self.colors["bg"])
        
        # Configuration variables (loaded from config.json or fallback defaults)
        self.relaxed_score = 1.20
        self.frowned_score = 0.85
        self.sensitivity = 50.0
        self.overlay_opacity = 0.9
        self.show_video_preview = True
        self.camera_index = 0
        self.poll_fps = 30.0
        self.debounce_time = 0.5
        self.current_lang = "EN"
        self.translations = TRANSLATIONS
        self.face_tracking_enabled = True
        self.smooth_box = None
        self.camera_active = True
        
        self.load_config()
        
        # Initialize facial expression detector and window overlay
        self.detector = FaceFrownDetector()
        self.detector.set_calibration(self.relaxed_score, self.frowned_score)
        self.detector.sensitivity = self.sensitivity
        
        self.overlay = FrownWarningOverlay(self.root)
        self.overlay.set_opacity(self.overlay_opacity)
        
        # Mutex lock for thread-safe access to the cv2.VideoCapture pointer
        self.cap_lock = threading.Lock()
        
        # Video capture worker thread and frame queue
        self.video_queue: queue.Queue = queue.Queue(maxsize=2)
        self.is_running = True
        self.cap: Optional[cv2.VideoCapture] = None
        self.video_thread: Optional[threading.Thread] = None
        
        # Calibration request flags triggered from GUI events
        self.calibrate_relaxed_requested = False
        self.calibrate_frowned_requested = False
        self.last_combined_score = 1.0  # Buffer to store the last combined metric score
        self.frowning_start_time: Optional[float] = None
        
        # Logical tracker state (to localize text on-the-fly without fragile string comparisons)
        # Possible values: "searching", "frowning", "warning", "relaxed", "no_face", "no_cam"
        self.tracker_state: str = "searching"
        
        # Styling configurations for ttk widgets (with dark theme support)
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure(".", background=self.colors["bg"], foreground=self.colors["text"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        
        # Configure internal padding and dropdown arrow size for ttk.Combobox
        self.style.configure('TCombobox', 
            padding=(10, 6),  # Margins: 10px sides, 6px top/bottom
            arrowsize=14      # Proportional arrow selector size
        )
        
        # Map Combobox colors to resolve white-on-white text issues on Linux GTK themes
        self.style.map('TCombobox', 
            fieldbackground=[('readonly', self.colors["card"])],
            background=[('readonly', self.colors["card"])],
            foreground=[('readonly', self.colors["text"])],
            selectbackground=[('readonly', self.colors["accent"])],
            selectforeground=[('readonly', self.colors["bg"])]
        )
        
        # Configure the dropdown popup listbox styling explicitly
        self.root.option_add('*TCombobox*Listbox.background', self.colors["card"])
        self.root.option_add('*TCombobox*Listbox.foreground', self.colors["text"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.colors["accent"])
        self.root.option_add('*TCombobox*Listbox.selectForeground', self.colors["bg"])
        
        # Build graphical widgets
        self.create_widgets()
        
        # Start background camera stream
        self.start_video_stream()
        
        # Start polling the processed frames queue
        self.poll_queue()
        
        # Securely release resources upon window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def load_config(self) -> None:
        """Loads calibration parameters from JSON configuration file."""
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
                    self.current_lang = config.get("current_lang", "EN")
                    self.face_tracking_enabled = config.get("face_tracking", True)
                    self.camera_active = config.get("camera_active", True)
            except Exception as e:
                print(f"Could not load config.json: {e}")
                
    def save_config(self) -> None:
        """Saves current configuration to JSON file."""
        try:
            config = {
                "relaxed_score": self.relaxed_score,
                "frowned_score": self.frowned_score,
                "sensitivity": self.sensitivity,
                "overlay_opacity": self.overlay_opacity,
                "camera_index": self.camera_index,
                "poll_fps": self.poll_fps,
                "debounce_time": self.debounce_time,
                "current_lang": self.current_lang,
                "face_tracking": self.face_tracking_enabled,
                "camera_active": self.camera_active
            }
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Could not save config.json: {e}")

    def create_widgets(self) -> None:
        """Creates stylish interface widgets based on the grid/pack layout."""
        # Main container frame with padding
        main_container = tk.Frame(self.root, bg=self.colors["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left column — Video stream preview container
        self.video_frame = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        self.video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Video title label
        self.video_title = tk.Label(
            self.video_frame, 
            text="Expression Monitoring Camera", 
            font=("Helvetica", 12, "bold"),  
            bg=self.colors["card"], 
            fg=self.colors["text"]
        )
        self.video_title.pack(fill=tk.X, pady=10)
        
        # Video display container label
        self.video_label = tk.Label(self.video_frame, bg=self.colors["bg"])
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        
        # Bottom panel inside the video frame (for language selection in the bottom-left corner)
        video_bottom_bar = tk.Frame(self.video_frame, bg=self.colors["card"])
        video_bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(5, 10))
        
        # Language selector label (universal globe icon)
        self.lang_label = tk.Label(
            video_bottom_bar, 
            text="🌐", 
            font=("Segoe UI Emoji", 11), 
            bg=self.colors["card"], 
            fg=self.colors["text_muted"]
        )
        self.lang_label.pack(side=tk.LEFT, padx=(5, 5))
        
        # Interface language selection dropdown
        self.lang_combobox = ttk.Combobox(
            video_bottom_bar, 
            values=["EN", "RU", "DE", "FR"], 
            state="readonly",
            width=6,
            font=("Helvetica", 9)
        )
        self.lang_combobox.set(self.current_lang)
        self.lang_combobox.pack(side=tk.LEFT, padx=(0, 5))
        self.lang_combobox.bind("<<ComboboxSelected>>", self.on_lang_change)
        
        # Right column — Control panel and calibration settings
        control_frame = tk.Frame(main_container, bg=self.colors["bg"], width=320)
        control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        control_frame.pack_propagate(False)
        
        # 1. Status Section (Card)
        status_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        status_card.pack(fill=tk.X, pady=(0, 15))
        
        self.status_title_label = tk.Label(status_card, text="CURRENT STATUS", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"])
        self.status_title_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.status_text_label = tk.Label(status_card, text="Searching face...", font=("Helvetica", 16, "bold"), bg=self.colors["card"], fg=self.colors["accent"])
        self.status_text_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Frown level relative progress bar
        progress_bg = tk.Frame(status_card, bg=self.colors["bg"], height=16)
        progress_bg.pack(fill=tk.X, padx=15, pady=(0, 15))
        progress_bg.pack_propagate(False)
        
        self.frown_bar = tk.Frame(progress_bg, bg=self.colors["accent"])
        self.frown_bar.place(x=0, y=0, relwidth=0.0, relheight=1.0)
        
        # Calibration action threshold indicator line (rendered on top of progress bar)
        self.threshold_line = tk.Frame(progress_bg, bg=self.colors["text_muted"], width=2)
        self.threshold_line.place(relx=0.5, y=0, relheight=1.0)
        
        self.metrics_label = tk.Label(status_card, text="Metric: 0.00 | Threshold: 0.00", font=("Courier", 10), bg=self.colors["card"], fg=self.colors["text_muted"])
        self.metrics_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # 2. Muscle Calibration Card
        calib_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        calib_card.pack(fill=tk.X, pady=(0, 15))
        
        self.calib_title_label = tk.Label(calib_card, text="PERSONAL CALIBRATION", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"])
        self.calib_title_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.calib_desc_label = tk.Label(
            calib_card, 
            text="Click 'Relaxed Face' while looking straight and relaxed. Then frown and click 'Frowned Face'.", 
            font=("Helvetica", 9), 
            bg=self.colors["card"], 
            fg=self.colors["text_muted"], 
            justify=tk.LEFT,
            wraplength=280
        )
        self.calib_desc_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Calibration action buttons with flat modern styles
        self.btn_cal_relaxed = tk.Button(
            calib_card, 
            text="😊 Relaxed Face", 
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
            text="😡 Frowned Face", 
            font=("Helvetica", 11, "bold"),
            bg="#C62828", fg="white", 
            activebackground="#B71C1C", activeforeground="white",
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=8,
            command=self.request_calibrate_frowned
        )
        self.btn_cal_frowned.pack(fill=tk.X, padx=15, pady=(0, 15), ipady=6)
        
        # 3. Tuning & Preferences Card
        settings_card = tk.Frame(control_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        settings_card.pack(fill=tk.BOTH, expand=True)
        
        self.settings_title_label = tk.Label(settings_card, text="FINE TUNING", font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_muted"])
        self.settings_title_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Camera source dropdown
        self.camera_title_label = tk.Label(settings_card, text="Active Camera:", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.camera_title_label.pack(anchor="w", padx=15, pady=(5, 2))
        
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
            first_opt = cam_options[0] if cam_options else "Default Camera [ID: 0]"
            self.cam_combobox.set(first_opt)
            try:
                self.camera_index = int(first_opt.split("[ID: ")[-1].replace("]", ""))
            except Exception:
                self.camera_index = 0
            
        self.cam_combobox.pack(fill=tk.X, padx=15, pady=(0, 10))
        self.cam_combobox.bind("<<ComboboxSelected>>", self.on_camera_change)
        
        # Sensitivity slider
        self.sens_label = tk.Label(settings_card, text=f"Sensitivity: {self.sensitivity:.0f}%", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
        self.sens_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        # Custom flat slider using Tkinter.Scale
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
        
        # Overlay opacity slider
        self.opacity_label = tk.Label(settings_card, text=f"Banner Opacity: {self.overlay_opacity*100:.0f}%", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
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
        
        # Polling rate slider (Frames Per Second)
        self.fps_label = tk.Label(settings_card, text=f"Polling Rate: {self.poll_fps:.0f} FPS", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
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
        
        # Response delay debounce slider
        self.debounce_label = tk.Label(settings_card, text=f"Banner Delay: {self.debounce_time:.1f} sec", font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"])
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
        
        # Checkbox for Camera ON/OFF
        self.chk_camera_on_var = tk.BooleanVar(value=self.camera_active)
        self.chk_camera_on = tk.Checkbutton(
            settings_card, 
            text="Enable Camera", 
            variable=self.chk_camera_on_var,
            bg=self.colors["card"], 
            fg=self.colors["text"],
            activebackground=self.colors["card"], 
            activeforeground=self.colors["text"],
            selectcolor=self.colors["bg"],
            font=("Helvetica", 10),
            command=self.toggle_camera_active
        )
        self.chk_camera_on.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Checkbox for Face Auto-Tracking (Zoom)
        self.chk_tracking_var = tk.BooleanVar(value=self.face_tracking_enabled)
        self.chk_tracking = tk.Checkbutton(
            settings_card, 
            text="Face Tracking", 
            variable=self.chk_tracking_var,
            bg=self.colors["card"], 
            fg=self.colors["text"],
            activebackground=self.colors["card"], 
            activeforeground=self.colors["text"],
            selectcolor=self.colors["bg"],
            font=("Helvetica", 10),
            command=self.toggle_tracking
        )
        self.chk_tracking.pack(anchor="w", padx=15, pady=(5, 5))
        
        # Reset and save calibration buttons
        self.btn_reset = tk.Button(
            settings_card,
            text="🔄 Reset Calibration",
            font=("Helvetica", 10),
            bg="#424242", fg="white",
            activebackground="#212121", activeforeground="white",
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=12,
            command=self.reset_calibration
        )
        self.btn_reset.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(25, 20), ipady=6)
        
        # Refresh all UI labels according to current localization
        self.update_ui_text()

    def request_calibrate_relaxed(self) -> None:
        """Sends a request to calibrate the relaxed face baseline."""
        self.calibrate_relaxed_requested = True
        
    def request_calibrate_frowned(self) -> None:
        """Sends a request to calibrate the frowned face baseline."""
        self.calibrate_frowned_requested = True
        
    def reset_calibration(self) -> None:
        """Resets calibration coefficients back to factory defaults."""
        self.relaxed_score = 1.20
        self.frowned_score = 0.85
        self.detector.set_calibration(self.relaxed_score, self.frowned_score)
        self.save_config()
        t = self.translations[self.current_lang]
        messagebox.showinfo(t["msg_reset_title"], t["msg_reset_ok"])
        
    def on_sensitivity_change(self, value: str) -> None:
        """Callback triggered when the sensitivity slider is dragged."""
        val = float(value)
        self.sensitivity = val
        self.detector.sensitivity = val
        fmt = self.translations[self.current_lang]["sens_label_fmt"]
        self.sens_label.configure(text=fmt.format(sens=val))
        self.save_config()
        
    def on_opacity_change(self, value: str) -> None:
        """Triggered when the opacity slider is dragged."""
        val = float(value) / 100.0
        self.overlay_opacity = val
        self.overlay.set_opacity(val)
        fmt = self.translations[self.current_lang]["opacity_label_fmt"]
        self.opacity_label.configure(text=fmt.format(opacity=val*100.0))
        self.save_config()
        
    def on_fps_change(self, value: str) -> None:
        """Triggered when the polling FPS slider is dragged."""
        val = float(value)
        self.poll_fps = val
        fmt = self.translations[self.current_lang]["fps_label_fmt"]
        self.fps_label.configure(text=fmt.format(fps=val))
        self.save_config()
        
    def on_debounce_change(self, value: str) -> None:
        """Triggered when the banner debounce delay slider is dragged."""
        val = float(value)
        self.debounce_time = val
        fmt = self.translations[self.current_lang]["debounce_label_fmt"]
        self.debounce_label.configure(text=fmt.format(debounce=val))
        self.save_config()
        
    def on_lang_change(self, event: Any) -> None:
        """Triggered when the selected interface language is swapped in combobox."""
        self.current_lang = self.lang_combobox.get()
        self.save_config()
        self.update_ui_text()
        
    def toggle_tracking(self) -> None:
        """Toggles face auto-zooming tracking mode."""
        self.face_tracking_enabled = self.chk_tracking_var.get()
        if not self.face_tracking_enabled:
            self.smooth_box = None
        self.save_config()
        
    def toggle_camera_active(self) -> None:
        """Toggles camera active state."""
        self.camera_active = self.chk_camera_on_var.get()
        if not self.camera_active:
            self.smooth_box = None
        self.save_config()
        
    def update_ui_text(self) -> None:
        """Re-renders all interface labels and layouts according to the chosen language."""
        lang = self.current_lang
        t = self.translations[lang]
        
        # Update main window title
        self.root.title(t["window_title"])
        
        # Update floating warning banner
        self.overlay.title_label.configure(text=t["overlay_title"])
        self.overlay.subtitle_label.configure(text=t["overlay_subtitle"])
        
        # Left column guides
        self.video_title.configure(text=t["video_title"])
        
        # Right column (Section headers)
        self.status_title_label.configure(text=t["status_header"])
        self.calib_title_label.configure(text=t["calib_header"])
        self.calib_desc_label.configure(text=t["calib_desc"])
        self.settings_title_label.configure(text=t["settings_header"])
        self.camera_title_label.configure(text=t["camera_label"])
        
        # Interactive buttons
        self.btn_cal_relaxed.configure(text=t["btn_relaxed"])
        self.btn_cal_frowned.configure(text=t["btn_frowned"])
        self.btn_reset.configure(text=t["btn_reset"])
        self.chk_tracking.configure(text=t["tracking_label"])
        self.chk_camera_on.configure(text=t["camera_active_label"])
        
        # Slider descriptions formatting
        self.sens_label.configure(text=t["sens_label_fmt"].format(sens=self.sensitivity))
        self.opacity_label.configure(text=t["opacity_label_fmt"].format(opacity=self.overlay_opacity * 100.0))
        self.fps_label.configure(text=t["fps_label_fmt"].format(fps=self.poll_fps))
        self.debounce_label.configure(text=t["debounce_label_fmt"].format(debounce=self.debounce_time))
        
        # Update static tracker status label based on our logical state
        if hasattr(self, "status_text_label") and self.tracker_state:
            self.status_text_label.configure(text=t[f"status_{self.tracker_state}"])
        
    def scan_cameras(self) -> Dict[int, str]:
        """
        Scans available system webcams using both v4l2 device nodes and capture tests.
        Returns a dictionary mapping {index: "Camera Name"}.
        """
        cameras = {}
        # Poll the first 8 device indices in the system
        for i in range(8):
            device_name = ""
            # Attempt to read camera product name on Linux via sysfs directory
            name_file = f"/sys/class/video4linux/video{i}/name"
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r", encoding="utf-8") as f:
                        device_name = f.read().strip()
                        # Clean up repeating keywords
                        if ":" in device_name:
                            device_name = device_name.split(":")[0].strip()
                except Exception:
                    pass
            
            # Fallback if name is not found (or running on macOS/Windows)
            if not device_name:
                device_name = f"Camera {i}"
                
            # Validate that camera resource is openable
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Attempt to read a real frame.
                # This successfully filters out metadata-only/auxiliary v4l2 sub-devices on Linux,
                # which can be opened but fail to stream video matrices.
                ret, _ = cap.read()
                if ret:
                    cameras[i] = device_name
                cap.release()
                
        # Fallback check using device listings if cameras are busy or capture test fails
        if not cameras:
            for i in range(5):
                name_file = f"/sys/class/video4linux/video{i}/name"
                if os.path.exists(name_file):
                    try:
                        with open(name_file, "r", encoding="utf-8") as f:
                            name = f.read().strip().split(":")[0].strip()
                            # Ignore obvious metadata nodes by checking sub-device names
                            if "metadata" not in name.lower() and "association" not in name.lower():
                                cameras[i] = name
                    except Exception:
                        pass
                        
        # Fallback to default index 0 if list remains empty
        if not cameras:
            cameras[0] = "Default Camera"
            
        return cameras
        
    def on_camera_change(self, event: Any) -> None:
        """Triggered when another camera is selected from the combobox."""
        selected_str = self.cam_combobox.get()
        # Parse system camera index from string formatted as "Name [ID: X]"
        try:
            parts = selected_str.split("[ID: ")
            new_index = int(parts[-1].replace("]", "").strip())
        except Exception:
            new_index = 0
            
        if new_index == self.camera_index and self.cap is not None:
            return
            
        self.camera_index = new_index
        self.save_config()
        
        self.status_text_label.configure(text="Switching camera...", fg=self.colors["accent"])
        
        # Swap camera resources in a background thread to prevent GUI lockups
        threading.Thread(target=self._switch_camera_resource, daemon=True).start()
        
    def _switch_camera_resource(self) -> None:
        """Safely reconnects to the newly selected camera in a background thread."""
        # Instantiate VideoCapture outside the mutex lock (takes up to 1s on OS drivers)
        new_cap = cv2.VideoCapture(self.camera_index)
        
        with self.cap_lock:
            old_cap = self.cap
            self.cap = None  # Set self.cap = None to put the processing worker thread to sleep
            
            if old_cap is not None:
                old_cap.release()
                
            if new_cap.isOpened():
                self.cap = new_cap
                success = True
            else:
                new_cap.release()
                success = False
                
        if not success:
            # Fallback to the first available working device on failure
            fallback_index = 0
            if self.available_cams:
                fallback_index = list(self.available_cams.keys())[0]
                
            fallback_cap = cv2.VideoCapture(fallback_index)
            
            with self.cap_lock:
                if fallback_cap.isOpened():
                    self.cap = fallback_cap
                    self.camera_index = fallback_index
                    self.save_config()
                    # Restore combobox selection to the fallback device
                    for opt in self.cam_combobox["values"]:
                        if f"[ID: {fallback_index}]" in opt:
                            self.root.after(0, lambda o=opt: self.cam_combobox.set(o))
                            break
                else:
                    fallback_cap.release()
            
            t = self.translations[self.current_lang]
            self.root.after(0, lambda: messagebox.showerror(
                t["msg_cam_err_title"], 
                t["msg_cam_err_switch"]
            ))

    def start_video_stream(self) -> None:
        """Initializes the webcam device and spawns the background worker processing thread."""
        self.cap = cv2.VideoCapture(self.camera_index)
        t = self.translations[self.current_lang]
        if not self.cap.isOpened():
            self.tracker_state = "no_cam"
            messagebox.showerror(t["msg_cam_err_title"], t["msg_cam_err_access"])
            self.status_text_label.configure(text=t["status_no_cam"], fg=self.colors["alert"])
            return
            
        # Spawns background worker processing thread
        self.video_thread = threading.Thread(target=self.capture_and_process, daemon=True)
        self.video_thread.start()
        
    def capture_and_process(self) -> None:
        """
        Background processing loop:
        1. Captures webcam frames;
        2. Analyzes expression landmarks;
        3. Annotates frames;
        4. Injects frames into the Tkinter queue.
        """
        while self.is_running:
            if not self.camera_active:
                # Free camera resources immediately
                with self.cap_lock:
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
                
                # Inject an empty frame and "paused" state metrics
                metrics = {
                    "combined_score": 1.0,
                    "frown_level_pct": 0.0,
                    "threshold_pct": 50.0,
                    "is_frowning": False,
                    "status": "paused"
                }
                try:
                    if self.video_queue.full():
                        try:
                            self.video_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.video_queue.put_nowait((None, metrics))
                except Exception:
                    pass
                time.sleep(0.1)
                continue

            with self.cap_lock:
                # If camera is active but self.cap was released, re-open it!
                if self.cap is None:
                    self.cap = cv2.VideoCapture(self.camera_index)
                
                if not self.cap.isOpened():
                    cap_is_valid = False
                else:
                    cap_is_valid = True
                    # Safely read a frame while holding the mutex lock
                    ret, frame = self.cap.read()
                    
            if not cap_is_valid:
                time.sleep(0.1)
                continue
                
            if not ret:
                time.sleep(0.01)
                continue
                
            # Flip frame horizontally for mirror-like visual experience
            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape
            
            # Convert BGR to RGB for MediaPipe consumption
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process frame through FaceFrownDetector
            metrics, landmarks = self.detector.process_frame(frame_rgb)
            
            # Draw key guide landmarks on top of frame (if preview is enabled)
            if self.show_video_preview and landmarks is not None:
                # Extract coordinate positions of key eyebrows and eyes guides
                try:
                    p_r_brow = landmarks[self.detector.RIGHT_EYEBROW_INNER]
                    p_l_brow = landmarks[self.detector.LEFT_EYEBROW_INNER]
                    p_r_eye = landmarks[self.detector.RIGHT_EYE_INNER]
                    p_l_eye = landmarks[self.detector.LEFT_EYE_INNER]
                    
                    # Map normalized coordinates back to actual pixel dimensions
                    px_r_brow = (int(p_r_brow.x * w), int(p_r_brow.y * h))
                    px_l_brow = (int(p_l_brow.x * w), int(p_l_brow.y * h))
                    px_r_eye = (int(p_r_eye.x * w), int(p_r_eye.y * h))
                    px_l_eye = (int(p_l_eye.x * w), int(p_l_eye.y * h))
                    
                    # Draw green points normally, or red points if user is frowning
                    color_marker = (50, 220, 50) if not (metrics and metrics["is_frowning"]) else (50, 50, 255)
                    
                    # Render eyebrows and inner eye points
                    cv2.circle(frame_rgb, px_r_brow, 4, color_marker, -1)
                    cv2.circle(frame_rgb, px_l_brow, 4, color_marker, -1)
                    cv2.circle(frame_rgb, px_r_eye, 4, (255, 100, 0), -1)
                    cv2.circle(frame_rgb, px_l_eye, 4, (255, 100, 0), -1)
                    
                    # Render horizontal and vertical guidance lines
                    cv2.line(frame_rgb, px_r_brow, px_l_brow, color_marker, 2)
                    cv2.line(frame_rgb, px_r_brow, px_r_eye, (0, 180, 255), 1)
                    cv2.line(frame_rgb, px_l_brow, px_l_eye, (0, 180, 255), 1)
                    
                except Exception as draw_err:
                    print(f"Error rendering facial markers: {draw_err}")
            
            # Apply face tracking zoom if enabled
            if self.face_tracking_enabled and landmarks is not None:
                try:
                    xs = [lm.x for lm in landmarks]
                    ys = [lm.y for lm in landmarks]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    
                    box_w = x_max - x_min
                    box_h = y_max - y_min
                    
                    # Add generous margin for a natural crop of head/shoulders
                    pad_x = box_w * 0.45
                    pad_y = box_h * 0.55
                    
                    target_x_min = max(0.0, x_min - pad_x)
                    target_x_max = min(1.0, x_max + pad_x)
                    target_y_min = max(0.0, y_min - pad_y)
                    target_y_max = min(1.0, y_max + pad_y)
                    
                    # Force target box aspect ratio to match the camera frame aspect ratio
                    target_w = target_x_max - target_x_min
                    target_h = target_y_max - target_y_min
                    frame_aspect = w / h
                    box_aspect = (target_w * w) / (target_h * h)
                    
                    if box_aspect > frame_aspect:
                        needed_h = (target_w * w) / (frame_aspect * h)
                        center_y = (target_y_min + target_y_max) / 2.0
                        target_y_min = max(0.0, center_y - needed_h / 2.0)
                        target_y_max = min(1.0, center_y + needed_h / 2.0)
                    else:
                        needed_w = (target_h * h * frame_aspect) / w
                        center_x = (target_x_min + target_x_max) / 2.0
                        target_x_min = max(0.0, center_x - needed_w / 2.0)
                        target_x_max = min(1.0, center_x + needed_w / 2.0)
                        
                    # Apply LERP (Linear Interpolation) to smooth out camera movements
                    if self.smooth_box is None:
                        self.smooth_box = (target_x_min, target_y_min, target_x_max, target_y_max)
                    else:
                        alpha = 0.08  # LERP factor (lower = smoother, higher = faster)
                        s_x_min, s_y_min, s_x_max, s_y_max = self.smooth_box
                        self.smooth_box = (
                            s_x_min + alpha * (target_x_min - s_x_min),
                            s_y_min + alpha * (target_y_min - s_y_min),
                            s_x_max + alpha * (target_x_max - s_x_max),
                            s_y_max + alpha * (target_y_max - s_y_max)
                        )
                        
                    # Crop image to the smoothed tracking bounding box
                    s_x_min, s_y_min, s_x_max, s_y_max = self.smooth_box
                    px_min_x = max(0, min(w - 1, int(s_x_min * w)))
                    px_max_x = max(px_min_x + 10, min(w, int(s_x_max * w)))
                    px_min_y = max(0, min(h - 1, int(s_y_min * h)))
                    px_max_y = max(px_min_y + 10, min(h, int(s_y_max * h)))
                    
                    frame_rgb = frame_rgb[px_min_y:px_max_y, px_min_x:px_max_x]
                except Exception as track_err:
                    print(f"Error executing face zoom tracking: {track_err}")
            else:
                self.smooth_box = None
            
            # Scale and convert frame for Tkinter canvas consumption
            pil_img = None
            if self.show_video_preview:
                curr_h, curr_w, _ = frame_rgb.shape
                max_w, max_h = 540, 400
                scale = min(max_w / curr_w, max_h / curr_h)
                new_w, new_h = int(curr_w * scale), int(curr_h * scale)
                
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
                pil_img = Image.fromarray(frame_resized)
                
            # Inject finished frame and status dictionary into the GUI queue
            try:
                # Purge backed-up frames in queue to maintain realtime response and zero lag
                if self.video_queue.full():
                    try:
                        self.video_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.video_queue.put_nowait((pil_img, metrics))
            except Exception:
                pass
                
            # Sleep dynamically based on selected polling FPS to save CPU load
            sleep_time = 1.0 / max(2.0, self.poll_fps)
            time.sleep(sleep_time)

    def poll_queue(self) -> None:
        """
        Regularly polls queue from Tkinter GUI thread to update video feeds, progress bars, and warn banners.
        """
        if not self.is_running:
            return
            
        latest_item = None
        # Retrieve only the most recent processed frame to prevent video lag
        while not self.video_queue.empty():
            try:
                latest_item = self.video_queue.get_nowait()
            except queue.Empty:
                break
                
        if latest_item is not None:
            pil_img, metrics = latest_item
            
            # 1. Update webcam canvas display
            if self.show_video_preview:
                if pil_img is not None:
                    try:
                        img_tk = ImageTk.PhotoImage(image=pil_img)
                        self.video_label.configure(image=img_tk)
                        self.video_label.image = img_tk  # Maintain reference to prevent garbage collection
                    except Exception as tk_img_err:
                        print(f"Error rendering image on Tkinter canvas: {tk_img_err}")
                else:
                    # Clear image reference to show a blank dark screen when paused
                    self.video_label.configure(image="")
                    self.video_label.image = None
            
            # 2. Update status and metrics panel
            if metrics is not None:
                t = self.translations[self.current_lang]
                if "status" in metrics and metrics["status"] == "paused":
                    # Camera is deactivated: Reset all tracking parameters to zero and hide overlays
                    self.frowning_start_time = None
                    self.tracker_state = "paused"
                    self.frown_bar.place(relwidth=0.0)
                    self.threshold_line.place(relx=0.5)
                    self.overlay.hide_warning()
                    
                    self.status_text_label.configure(text=t["status_paused"], fg=self.colors["accent"])
                    self.metrics_label.configure(
                        text=t["metrics_label_fmt"].format(
                            score=0.0, 
                            threshold_score=0.0, 
                            frown_pct=0.0, 
                            threshold_pct=50.0
                        )
                    )
                else:
                    frown_pct = metrics["frown_level_pct"]
                    threshold_pct = metrics["threshold_pct"]
                    is_frowning = metrics["is_frowning"]
                    score = metrics["combined_score"]
                    
                    # Buffer latest combined score for calibration use
                    self.last_combined_score = score
                    
                    # Update the horizontal progress bar relative width
                    self.frown_bar.place(relwidth=frown_pct / 100.0)
                    
                    # Position threshold line coordinate
                    self.threshold_line.place(relx=threshold_pct / 100.0)
                    
                    # Evaluate frowning debounce and trigger warn overlays
                    if is_frowning:
                        if self.frowning_start_time is None:
                            self.frowning_start_time = time.time()
                            
                        elapsed = time.time() - self.frowning_start_time
                        
                        if elapsed >= self.debounce_time:
                            self.tracker_state = "frowning"
                            self.status_text_label.configure(text=t["status_frowning"], fg=self.colors["alert"])
                            self.frown_bar.configure(bg=self.colors["alert"])
                            self.overlay.show_warning()
                        else:
                            self.tracker_state = "warning"
                            self.status_text_label.configure(text=t["status_warning"], fg="#FFC107")  # Amber warning status
                            self.frown_bar.configure(bg="#FFC107")
                            self.overlay.hide_warning()
                    else:
                        self.tracker_state = "relaxed"
                        self.frowning_start_time = None
                        self.status_text_label.configure(text=t["status_relaxed"], fg=self.colors["success"])
                        self.frown_bar.configure(bg=self.colors["success"])
                        self.overlay.hide_warning()
                        
                    # Format metrics labels
                    fmt = t["metrics_label_fmt"]
                    threshold_score = self.detector.relaxed_score - (self.detector.relaxed_score - self.detector.frowned_score) * (threshold_pct / 100.0)
                    self.metrics_label.configure(
                        text=fmt.format(
                            score=score, 
                            threshold_score=threshold_score, 
                            frown_pct=frown_pct, 
                            threshold_pct=threshold_pct
                        )
                    )
                
                # Perform calibration securely in main thread on request flags
                if self.calibrate_relaxed_requested:
                    self.calibrate_relaxed_requested = False
                    self.relaxed_score = self.last_combined_score
                    self.detector.set_calibration(self.relaxed_score, self.frowned_score)
                    self.save_config()
                    messagebox.showinfo(t["msg_cal_title"], t["msg_cal_relaxed_ok"].format(score=self.relaxed_score))
                    
                if self.calibrate_frowned_requested:
                    self.calibrate_frowned_requested = False
                    self.frowned_score = self.last_combined_score
                    self.detector.set_calibration(self.relaxed_score, self.frowned_score)
                    self.save_config()
                    messagebox.showinfo(t["msg_cal_title"], t["msg_cal_frowned_ok"].format(score=self.frowned_score))
            else:
                # Fallback if face is not found in frame
                t = self.translations[self.current_lang]
                self.tracker_state = "no_face"
                self.frowning_start_time = None
                self.status_text_label.configure(text=t["status_no_face"], fg=self.colors["text_muted"])
                self.frown_bar.place(relwidth=0.0)
                self.overlay.hide_warning()
                
        # Request next queue check in 15 ms
        self.root.after(15, self.poll_queue)
        
    def on_closing(self) -> None:
        """Releases all open resources safely on application close."""
        self.is_running = False
        
        # Close warning banner
        try:
            self.overlay.destroy()
        except Exception:
            pass
            
        # Safely release OpenCV webcam under mutex lock
        with self.cap_lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            
        # Release MediaPipe Tasks model
        try:
            self.detector.close()
        except Exception:
            pass
            
        # Destroy Tkinter window
        self.root.destroy()
