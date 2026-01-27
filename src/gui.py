import os
from time import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from datetime import datetime
# Importações do backend
from .rateio import processar
from . import config as cfg_mod
from .generalsutils import plan_aberta

# =====================================================
# CONFIGURAÇÃO VISUAL E CONSTANTES
# =====================================================
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Paleta de Cores Adimax & UI Moderna
LARANJA_ADIMAX     = "#FFA024"  # Laranja da Marca
COR_HOVER         = "#E58E1F"  # Laranja escuro (interação)
COR_FUNDO_JANELA  = "#F0F2F5"  # Cinza suave (fundo da aplicação)
COR_CARD_BG       = "#FFFFFF"  # Branco (área de conteúdo)
COR_TEXTO_PRINC   = "#333333"  # Cinza escuro (títulos/rótulos)
COR_BOTAO_SEC     = "#374151"  # Cinza chumbo (botões secundários)
COR_LOG_BG        = "#F0F2F5"  # Fundo do terminal
COR_LOG_TXT       = "#000000"  # Texto padrão do terminal

LOGO_FILENAME = "adimax.png"

def get_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()

BASE_DIR = get_base_dir()
LOGO_PATH = os.path.join(BASE_DIR, "..", "assets", LOGO_FILENAME)

# =====================================================
# ADAPTADORES
# =====================================================
class ProgressBarAdapter:
    """Adapta a lógica do backend (inteiros) para o CustomTkinter (0.0 a 1.0)"""
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

