import os
import re
import json
import pandas as pd
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sys
import threading
import shutil

import xml
import xml.etree.ElementTree as ET


from tkinter import (
    Tk, StringVar, filedialog, messagebox,
    Frame, Label, Entry, Button, BooleanVar, Checkbutton
)
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Progressbar, Style

from PIL import Image, ImageTk
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError

from pdf2image import convert_from_path
from pyzbar.pyzbar import decode



# =====================================================
# UTILITÁRIOS (.py / .exe)
# =====================================================

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# =====================================================
# CONFIGURAÇÕES BÁSICAS
# =====================================================

CONFIG_FILE = "config.json"
LOGO_FILENAME = "adimax.png"
LOGO_MAX_WIDTH = 90
LOGO_MAX_HEIGHT = 90

BASE_DIR = get_base_dir()
LOGO_PATH = os.path.join(BASE_DIR, LOGO_FILENAME)


# =====================================================
# CONVERSÃO MONETÁRIA
# =====================================================

def converter_moeda_para_decimal(valor):
    if valor is None:
        return None

    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor))
        except:
            return None

    s = str(valor).strip()
    if s in ("", "nan", "-", "—"):
        return None

    s = s.replace("R$", "").replace(" ", "").replace("\xa0", "")
    s = re.sub(r"[^\d\.,-]", "", s)

    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def formato_brl(valor):
    if valor is None:
        return "0,00"
    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# =====================================================
# IDENTIFICAÇÃO DE OPERAÇÃO
# =====================================================

def identificar_prefixo_oper(operacao: str):
    if not operacao:
        return None

    op = operacao.upper()

    if "VENDA" in op:
        return "V"
    if "BONIF" in op:
        return "B"
    if "AMOSTRA" in op:
        return "A"

    return None


# =====================================================
# CHAVE CT-e
# =====================================================

def chave_cte(chave):
    return (
        chave
        and len(chave) == 44
        and chave.isdigit()
        and chave[20:22] == "57"
    )


# =====================================================
# PDF → IMAGENS
# =====================================================

def converter_pdf_em_imagens(pdf_path, log_func=None):
    try:
        poppler_bin = os.path.join(
            get_base_dir(),
            "poppler",
            "Library",
            "bin"
        )

        return convert_from_path(
            pdf_path,
            dpi=300,
            poppler_path=poppler_bin
        )

    except Exception as e:
        if log_func:
            log_func(f"Erro ao converter PDF em imagens (Poppler): {e}")
        return []


# =====================================================
# LEITURA DE CÓDIGO DE BARRAS
# =====================================================

def extrair_chave_cte_da_imagem(imagem, log_func=None):
    for c in decode(imagem):
        try:
            texto = c.data.decode("utf-8").strip()
        except:
            continue

        if chave_cte(texto):
            if log_func:
                log_func("📦 Chave CT-e captada via código de barras")
            return texto

    return None


def extrair_chave_cte(texto, imagem, log_func=None):
    if texto:
        for c in re.findall(r"\b\d{44}\b", texto.upper()):
            if chave_cte(c):
                return c

    if imagem:
        return extrair_chave_cte_da_imagem(imagem, log_func)

    return None


# =====================================================
# SPLIT DE PDF
# =====================================================

def split_pdf_por_cte(pdf_entrada, pasta_saida, log_func):
    os.makedirs(pasta_saida, exist_ok=True)

    try:
        reader = PdfReader(pdf_entrada)
    except PdfReadError:
        log_func(f"❌ PDF inválido: {os.path.basename(pdf_entrada)}")
        return

    imagens = converter_pdf_em_imagens(pdf_entrada, log_func)

    for i, page in enumerate(reader.pages):
        try:
            texto = page.extract_text()
        except:
            texto = None

        imagem = imagens[i] if i < len(imagens) else None
        chave = extrair_chave_cte(texto, imagem, log_func)

        if not chave:
            log_func(f"❌ Página {i + 1}: chave CT-e não encontrada")
            continue

        destino = os.path.join(pasta_saida, f"{chave}-procCTe.pdf")

        writer = PdfWriter()
        writer.add_page(page)

        with open(destino, "wb") as f:
            writer.write(f)

        log_func(f"✔ Página {i + 1} → {os.path.basename(destino)}")


