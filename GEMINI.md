# Frown Guard (Expression & Forehead Wrinkle Control)

A Python + MediaPipe application that monitors facial expressions (eyebrow scowling, furrowing, and forehead wrinkling) in real-time via a webcam. When frowning is detected, it instantly displays a semi-transparent on-screen warning banner always-on-top of all other windows, which automatically vanishes the moment the face relaxes.

## Project Architecture

The project is divided into the following modular components to ensure clean code, loose coupling, and high maintainability:

1. **`frown_guard/detector.py` (Facial Expression Analyzer):**
   - Encapsulates the modern **MediaPipe Tasks FaceLandmarker** API.
   - Extracts highly robust, **pose-invariant AI blendshape coefficients** (specifically `browDownLeft`/`browDownRight` for scowling, and `browOuterUpLeft`/`browOuterUpRight` for forehead wrinkling) to eliminate false triggers during head rotations (yaw, pitch, roll) or distance changes.
   - Falls back to normalized 3D geometric eye-eyebrow metrics if blendshapes are unavailable.
   - Handles the customized calibration algorithms to adapt to any user's face.

2. **`frown_guard/overlay.py` (Floating On-screen Warning Banner):**
   - Lightweight, borderless (`overrideredirect`) Tkinter window styled as a modern material warning card.
   - Stays **always on top of all windows** (`-topmost`) with adjustable transparency (`alpha`).
   - Configured with special attributes to **avoid stealing keyboard focus**, preventing any interruption to the user's active typing or work.
   - Binds mouse gesture events to support user-controlled drag-and-drop repositioning anywhere on the screen.

3. **`frown_guard/app.py` (Main Control Dashboard):**
   - Gorgeous Dark-Theme Tkinter graphical user interface.
   - Renders the live webcam preview with annotated facial tracking lines in real-time.
   - Employs **`threading.Lock` (mutex)** synchronization to safely coordinate webcam hardware between the processing background thread and the main GUI thread, completely preventing race conditions and segmentation faults.
   - Provides full controls for:
     - Custom Calibration ("Relaxed Face" & "Frowned Face" buttons with forced geometry-manager padding `ipady` for Linux).
     - **Active Camera Selection dropdown** (automatically scans and queries real physical device names from `/sys/class/video4linux` and tests frame extraction with `cap.read()` to filter out auxiliary metadata video channels).
     - **Debounce Delay Slider** (prevents flickering; user must frown continuously for at least $T$ seconds for the banner to show).
     - **Sensitivity Slider** (calibrates reaction thresholds).
     - **Polling Frequency Slider** (ranges from 2 Hz to 30 Hz, allowing massive CPU and battery savings on laptops).
     - **Banner Opacity Slider**.
   - Persists all settings dynamically inside `config.json`.

4. **`main.py` (Application Entry Point):**
   - Initializes Tkinter, imports the Pillow-Tkinter dynamic solver `PIL._tkinter_finder` for PyInstaller freezing, and executes the event mainloop.

5. **`test_detector.py` (Unit Tests):**
   - Contains unit tests checking 3D Euclidean distance math, ratio normalizations, and calibration mappings using Mock MediaPipe landmarks.

6. **`build_appimage.sh` (Packaging Script):**
   - Automates compilation into a portable, standalone Linux **`Frown_Guard-x86_64.AppImage`** executable, bundling the python environment, opencv, mediapipe binary libraries, and model files.

## Programming Standards

- **Strict Type Hinting:** All classes, functions, and methods are fully typed using Python's `typing` module to maintain code safety and autocomplete assistance.
- **Thread Safety:** All sharing of OpenCV/MediaPipe resources is strictly locked with мьютекс (`threading.Lock`) to prevent native pointer segmentation crashes in C++ wrapper boundaries.
- **Robust Error Handling:** Seamlessly intercepts and handles situations where cameras are busy, locked, or unplugged, falling back gracefully without crashing.
- **User-Centric Spacing (Linux/X11):** Explicitly applies internal packing padding (`ipady`) on buttons to prevent Linux GTK themes from overriding and flattening interactive controls.
