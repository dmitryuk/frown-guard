import sys
import tkinter as tk

# Явный импорт для PyInstaller, чтобы гарантировать упаковку сопряжения Pillow и Tkinter в бинарник
try:
    import PIL._tkinter_finder
except ImportError:
    pass

from frown_guard.app import FrownGuardApp

def main() -> None:
    """Точка входа в приложение Frown Guard."""
    try:
        root = tk.Tk()
        
        # Создаем экземпляр приложения
        app = FrownGuardApp(root)
        
        # Запускаем бесконечный цикл обработки событий Tkinter
        root.mainloop()
        
    except Exception as e:
        print(f"Критическая ошибка при запуске приложения: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
