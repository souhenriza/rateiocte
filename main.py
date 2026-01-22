import os
import customtkinter as ctk  # Importação da lib moderna
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
    # ===== CONFIGURAÇÕES GLOBAIS CTK =====
    # Isso garante que ele pegue o tema do sistema (Light/Dark) antes de abrir
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    # ===== CRIAÇÃO DA JANELA MODERNA =====
    # Substituímos root = Tk() por app = ctk.CTk()
    app = ctk.CTk()

    # ===== ÍCONE =====
    # A função iconbitmap funciona igual no CustomTkinter
    try:
        icon_path = os.path.join(
            get_base_dir(),
            "assets",
            "adimax.ico"
        )
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
    except Exception:
        pass
    # =================

    # Instancia a GUI passando a janela moderna 'app'
    # A classe RateioGUI vai configurar título, tamanho e geometria nela mesma
    gui = RateioGUI(app)

    # Loop principal
    app.mainloop()

if __name__ == "__main__":
    main()