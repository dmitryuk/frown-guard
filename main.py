import sys
import tkinter as tk

# Explicit import for PyInstaller to guarantee packaging of the Pillow and Tkinter integration in the binary
try:
    import PIL._tkinter_finder
except ImportError:
    pass

from frown_guard.app import FrownGuardApp

def main() -> None:
    """Entry point of the Frown Guard application."""
    try:
        root = tk.Tk()
        
        # Create an instance of the application
        app = FrownGuardApp(root)
        
        # Run the infinite Tkinter event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Critical error during application startup: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
