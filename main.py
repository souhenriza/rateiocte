import os
from tkinter import Tk

from src.gui import RateioGUI


def get_base_dir():
    """
    Compatível com execução normal e PyInstaller.
    """
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def main():
    # ===== DPI AWARENESS (WINDOWS) =====
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    # ==================================

    root = Tk()

    # ===== ESCALA TKINTER =====
    try:
        dpi = root.winfo_fpixels("1i")
        scaling = dpi / 72
        root.tk.call("tk", "scaling", scaling)
    except Exception:
        root.tk.call("tk", "scaling", 1.25)
    # =========================

    # ===== ÍCONE =====
    try:
        icon_path = os.path.join(
            get_base_dir(),
            "assets",
            "adimax.ico"
        )
        root.iconbitmap(icon_path)
    except Exception:
        pass
    # =================

    RateioGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