# =====================================================
# LOCALIZAÇÃO / XML
# =====================================================

def localizar_pdf(pasta, criterio):
    if not criterio or not os.path.isdir(pasta):
        return None

    for nome in os.listdir(pasta):
        if nome.lower().endswith(".pdf") and criterio in nome:
            return os.path.join(pasta, nome)

    return None


def extract_chave_from_xml_filename(nome):
    m = re.search(r"(\d{44})", nome)
    return m.group(1) if m else None


def extract_cte_number_from_chave(chave):
    return chave[25:34] if chave else None


def safe_rename(src, dst):
    base, ext = os.path.splitext(dst)
    i = 1
    novo = dst

    while os.path.exists(novo):
        novo = f"{base}({i}){ext}"
        i += 1

    os.rename(src, novo)


def renomear_pdfs_para_xmls(xml_pasta, pdf_pasta, log_func):
    if not os.path.isdir(xml_pasta):
        return

    for xml in os.listdir(xml_pasta):
        if not xml.lower().endswith(".xml"):
            continue

        chave = extract_chave_from_xml_filename(xml)
        if not chave or not chave_cte(chave):
            continue

        destino = os.path.join(pdf_pasta, f"{chave}-procCTe.pdf")
        if os.path.exists(destino):
            continue

        numero = extract_cte_number_from_chave(chave)
        pdf = localizar_pdf(pdf_pasta, numero)

        if pdf:
            safe_rename(pdf, destino)
            log_func(f"🔁 PDF renomeado → {os.path.basename(destino)}")


# =====================================================
# PDF OVERLAY
# =====================================================

def criar_overlay(texto, overlay_path, x=410, y=120):
    c = canvas.Canvas(overlay_path)
    c.setFont("Helvetica", 10)

    for linha in texto.split("\n"):
        c.drawString(x, y, linha)
        y -= 12

    c.save()


def sobrepor_pdf(pdf_original, overlay_pdf, pdf_saida):
    reader = PdfReader(pdf_original)
    overlay = PdfReader(overlay_pdf)

    page = reader.pages[0]
    page.merge_page(overlay.pages[0])

    writer = PdfWriter()
    writer.add_page(page)

    with open(pdf_saida, "wb") as f:
        writer.write(f)

    os.remove(overlay_pdf)

#---------------------------------------------------------
# UTILITARIOS DE TEMPO

def calculo_tempo(instante_inicial, instantefinal):
    duracao = instantefinal - instante_inicial

    return duracao

def converter_tempo(segundos):
    minutos = int(segundos//60)
    resto = int(segundos % 60)

    if minutos > 0:
        return f"{minutos} min {resto} s"
    return f"{resto} s"



#COMPLEMENTOS

def verificar_complemento(texto_pdf):
    if texto_pdf is None:
        return False

    texto_padrao = texto_pdf.upper()

    if 'COMPLEMENTO' in texto_padrao:
        return True
    else:
        return False
    
#FUNCOES DE VERIFICACAO

def extrair_valor_total_cte(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        ns = {"cte": "http://www.portalfiscal.inf.br/cte"}

        v_prest = root.find(".//cte:vPrest", ns)
        v_tprest = v_prest.find("cte:vTPrest", ns)

        return Decimal(v_tprest.text).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    except Exception:
        return None
    
def localizar_xml_por_chave(chave, pasta):
    if not chave or not os.path.isdir(pasta):
        return None

    for nome in os.listdir(pasta):
        if nome.lower().endswith(".xml") and chave in nome:
            return os.path.join(pasta, nome)

    return None

# =====================================================
# INTERFACE GRÁFICA
# =====================================================


 

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    # ===== DPI AWARENESS (ANTES DE TUDO) =====
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    # ========================================

    root = Tk()

    # ===== ESCALA TKINTER =====
    try:
        dpi = root.winfo_fpixels('1i')
        scaling = dpi / 72
        root.tk.call('tk', 'scaling', scaling)
    except Exception:
        root.tk.call('tk', 'scaling', 1.25)

    # =========================

    # ÍCONE
    try:
        icon_path = os.path.join(get_base_dir(), "adimax.ico")
        root.iconbitmap(icon_path)
    except Exception:
        pass

    RateioGUI(root)
    root.mainloop()
