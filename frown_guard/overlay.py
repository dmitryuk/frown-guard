import tkinter as tk
from typing import Optional

class FrownWarningOverlay(tk.Toplevel):
    """
    Плавающее безрамочное окно-уведомление, которое отображается поверх всех окон,
    когда пользователь хмурится, и скрывается, когда лицо расслаблено.
    """
    def __init__(self, parent: Optional[tk.Tk] = None) -> None:
        super().__init__(parent)
        
        # Настройка безрамочного окна
        self.overrideredirect(True)
        # Окно всегда поверх остальных
        self.attributes("-topmost", True)
        # Прозрачность окна (85% непрозрачности для современного вида)
        self.attributes("-alpha", 0.9)
        
        # Цветовая палитра (яркий красный предупреждающий тон)
        self.bg_color = "#C62828"  # Material Red 800
        self.fg_color = "#FFFFFF"  # Белый текст
        self.accent_color = "#FFEB3B"  # Желтый акцент для смайлика
        
        self.configure(bg=self.bg_color, highlightbackground="#B71C1C", highlightthickness=2)
        
        # Размеры окна и начальное позиционирование (сверху по центру экрана)
        self.width = 400
        self.height = 65
        
        # Определение размеров экрана
        screen_width = self.winfo_screenwidth()
        # Позиционируем по центру по горизонтали, и немного отступив сверху (10% от верха экрана)
        start_x = (screen_width - self.width) // 2
        start_y = 50
        
        self.geometry(f"{self.width}x{self.height}+{start_x}+{start_y}")
        
        # Контент уведомления
        self.container = tk.Frame(self, bg=self.bg_color)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Большая предупреждающая иконка/текст
        self.icon_label = tk.Label(
            self.container, 
            text="😡", 
            font=("Segoe UI Emoji", 24, "bold"), 
            bg=self.bg_color, 
            fg=self.accent_color
        )
        self.icon_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # Основной текст
        self.text_frame = tk.Frame(self.container, bg=self.bg_color)
        self.text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.title_label = tk.Label(
            self.text_frame, 
            text="Не хмурьтесь!", 
            font=("Helvetica", 14, "bold"), 
            bg=self.bg_color, 
            fg=self.fg_color,
            anchor="w"
        )
        self.title_label.pack(fill=tk.X, pady=(2, 0))
        
        self.subtitle_label = tk.Label(
            self.text_frame, 
            text="Пожалуйста, расслабьте лоб и брови", 
            font=("Helvetica", 10), 
            bg=self.bg_color, 
            fg="#FFCDD2",  # Светло-розовый оттенок для читаемости
            anchor="w"
        )
        self.subtitle_label.pack(fill=tk.X)
        
        # Переменные для перетаскивания окна мышкой
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Привязка событий мыши для возможности перемещения окна в любое место экрана
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.drag)
        
        # Привязываем перетаскивание и к внутренним элементам, чтобы за них тоже можно было тянуть
        for widget in [self.container, self.icon_label, self.text_frame, self.title_label, self.subtitle_label]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        # Изначально скрываем окно
        self.is_visible = False
        self.withdraw()
        
    def start_drag(self, event: tk.Event) -> None:
        """Запоминает начальные координаты при клике для перемещения окна."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
    def drag(self, event: tk.Event) -> None:
        """Перемещает окно вслед за курсором мыши."""
        # Вычисляем смещение
        delta_x = event.x - self._drag_start_x
        delta_y = event.y - self._drag_start_y
        
        # Новые координаты окна на экране
        new_x = self.winfo_x() + delta_x
        new_y = self.winfo_y() + delta_y
        
        self.geometry(f"+{new_x}+{new_y}")
        
    def show_warning(self) -> None:
        """Мгновенно отображает уведомление на экране."""
        if not self.is_visible:
            self.deiconify()
            self.attributes("-topmost", True)  # Повторно форсируем поверх всех окон
            self.is_visible = True
            
    def hide_warning(self) -> None:
        """Скрывает уведомление с экрана."""
        if self.is_visible:
            self.withdraw()
            self.is_visible = False
            
    def set_opacity(self, alpha: float) -> None:
        """Позволяет изменять прозрачность окна (0.1 - 1.0)."""
        alpha_val = max(0.1, min(1.0, alpha))
        self.attributes("-alpha", alpha_val)
