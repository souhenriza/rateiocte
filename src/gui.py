import os
import time
import threading

from tkinter import (
    Tk, StringVar, BooleanVar,
    Frame, Label, Entry, Button, Checkbutton,
    filedialog, messagebox
)
from tkinter.ttk import Progressbar, Style
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk

from .rateio import processar
import src.config as cfg_mod
    
# =====================================================
# CONSTANTES VISUAIS / ASSETS
# =====================================================

LOGO_FILENAME = "adimax.png"
LOGO_MAX_WIDTH = 90
LOGO_MAX_HEIGHT = 90


def get_base_dir():
    """Compatível com execução normal e PyInstaller."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


BASE_DIR = get_base_dir()
LOGO_PATH = os.path.join(BASE_DIR, "..", "assets", LOGO_FILENAME)


# =====================================================
# GUI
# =====================================================

class RateioGUI:
    def __init__(self, root: Tk):
        self.root = root

        # ---------------------------
        # CONFIGURAÇÕES DA JANELA
        # ---------------------------
        root.title("Sistema de Rateio de CT-e")
        root.geometry("850x680")
        root.resizable(True, True)
        root.configure(bg="#F5F5F5")
        root.state("zoomed")

        # ---------------------------
        # VARIÁVEIS TKINTER
        # ---------------------------
        self.v_planilha = StringVar()
        self.v_pdfs = StringVar()
        self.v_xml = StringVar()
        self.v_saida = StringVar()
        self.v_pdf_unico = BooleanVar(value=False)

        # ---------------------------
        # CARREGA CONFIGURAÇÕES
        # ---------------------------
        self._carregar_config_gui()

        # ---------------------------
        # FRAME PRINCIPAL
        # ---------------------------
        frame = Frame(root, bg="#F5F5F5", padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        # ---------------------------
        # LOGO
        # ---------------------------
        if os.path.exists(LOGO_PATH):
            img = Image.open(LOGO_PATH)
            img.thumbnail((LOGO_MAX_WIDTH, LOGO_MAX_HEIGHT))
            self.logo_img = ImageTk.PhotoImage(img)
            Label(frame, image=self.logo_img, bg="#F5F5F5").pack()

        # ---------------------------
        # TÍTULO
        # ---------------------------
        Label(
            frame,
            text="SISTEMA DE GRAVAÇÃO DE CT-e",
            bg="#F5F5F5",
            font=("Times-Roman", 15, "bold")
        ).pack(pady=10)

        # ---------------------------
        # CAMPOS
        # ---------------------------
        self._campo(frame, "Planilha:", self.v_planilha, self.sel_planilha)
        self._campo(frame, "Pasta PDFs:", self.v_pdfs, self.sel_pdfs)
        self._campo(frame, "Pasta XML:", self.v_xml, self.sel_xml)
        self._campo(frame, "Saída:", self.v_saida, self.sel_saida)

        # ---------------------------
        # CHECKBOX
        # ---------------------------
        Checkbutton(
            frame,
            text="Gerar saída em um único PDF",
            variable=self.v_pdf_unico,
            bg="#F5F5F5"
        ).pack(pady=5)

        # ---------------------------
        # BOTÃO PROCESSAR
        # ---------------------------
        self.btn_processar = Button(
            frame,
            text="INICIAR PROCESSAMENTO",
            bg="#FFA024",
            width=30,
            height=2,
            command=self.iniciar_processamento
        )
        self.btn_processar.pack(pady=10)

        # ---------------------------
        # PROGRESS BAR
        # ---------------------------
        style = Style()
        style.configure(
            "Adimax.Horizontal.TProgressbar",
            background="#FFA024",
            thickness=18
        )

        self.progress = Progressbar(
            frame,
            length=600,
            mode="determinate",
            style="Adimax.Horizontal.TProgressbar"
        )
        self.progress.pack(pady=5)

        # ---------------------------
        # LOG
        # ---------------------------
        self.log = ScrolledText(frame, width=95, height=15)
        self.log.pack(pady=10)

    # =====================================================
    # COMPONENTES AUXILIARES
    # =====================================================

    def _campo(self, frame, texto, var, cmd):
        linha = Frame(frame, bg="#F5F5F5")
        linha.pack(fill="x", pady=2)

        Label(
            linha,
            text=texto,
            width=15,
            anchor="w",
            bg="#F5F5F5"
        ).pack(side="left")

        Entry(linha, textvariable=var).pack(
            side="left", fill="x", expand=True
        )

        Button(
            linha,
            text="Selecionar",
            command=cmd,
            width=12
        ).pack(side="left", padx=10)

    def log_msg(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    # =====================================================
    # CONFIGURAÇÃO (GUI ↔ config.py)
    # =====================================================

    def _carregar_config_gui(self):
        cfg = cfg_mod.carregar_config()
        self.v_planilha.set(cfg.get("planilha", ""))
        self.v_pdfs.set(cfg.get("pdfs", ""))
        self.v_xml.set(cfg.get("xml", ""))
        self.v_saida.set(cfg.get("saida", ""))

    def _salvar_config_gui(self):
        cfg_mod.salvar_config({
            "planilha": self.v_planilha.get(),
            "pdfs": self.v_pdfs.get(),
            "xml": self.v_xml.get(),
            "saida": self.v_saida.get()
        })


    # =====================================================
    # SELETORES
    # =====================================================

    def sel_planilha(self):
        self.v_planilha.set(filedialog.askopenfilename())

    def sel_pdfs(self):
        self.v_pdfs.set(filedialog.askdirectory())

    def sel_xml(self):
        self.v_xml.set(filedialog.askdirectory())

    def sel_saida(self):
        self.v_saida.set(filedialog.askdirectory())

    # =====================================================
    # PROCESSAMENTO
    # =====================================================

    def iniciar_processamento(self):
        if not self.v_planilha.get() or not self.v_pdfs.get() or not self.v_saida.get():
            messagebox.showerror(
                "Erro",
                "Planilha, PDFs e pasta de saída são obrigatórios."
            )
            return

        self.btn_processar.config(state="disabled")
        self.root.config(cursor="watch")

        self._salvar_config_gui()

        threading.Thread(
            target=self._processar_thread,
            daemon=True
        ).start()

    def _processar_thread(self):
        self.tempo_inicial = time.time()

        try:
            processar(
                planilha=self.v_planilha.get(),
                pasta_pdfs=self.v_pdfs.get(),
                pasta_xml=self.v_xml.get(),
                pasta_saida=self.v_saida.get(),
                pdf_unico=self.v_pdf_unico.get(),
                log=self.log_msg,
                progresso=self.progress
            )
        except Exception as e:
            self.log_msg(f"❌ Erro inesperado: {e}")
        finally:
            self.tempo_final = time.time()
            self.root.after(0, self.finalizar_processamento)

    def finalizar_processamento(self):
        duracao = round(self.tempo_final - self.tempo_inicial, 2)

        self.btn_processar.config(state="normal")
        self.root.config(cursor="")

        messagebox.showinfo(
            "Concluído",
            f"Processamento finalizado com sucesso\n\nDuração total: {duracao}s"
        )

        self.log_msg(f"⏱️ Tempo total: {duracao}s")
