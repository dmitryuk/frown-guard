# Contributing to Frown Guard

Thank you for your interest in contributing to Frown Guard! We appreciate all contributions to help make this application better for everyone.

---

## 🛠️ Development Setup (How to Build and Run from Source)

If you are a developer and want to run, modify, or test Frown Guard from the source code, please follow these steps:

### Prerequisites
* Python 3.10+ (tested up to Python 3.14)
* Libraries: `opencv-python`, `mediapipe`, `pillow` (installed automatically during pip requirements setup)

### Setup & Launch Steps:
1. Clone the repository and navigate into the project directory.
2. Initialize a virtual environment and run the application:
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate environment and install dependencies
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Launch the application
   python3 main.py
   ```

### 📦 Standalone Compilations
If you want to package your modified version into a standalone installer on your local machine:
- **Linux:** Run `./build_appimage.sh` to compile `dist/Frown_Guard-x86_64.AppImage`.
- **macOS:** Run `./build_mac.sh` to compile `dist/Frown_Guard.dmg`.
- **Windows:** Run `build_win.bat` in CMD to compile `dist/Frown_Guard.exe`.

---

## How You Can Contribute

### 1. Reporting Bugs & Problems
- If you find a bug, please check the existing issues on GitHub to see if it has already been reported.
- If it hasn't, open a new issue with a clear, descriptive title.
- Provide a clear description of the issue, steps to reproduce it, and your operating system / environment details.

### 2. Suggesting Enhancements & Features
- We welcome feature suggestions! Open an issue on GitHub describing your idea.
- Explain the benefits of the feature and how it should work inside the application.

### 3. Submitting Pull Requests (Code Contributions)
- Fork the repository.
- Create a new branch named after your bug fix or feature (e.g., `fix/camera-lock` or `feature/additional-languages`).
- Implement your changes, adhering to the project's existing coding style, naming conventions, and thread-safe architecture.
- Ensure all unit tests pass, and write new unit tests if adding new logical functionality.
- Open a Pull Request targeting the `main` branch.

## Code of Conduct
We want to keep our project open, friendly, and welcoming to all. Please treat other contributors and maintainers with respect, empathy, and professional courtesy at all times.
