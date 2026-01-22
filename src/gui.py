import os
import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

from .rateio import processar
from . import config as cfg_mod

# Configuração Visual
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Paleta de Cores
COR_PRIMARIA      = "#FFA024"  # Laranja Adimax
COR_HOVER         = "#E58E1F"
COR_FUNDO         = "#F0F2F5"  # Cinza Gelatinoso (Fundo Moderno)
COR_CARD          = "#FFFFFF"  # Branco
COR_TEXTO         = "#333333"
COR_BTN_SEC       = "#374151"  # Cinza Chumbo
COR_LOG_BG        = "#1E1E1E"  # Fundo Terminal
COR_LOG_TXT       = "#00FF00"  # Texto Terminal

LOGO_FILENAME = "adimax.png"

def get_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()

BASE_DIR = get_base_dir()
LOGO_PATH = os.path.join(BASE_DIR, "..", "assets", LOGO_FILENAME)

class ProgressBarAdapter:
    def __init__(self, ctk_progressbar):
        self.bar = ctk_progressbar
        self._max = 100
        self._val = 0

    def __setitem__(self, key, value):
        if key == "maximum":
            self._max = value if value > 0 else 100
        elif key == "value":
            self._val = value
            percent = self._val / self._max
            self.bar.set(percent)
        self.bar.update_idletasks()

class RateioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Rateio de CT-e")
        self.root.geometry("950x850")
        self.root.minsize(850, 700)
        self.root.configure(fg_color=COR_FUNDO)
        
        self.v_planilha = ctk.StringVar()
        self.v_pdfs = ctk.StringVar()
        self.v_xml = ctk.StringVar()
        self.v_saida = ctk.StringVar()
        self.v_pdf_unico = ctk.BooleanVar(value=False)

        self._carregar_config_gui()

        # Frame Principal (Card Branco)
        self.main_frame = ctk.CTkFrame(
            self.root, 
            corner_radius=15, 
            fg_color=COR_CARD,
            border_color="#E5E7EB",
            border_width=1
        )
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Lógica de Redimensionamento do Logo (Aspect Ratio)
        if os.path.exists(LOGO_PATH):
            pil_img_raw = Image.open(LOGO_PATH)
            
            # Calcula proporção para altura fixa de 100px
            base_height = 50
            w_percent = (base_height / float(pil_img_raw.size[1]))
            w_size = int((float(pil_img_raw.size[0]) * float(w_percent)))
            
            self.logo_img = ctk.CTkImage(
                light_image=pil_img_raw, 
                dark_image=pil_img_raw, 
                size=(w_size, base_height)
            )
            
            ctk.CTkLabel(self.main_frame, text="", image=self.logo_img).pack(pady=(25, 5))

        ctk.CTkLabel(
            self.main_frame,
            text="SISTEMA DE GRAVAÇÃO DE CT-e",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COR_TEXTO
        ).pack(pady=(0, 25))

        self.inputs_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.inputs_frame.pack(fill="x", padx=50)

        self._criar_campo(self.inputs_frame, "Planilha Excel:", self.v_planilha, self.sel_planilha)
        self._criar_campo(self.inputs_frame, "Pasta de PDFs:", self.v_pdfs, self.sel_pdfs)
        self._criar_campo(self.inputs_frame, "Pasta de XMLs:", self.v_xml, self.sel_xml)
        self._criar_campo(self.inputs_frame, "Pasta de Saída:", self.v_saida, self.sel_saida)

        ctk.CTkCheckBox(
            self.main_frame,
            text="Unificar arquivos em um único PDF final",
            variable=self.v_pdf_unico,
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO,
            hover_color=COR_PRIMARIA,
            fg_color=COR_PRIMARIA,
            border_color="#9CA3AF"
        ).pack(pady=20)

        self.btn_processar = ctk.CTkButton(
            self.main_frame,
            text="INICIAR PROCESSAMENTO",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COR_PRIMARIA,
            hover_color=COR_HOVER,
            height=45,
            corner_radius=8,
            command=self.iniciar_processamento
        )
        self.btn_processar.pack(fill="x", padx=120, pady=5)

        self.progress_widget = ctk.CTkProgressBar(
            self.main_frame,
            orientation="horizontal",
            progress_color=COR_PRIMARIA,
            height=12
        )
        self.progress_widget.set(0)
        self.progress_widget.pack(fill="x", padx=50, pady=(15, 5))
        
        self.progress_adapter = ProgressBarAdapter(self.progress_widget)

        ctk.CTkLabel(
            self.main_frame, 
            text="Log do Sistema:", 
            anchor="w",
            text_color=COR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(fill="x", padx=50, pady=(15, 5))

        self.log_box = ctk.CTkTextbox(
            self.main_frame,
            height=120,
            fg_color=COR_LOG_BG,
            text_color=COR_LOG_TXT,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8
        )
        self.log_box.pack(fill="both", expand=True, padx=50, pady=(0, 30))
        self.log_box.configure(state="disabled")

    def _criar_campo(self, parent, texto, var, comando):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            frame, 
            text=texto, 
            width=110, 
            anchor="w",
            text_color=COR_TEXTO,
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        entry = ctk.CTkEntry(
            frame, 
            textvariable=var, 
            placeholder_text="Caminho do arquivo...",
            height=32,
            border_color="#D1D5DB",
            fg_color="#F9FAFB",
            text_color="#111827"
        )
        entry.pack(side="left", fill="x", expand=True, padx=10)

        ctk.CTkButton(
            frame, 
            text="Selecionar", 
            width=90,
            height=32,
            command=comando,
            fg_color=COR_BTN_SEC, 
            hover_color="#111827",
            font=ctk.CTkFont(size=11)
        ).pack(side="right")

    def log_msg(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

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

    def sel_planilha(self):
        arquivo = filedialog.askopenfilename(title="Selecione a Planilha", filetypes=[("Excel", "*.xlsx *.xls")])
        if arquivo: self.v_planilha.set(arquivo)

    def sel_pdfs(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta de PDFs")
        if pasta: self.v_pdfs.set(pasta)

    def sel_xml(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta de XMLs")
        if pasta: self.v_xml.set(pasta)

    def sel_saida(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta de Saída")
        if pasta: self.v_saida.set(pasta)

    def iniciar_processamento(self):
        if not self.v_planilha.get() or not self.v_pdfs.get() or not self.v_saida.get():
            messagebox.showerror("Atenção", "Por favor, preencha todos os campos antes de iniciar.")
            return

        self.btn_processar.configure(state="disabled", text="PROCESSANDO...", fg_color="#9CA3AF")
        self._salvar_config_gui()
        threading.Thread(target=self._processar_thread, daemon=True).start()

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
                progresso=self.progress_adapter
            )
        except Exception as e:
            self.log_msg(f"ERRO CRÍTICO: {e}")
        finally:
            self.tempo_final = time.time()
            self.root.after(0, self.finalizar_processamento)

    def finalizar_processamento(self):
        duracao = round(self.tempo_final - self.tempo_inicial, 2)
        self.btn_processar.configure(state="normal", text="INICIAR PROCESSAMENTO", fg_color=COR_PRIMARIA)
        messagebox.showinfo("Sucesso", f"Processamento finalizado em {duracao}s")
        self.log_msg(f"--- FIM DA OPERAÇÃO ({duracao}s) ---")