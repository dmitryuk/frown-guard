import os
import sys
import tkinter as tk
from typing import Optional, TextIO

# Explicit import for PyInstaller to guarantee packaging of the Pillow and Tkinter integration in the binary
try:
    import PIL._tkinter_finder
except ImportError:
    pass

from frown_guard.paths import config_dir, show_request_file


def acquire_single_instance_lock() -> Optional[TextIO]:
    """
    Holds an exclusive lock for the process lifetime so a login-launched copy and a
    manually opened copy never fight over the webcam. Returns None if another
    instance already holds it. (No-op where fcntl is unavailable, e.g. Windows.)
    """
    try:
        import fcntl
    except ImportError:
        return open(os.devnull, "w")
    handle = open(os.path.join(config_dir(), "instance.lock"), "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def main() -> None:
    """Entry point of the Frown Guard application."""
    # --background: start hidden in the menu bar (used by Launch at Login)
    start_hidden = "--background" in sys.argv[1:]

    lock = acquire_single_instance_lock()
    if lock is None:
        print("Frown Guard is already running.", file=sys.stderr)
        # Opened again from Finder/Spotlight: ask the running instance to show its
        # window (macOS does not reliably route a re-open to a launchd-started copy)
        if not start_hidden:
            try:
                open(show_request_file(), "w").close()
            except OSError:
                pass
        # Exit 0 so launchd's KeepAlive(SuccessfulExit=false) does not keep retrying
        sys.exit(0)

    # Imported after the lock check: loading OpenCV/MediaPipe takes seconds
    from frown_guard.app import FrownGuardApp

    try:
        root = tk.Tk()
        if start_hidden:
            root.withdraw()  # avoid a window flash before the app hides itself

        # Create an instance of the application
        app = FrownGuardApp(root, start_hidden=start_hidden)

        # Run the infinite Tkinter event loop
        root.mainloop()

    except Exception as e:
        print(f"Critical error during application startup: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
