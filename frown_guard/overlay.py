import tkinter as tk
from typing import Optional

class FrownWarningOverlay(tk.Toplevel):
    """
    Floating frameless notification window displayed on top of all windows
    when the user is frowning, and hidden when the face is relaxed.
    """
    def __init__(self, parent: Optional[tk.Tk] = None) -> None:
        super().__init__(parent)
        
        # Configure frameless window
        self.overrideredirect(True)
        # Always on top
        self.attributes("-topmost", True)
        # Window opacity (90% opacity for a modern look)
        self.attributes("-alpha", 0.9)
        
        # Color palette (bright red warning tone)
        self.bg_color = "#C62828"  # Material Red 800
        self.fg_color = "#FFFFFF"  # White text
        self.accent_color = "#FFEB3B"  # Yellow accent for smiley face
        
        self.configure(bg=self.bg_color, highlightbackground="#B71C1C", highlightthickness=2)
        
        # Window dimensions and initial positioning (top center of the screen)
        self.width = 400
        self.height = 65
        
        # Determine screen dimensions
        screen_width = self.winfo_screenwidth()
        # Position centered horizontally and slightly offset from the top
        start_x = (screen_width - self.width) // 2
        start_y = 50
        
        self.geometry(f"{self.width}x{self.height}+{start_x}+{start_y}")
        
        # Notification content
        self.container = tk.Frame(self, bg=self.bg_color)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Large warning icon/text
        self.icon_label = tk.Label(
            self.container, 
            text="😡", 
            font=("Segoe UI Emoji", 24, "bold"), 
            bg=self.bg_color, 
            fg=self.accent_color
        )
        self.icon_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # Main text
        self.text_frame = tk.Frame(self.container, bg=self.bg_color)
        self.text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.title_label = tk.Label(
            self.text_frame, 
            text="Don't frown!", 
            font=("Helvetica", 14, "bold"), 
            bg=self.bg_color, 
            fg=self.fg_color,
            anchor="w"
        )
        self.title_label.pack(fill=tk.X, pady=(2, 0))
        
        self.subtitle_label = tk.Label(
            self.text_frame, 
            text="Please relax your forehead and eyebrows", 
            font=("Helvetica", 10), 
            bg=self.bg_color, 
            fg="#FFCDD2",  # Light pink tint for readability
            anchor="w"
        )
        self.subtitle_label.pack(fill=tk.X)
        
        # Variables for dragging the window with the mouse
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Bind mouse events to enable moving the window anywhere on the screen
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.drag)
        
        # Bind dragging to child widgets so they can also be used to drag the window
        for widget in [self.container, self.icon_label, self.text_frame, self.title_label, self.subtitle_label]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        # Initially hide the window
        self.is_visible = False
        self.withdraw()
        
    def start_drag(self, event: tk.Event) -> None:
        """Remembers initial click coordinates for moving the window."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
    def drag(self, event: tk.Event) -> None:
        """Moves the window relative to the mouse cursor."""
        # Calculate offset
        delta_x = event.x - self._drag_start_x
        delta_y = event.y - self._drag_start_y
        
        # New window coordinates on the screen
        new_x = self.winfo_x() + delta_x
        new_y = self.winfo_y() + delta_y
        
        self.geometry(f"+{new_x}+{new_y}")
        
    def show_warning(self) -> None:
        """Instantly displays the notification on the screen."""
        if not self.is_visible:
            self.deiconify()
            self.attributes("-topmost", True)  # Force on top again
            self.is_visible = True
            
    def hide_warning(self) -> None:
        """Hides the notification from the screen."""
        if self.is_visible:
            self.withdraw()
            self.is_visible = False
            
    def set_opacity(self, alpha: float) -> None:
        """Allows changing the window opacity (0.1 - 1.0)."""
        alpha_val = max(0.1, min(1.0, alpha))
        self.attributes("-alpha", alpha_val)
