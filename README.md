# Frown Guard — protect your muscle health and forget about wrinkles!

**Frown Guard** is an intelligent, cross-platform desktop application built with Python and MediaPipe that monitors your facial expressions in real-time via a webcam.

If you involuntarily scowl, furrow your eyebrows, or wrinkle your forehead (which leads to facial tension wrinkles and tension headaches), the app will instantly display a sleek, semi-transparent warning banner always-on-top of all windows. As soon as you relax your face, the banner immediately vanishes.

---

## 🌟 Key Features

* **🤖 Rotation-Invariant AI Tracking:** Uses deep learning **MediaPipe FaceLandmarker** blendshapes to evaluate real muscle tension (`browDown` & `browOuterUp`). It is **100% resistant to head rotations or distance shifts**, completely eliminating false triggers!
* **🎥 Smart Face Zooming:** Smoothly tracks, centers, and zooms in on your face in real-time (using LERP-smoothed interpolation), allowing you to clearly see and monitor your facial muscle adjustments.
* **⏱️ Anti-Flicker Debouncing & Saving:** Includes an adjustable delay filter to ignore momentary expressions (like blinking or sneezing) and a battery-saving camera FPS slider to keep CPU load extremely light.
* **📌 Focus-Free Warning Overlay:** Displays a sleek, draggable, always-on-top warning banner that **never steals keyboard focus**—allowing you to work and type entirely without interruption.
* **🌐 Multilingual & Hot-Swappable:** Full EN, RU, DE, and FR language support with dynamic "on-the-fly" hot-swapping and a robust, mutex-locked camera selector.

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

## 📄 License

This project is licensed under a custom **Non-Commercial License**. 

**ANY USE OF THIS SOFTWARE FOR COMMERCIAL, CORPORATE, FOR-PROFIT, OR WORKPLACE ENVIRONMENT PURPOSES IS STRICTLY PROHIBITED.** 

Please see the [LICENSE](LICENSE) file for the full legal text and conditions.