# =====================================================
# INTERFACE GRÁFICA PRINCIPAL
# =====================================================
class RateioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Rateio de CT-e")
        self.root.geometry("850x650")
        self.root.minsize(850, 600)
        self.root.configure(fg_color=COR_FUNDO_JANELA)
        
        # Variáveis de Controle
        self.v_planilha = ctk.StringVar()
        self.v_pdfs = ctk.StringVar()
        self.v_xml = ctk.StringVar()
        self.v_saida = ctk.StringVar()
        self.v_pdf_unico = ctk.BooleanVar(value=False)
        self.stop_event = threading.Event()
        self.processando = False
        self.arquivo_log_atual = None

        # Carregar configurações salvas
        self._carregar_config_gui()

        # --- CONTAINER PRINCIPAL (CARD) ---
        self.main_frame = ctk.CTkFrame(
            self.root, 
            corner_radius=15, 
            fg_color=COR_CARD_BG,
            border_color="#E5E7EB",
            border_width=1
        )
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # --- LOGO (COM REDIMENSIONAMENTO PROPORCIONAL) ---
        if os.path.exists(LOGO_PATH):
            pil_img_raw = Image.open(LOGO_PATH)
            base_height = 90
            w_percent = (base_height / float(pil_img_raw.size[1]))
            w_size = int((float(pil_img_raw.size[0]) * float(w_percent)))
            
            self.logo_img = ctk.CTkImage(
                light_image=pil_img_raw, 
                dark_image=pil_img_raw, 
                size=(w_size, base_height)
            )
            ctk.CTkLabel(self.main_frame, text="", image=self.logo_img).pack(pady=(25, 5))

        # --- TÍTULO ---
        ctk.CTkLabel(
            self.main_frame,
            text="SISTEMA DE GRAVAÇÃO DE CT-e",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COR_TEXTO_PRINC
        ).pack(pady=(0, 20))

        # --- CAMPOS DE ENTRADA ---
        self.inputs_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.inputs_frame.pack(fill="x", padx=50)

        self._criar_campo(self.inputs_frame, "Planilha Excel:", self.v_planilha, self.sel_planilha)
        self._criar_campo(self.inputs_frame, "Pasta de PDFs:", self.v_pdfs, self.sel_pdfs)
        self._criar_campo(self.inputs_frame, "Pasta de XMLs:", self.v_xml, self.sel_xml)
        self._criar_campo(self.inputs_frame, "Pasta de Saída:", self.v_saida, self.sel_saida)

        # --- OPÇÕES ---
        ctk.CTkCheckBox(
            self.main_frame,
            text="Unificar arquivos em um único PDF final",
            variable=self.v_pdf_unico,
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO_PRINC,
            hover_color=LARANJA_ADIMAX,
            fg_color=LARANJA_ADIMAX,
            border_color="#9CA3AF"
        ).pack(pady=15)


        self.v_mover_xml = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self.main_frame,
            text="Mover XMLs processados para a pasta de saída",
            variable=self.v_mover_xml,
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO_PRINC,
            hover_color=LARANJA_ADIMAX,
            fg_color=LARANJA_ADIMAX,
            border_color="#9CA3AF"
        ).pack(pady=(0,15))

        # --- BOTÃO DE AÇÃO ---
        self.btn_processar = ctk.CTkButton(
            self.main_frame,
            text="INICIAR PROCESSAMENTO",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=LARANJA_ADIMAX,
            hover_color=COR_HOVER,
            height=45,
            corner_radius=8,
            command=self.acao_botao

        )
        self.btn_processar.pack(fill="x", padx=120, pady=5)

        self.lbl_status = ctk.CTkLabel(
            self.main_frame,
            text="Aguardando início...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#666666"
        )
        self.lbl_status.pack(fill="x", padx=50, pady=(15, 0))

        self.progress_widget = ctk.CTkProgressBar(
            self.main_frame,
            orientation="horizontal",
            progress_color=LARANJA_ADIMAX,
            height=12
        )
        self.progress_widget.set(0)
        self.progress_widget.pack(fill="x", padx=50, pady=(5, 10))
        self.progress_adapter = ProgressBarAdapter(self.progress_widget)

    def _criar_campo(self, parent, texto, var, comando):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            frame, 
            text=texto, 
            width=110, 
            anchor="w",
            text_color=COR_TEXTO_PRINC,
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        ctk.CTkEntry(
            frame, 
            textvariable=var, 
            placeholder_text="Selecione o caminho...",
            height=32,
            border_color="#D1D5DB",
            fg_color="#F9FAFB",
            text_color="#111827"
        ).pack(side="left", fill="x", expand=True, padx=10)

        ctk.CTkButton(
            frame, 
            text="Selecionar", 
            width=90,
            height=32,
            command=comando,
            fg_color=COR_BOTAO_SEC, 
            hover_color="#111827",
            font=ctk.CTkFont(size=11)
        ).pack(side="right")

    def atualizar_status_fase(self, texto):

        self.lbl_status.configure(text=texto)
        self.log_msg(f"{texto}", tag="fase")

    def log_msg(self, msg: str, tag=None):
        if self.arquivo_log_atual:
            try: 
                with open(self.arquivo_log_atual, "a", encoding="utf-8") as f:
                    hora = datetime.now().strftime("%H:%M:%S")
                    f.write(f'[{hora}] {msg}\n')

            except Exception as e:
                print('Erro ao salvar o log. Tipo de erro: {e}')

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
        f = filedialog.askopenfilename(title="Selecionar Planilha", filetypes=[("Excel", "*.xlsx *.xls")])
        if f: self.v_planilha.set(f)

    def sel_pdfs(self):
        d = filedialog.askdirectory(title="Selecionar Pasta de PDFs")
        if d: self.v_pdfs.set(d)

    def sel_xml(self):
        d = filedialog.askdirectory(title="Selecionar Pasta de XMLs")
        if d: self.v_xml.set(d)

    def sel_saida(self):
        d = filedialog.askdirectory(title="Selecionar Pasta de Saída")
        if d: self.v_saida.set(d)

    def acao_botao(self):
        if not self.processando:
            self.iniciar_processamento()
        else:
            self.parar_processamento()


    def parar_processamento(self):
        if messagebox.askyesno("Confirmar", "Deseja realmente cancelar o processamento?"):
            self.stop_event.set() # Levanta a bandeira vermelha
            self.btn_processar.configure(text="CANCELANDO...", state="disabled")
            self.log_msg("⚠️ Solicitação de cancelamento enviada", tag="aviso")

    def iniciar_processamento(self):
        if not all([self.v_planilha.get(), self.v_pdfs.get(), self.v_saida.get()]):
            messagebox.showwarning("Atenção", "Preencha todos os campos obrigatórios.")
            return

        planilha = self.v_planilha.get()

        if not plan_aberta(planilha):
            messagebox.showerror(f'Arquivo Bloqueado!\nA planilha {os.path.basename(planilha)} pode estar aberta em algum computador')

            return
        
        try: 
            pasta_saida = self.v_saida.get()
            timestamp = datetime.now().strftime('%d-%m-%Y - %H-%M-%S')
            nome_log = f'Log_execucao_{timestamp}.txt'
            self.arquivo_log_atual = os.path.join(pasta_saida, nome_log)

            with open(self.arquivo_log_atual, 'w', encoding= 'UTF-8') as f:
                f.write(f"=== RELATÓRIO DE PROCESSAMENTO DE CT-E ===\n")
                f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                f.write(f"Planilha: {planilha}\n")
                f.write(f"Pasta PDFs: {self.v_pdfs.get()}\n")
                f.write("-" * 50 + "\n")
            
        except Exception as e:
            messagebox.showerror("Erro de Permissão", f"Não foi possível criar o arquivo de log na pasta de saída.\nErro: {e}")
        self.processando = True
        self.stop_event.clear()

        self.btn_processar.configure(
            text="PARAR / CANCELAR", 
            fg_color="#E43333",   
            hover_color="#D83030", 
            state="normal"       
        )
        
        self._salvar_config_gui()
        

        threading.Thread(target=self._processar_thread, daemon=True).start()

    def _processar_thread(self):
        self.tempo_inicial = time()
        try:
            processar(
                planilha=self.v_planilha.get(),
                pasta_pdfs=self.v_pdfs.get(),
                pasta_xml=self.v_xml.get(),
                pasta_saida=self.v_saida.get(),
                pdf_unico=self.v_pdf_unico.get(),
                mover_xml=self.v_mover_xml.get(),
                logger_func=self.log_msg,              
                status_func=self.atualizar_status_fase, 
                progresso=self.progress_adapter,
                stop_event=self.stop_event
            )
        except Exception as e:
            self.log_msg(f"ERRO FATAL: {e}", tag="erro")
            self.lbl_status.configure(text="Erro na execução", text_color="red")
        finally:
            self.tempo_final = time()
            self.root.after(0, self.finalizar_processamento)

    def finalizar_processamento(self):
        total_segundos = self.tempo_final- self.tempo_inicial
        duracao = self.tempo_final - self.tempo_inicial
        minutos = int(duracao // 60)
        segundos = int(duracao % 60)            
        tempo_str = f"{minutos}m {segundos}s" if minutos > 0 else f"{round(duracao, 2)}s"

        if self.stop_event.is_set():
            texto_status = "Cancelado pelo usuário"
            cor_status = "#FF8800" 
            self.log_msg("❌ Processo abortado.", tag="erro")
            messagebox.showinfo("Cancelado", "O processamento foi interrompido.")
        else:
            texto_status = f"Concluído em {tempo_str}"
            cor_status = "#228B22"
            messagebox.showinfo("Sucesso", f"Processamento concluído!\nTempo: {tempo_str}")

        self.processando = False
        self.btn_processar.configure(
            state="normal", 
            text="INICIAR PROCESSAMENTO", 
            fg_color=LARANJA_ADIMAX, 
            hover_color=COR_HOVER
        )

        self.lbl_status.configure(text=texto_status, text_color=cor_status)
        self.log_msg("-" * 40)

        if minutos > 0:
            texto_duracao = f'{minutos}:{segundos}'
        else:
            texto_duracao = f'{round(segundos,2)} segundos '

        self.btn_processar.configure(state="normal", text="INICIAR PROCESSAMENTO", fg_color=LARANJA_ADIMAX)
        
        self.lbl_status.configure(text=f"Concluído em {texto_duracao}", text_color="#228B22")
        self.log_msg("-" * 40)
        self.log_msg(f"Processo finalizado em {texto_duracao}.", tag="sucesso")
