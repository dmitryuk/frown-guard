# Frown Guard — Expression & Forehead Wrinkle Control

**Frown Guard** is an intelligent, cross-platform desktop application built with Python and MediaPipe that monitors your facial expressions in real-time via a webcam.

If you involuntarily scowl, furrow your eyebrows, or wrinkle your forehead (which leads to facial tension wrinkles and tension headaches), the app will instantly display a sleek, semi-transparent warning banner always-on-top of all windows. As soon as you relax your face, the banner immediately vanishes.

---

## 🌟 Key Features

* **🤖 Neural Network AI Tracking (State-of-the-Art):**
  Instead of outdated geometric distance measurements on a 2D frame, the detector uses the deep learning **MediaPipe FaceLandmarker** model to extract **facial blendshape coefficients**. It evaluates absolute muscle activity and is **100% invariant to head rotation (yaw, pitch, roll) or distance changes**. False positives during head turns are completely eliminated!
* **💆 Dual Forehead Muscle Monitoring:**
  The app tracks both downward scowling/eyebrow furrowing (`browDown`) and involuntary upward eyebrow raising (`browOuterUp`), which is the primary cause of horizontal forehead lines.
* **🛡️ Complete Thread Safety (Mutex Lock):**
  All shared access to camera and GPU resources is synchronized with a system mutex (`threading.Lock`). This prevents conflicts between the Tkinter main GUI thread and the background capture loop, eliminating race conditions and segmentation faults.
* **🔌 Dynamic Multi-Camera Support:**
  The app automatically scans your system, queries real human-readable hardware names (such as *HP HD Camera* or *HD Pro Webcam C920*), and lets you switch between devices "on the fly" with zero UI freezing. It automatically filters out duplicate metadata-only system video nodes.
* **⏱️ Anti-Flicker Debounce Filter:**
  The adjustable response delay slider filters out momentary changes in expression (such as blinking, sneezing, or yawning). The banner will only trigger if you frown continuously for at least the chosen duration. While waiting, the status bar smoothly transitions to an amber `"Warning... ⏳"`.
* **🔋 Battery-Saving Polling Rate (Adjustable FPS):**
  A dedicated slider lets you adjust the camera polling rate from 2 Hz to 30 Hz. Lowering the rate (e.g., to 5–10 frames/sec) reduces CPU load by several times, dramatically saving laptop battery while keeping face tracking fully active.
* **🎨 Precision Customization:**
  Adjust both reaction sensitivity and banner transparency to your preference. All parameters are saved dynamically in `config.json`.
* **📌 Seamless Overlay Experience:**
  The warning banner is displayed always-on-top, **does not steal keyboard focus** (meaning it will never interrupt your typing in active documents), and can be easily dragged and repositioned anywhere on the screen with your mouse.

---

## 💾 Installation & Downloads

For a seamless and plug-and-play experience without needing Python, terminal commands, or dependency setup, simply download the pre-compiled standalone package for your operating system:

1. Navigate to the official [Frown Guard Releases](https://github.com/dmitryuk/frawn-guard/releases) page.
2. Download the release artifact corresponding to your platform:
   - **Linux:** Download `Frown_Guard-x86_64.AppImage` (Grant execute permissions and run instantly).
   - **macOS:** Download `Frown_Guard.dmg` (Open the disk image and drag Frown Guard to your Applications folder).
   - **Windows:** Download `Frown_Guard.exe` (Run the standalone binary directly).

---

## 📐 How to Use (Calibration)

The application adapts to the unique muscle structure of any face:
1. Open the application and sit in a comfortable, natural working posture in front of your webcam.
2. Completely relax your face (smoothing out your forehead and eyebrows), look directly at the camera, and click the green **"😊 Relaxed Face"** button.
3. Frown as hard as you can (or raise your eyebrows, creating horizontal forehead wrinkles) and, while holding this expression, click the red **"😡 Frowned Face"** button.
4. Calibration is complete! The system will dynamically build a custom sensitivity scale centered around your individual facial muscle range and save it.

---

## 📦 Standalone Executable Compilation

No need for Python or a terminal — compile the application into a single portable executable for your operating system.

### 🐧 Build for Linux (AppImage Format)
The script compiles the binary with PyInstaller, generates the icon, and compresses the SquashFS system into a single portable binary:
```bash
./build_appimage.sh
```
**Result:** A portable **`Frown_Guard-x86_64.AppImage`** executable in the project root. Run it on any Linux distribution with a double-click.

### 🍏 Build for macOS (.app & .dmg Formats)
The script compiles a native macOS App Bundle and packages it into a compressed disk image. It automatically injects the `NSCameraUsageDescription` security authorization key to prevent camera permission crashes:
```bash
./build_mac.sh
```
**Result:** An installable **`Frown_Guard.dmg`** disk image in the project root. Open it and drag Frown Guard to your *Applications* folder.

### 🔌 Build for Windows (.exe Standalone Format)
The Batch script automatically sets up the environment, downloads assets, creates a multi-resolution `.ico` icon, and builds a single standalone Windows executable with the command console hidden:
```cmd
build_win.bat
```
**Result:** A standalone **`Frown_Guard.exe`** inside the `dist\` folder in the project root. Run it on any Windows 10/11 machine.

---

## 📂 Project Structure

```
frown-guard/
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── AGENTS.md                # Technical developer documentation (En)
├── README.md                # Comprehensive user manual (En)
├── build_appimage.sh        # Linux AppImage packaging script
├── build_mac.sh             # macOS DMG/App packaging script
├── build_win.bat            # Windows standalone EXE packaging script
├── mac_info.plist           # Apple camera sandbox permissions plist
├── test_detector.py         # Mathematical unit test suite
└── frown_guard/             # Source package folder
    ├── __init__.py          # Python package initializer
    ├── detector.py          # AI Blendshape analysis & calibration
    ├── overlay.py           # Passive always-on-top warning banner
    └── app.py               # Main control dashboard (GUI, threads, mutexes)
```

---

## 📄 License

This project is licensed under a custom **Non-Commercial License**. 

**ANY USE OF THIS SOFTWARE FOR COMMERCIAL, CORPORATE, FOR-PROFIT, OR WORKPLACE ENVIRONMENT PURPOSES IS STRICTLY PROHIBITED.** 

Please see the [LICENSE](LICENSE) file for the full legal text and conditions.

---
*Frown Guard — protect your muscle health and forget about wrinkles!*
