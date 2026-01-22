import os
import shutil
import re

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError

from reportlab.pdfgen import canvas
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode

from PIL import Image


# =====================================================
# UTILITÁRIOS DE CAMINHO (PYINSTALLER)
# =====================================================

def get_base_dir():
    if getattr(__import__("sys"), "frozen", False):
        return __import__("sys")._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# =====================================================
# IDENTIFICAÇÃO DE CHAVE CT-e
# =====================================================

def chave_cte(chave: str) -> bool:
    return (
        chave
        and len(chave) == 44
        and chave.isdigit()
        and chave[20:22] == "57"
    )


# =====================================================
# PDF → IMAGEM (POPPLER)
# =====================================================

def converter_pdf_em_imagens(pdf_path, log=None):
    try:
        poppler_bin = os.path.join(
            get_base_dir(),
            "..",
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
        if log:
            log(f"❌ Erro ao converter PDF em imagens: {e}")
        return []


# =====================================================
# EXTRAÇÃO DE CHAVE CT-e
# =====================================================

def extrair_barcode(imagem, log=None):

    if not imagem:
        return None

    for codigo in decode(imagem):
        try:
            texto = codigo.data.decode("utf-8").strip()
        except Exception:
            continue

        if chave_cte(texto):
            if log:
                log("Código de barras lido com sucesso!")
            return texto

    return None

# =====================================================
# SPLIT DE PDF POR CT-e
# =====================================================

def extrair_chave_somente_barcode(imagem, log=None):
    """
    Tenta extrair a chave CT-e exclusivamente via código de barras.
    Retorna a string de 44 dígitos ou None.
    """
    if not imagem:
        return None
        
    for codigo in decode(imagem):
        try:
            texto = codigo.data.decode("utf-8").strip()

            if chave_cte(texto):
                return texto
        except Exception:
            continue
    return None
# =======================================================

# =======================================================
#
def split_pdf_por_cte(pdf_entrada, pasta_saida, mapa_chaves, log, status_callback=None):
    """
    Divide o PDF validando cada página.
    Aceita 'status_callback' para atualizar a GUI em tempo real (página a página).
    """
    os.makedirs(pasta_saida, exist_ok=True)
    
    try:
        if status_callback:
            status_callback(f"Abrindo PDF: {os.path.basename(pdf_entrada)}...")
            
        reader = PdfReader(pdf_entrada)
        # Convertendo imagens (isso pode demorar, avisa o user)
        if status_callback:
            status_callback(f"Renderizando páginas do PDF para leitura...")
            
        imagens = converter_pdf_em_imagens(pdf_entrada, log) 
    except Exception as e:
        log(f"❌ Erro ao ler PDF: {e}")
        return

    total_paginas = len(reader.pages)

    for i, page in enumerate(reader.pages):
        # --- MICRO-UPDATE: Avisa qual página está lendo ---
        if status_callback:
            status_callback(f"Lendo página {i + 1} de {total_paginas}...")
        # --------------------------------------------------

        imagem = imagens[i] if i < len(imagens) else None
        chave = extrair_chave_somente_barcode(imagem, log)

        if chave and chave in mapa_chaves:
            destino = os.path.join(pasta_saida, f"{chave}-procCTe.pdf")
            
            # --- MICRO-UPDATE: Avisa que está gravando ---
            if status_callback:
                status_callback(f"Gravando arquivo: {chave}...")
            # ---------------------------------------------
            
            if os.path.exists(destino):
                continue

            writer = PdfWriter()
            writer.add_page(page)
            with open(destino, "wb") as f:
                writer.write(f)
            log(f"✔ Página {i + 1} separada: {chave}")
        else:
            if chave:
                log(f"⏭️ Ignorado: Chave {chave} lida, mas não está no mapa.")

# =====================================================
# LOCALIZAÇÃO E RENOMEIO
# =====================================================

def localizar_pdf(pasta, criterio):
    if not criterio or not os.path.isdir(pasta):
        return None

    for nome in os.listdir(pasta):
        if nome.lower().endswith(".pdf") and criterio in nome:
            return os.path.join(pasta, nome)

    return None


def safe_rename(src, dst):
    base, ext = os.path.splitext(dst)
    i = 1
    novo = dst

    while os.path.exists(novo):
        novo = f"{base}({i}){ext}"
        i += 1

    os.rename(src, novo)


def renomear_pdfs_para_xmls(xml_pasta, pdf_pasta, log):
    if not os.path.isdir(xml_pasta):
        return

    for xml in os.listdir(xml_pasta):
        if not xml.lower().endswith(".xml"):
            continue

        chave = re.search(r"(\d{44})", xml)
        if not chave:
            continue

        chave = chave.group(1)
        if not chave_cte(chave):
            continue

        destino = os.path.join(pdf_pasta, f"{chave}-procCTe.pdf")
        if os.path.exists(destino):
            continue

        numero = chave[25:34].lstrip("0")
# ... (código anterior)
    for xml in os.listdir(xml_pasta):
        xml_path = os.path.join(xml_pasta, xml)
        
        # ADICIONE ESTA VALIDAÇÃO AQUI TAMBÉM:
        # Importe as funções necessárias se não estiverem disponíveis
        from .xml_utils import classificar_cte, inf_cte 
        
        tipo = classificar_cte(xml_path)
        if tipo != '0' or inf_cte(xml_path):
            continue # Não usa XML de complemento para renomear PDFs
            
        # ... (segue o restante da sua lógica de renomeio)
        
        pdf = localizar_pdf(pdf_pasta, numero)
        if pdf:
            safe_rename(pdf, destino)
            log(f"🔁 PDF renomeado → {os.path.basename(destino)}")


# =====================================================
# OVERLAY DE TEXTO EM PDF
# =====================================================

def criar_overlay(texto: str, overlay_path: str, x=410, y=120):
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

from PyPDF2 import PdfReader

def debug_chave_no_pdf(pdf_path: str, chave: str):
    try:
        reader = PdfReader(pdf_path)

        for i, page in enumerate(reader.pages):
            texto = page.extract_text() or ""

            if chave in texto:
                print(
                    f"🔎 CHAVE ENCONTRADA NO PDF\n"
                    f"Arquivo: {os.path.basename(pdf_path)}\n"
                    f"Página: {i + 1}\n"
                    f"Chave encontrada: {chave}\n"
                    f"{'-'*50}"
                )
                return i + 1  # página (1-based)

        print(
            f"⚠️ Chave NÃO encontrada no PDF\n"
            f"Arquivo: {os.path.basename(pdf_path)}\n"
            f"Chave procurada: {chave}\n"
            f"{'-'*50}"
        )
        return None

    except Exception as e:
        print(f"❌ Erro ao ler PDF {pdf_path}: {e}")
        return None
