import os
import fitz  # PyMuPDF
from PIL import Image
from pyzbar.pyzbar import decode
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import re
import sys
import subprocess



if sys.platform == "win32":

    _OriginalPopen = subprocess.Popen

    class PopenSemJanela(_OriginalPopen):
        def __init__(self, *args, **kwargs):
            # Definições de flags do Windows para esconder janelas
            startupinfo = kwargs.get('startupinfo', subprocess.STARTUPINFO())
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
            
            
            creationflags = kwargs.get('creationflags', 0)
            kwargs['creationflags'] = creationflags | 0x08000000 
            
            if 'stdin' not in kwargs: kwargs['stdin'] = subprocess.DEVNULL
            if 'stdout' not in kwargs: kwargs['stdout'] = subprocess.DEVNULL
            if 'stderr' not in kwargs: kwargs['stderr'] = subprocess.DEVNULL
            
            super().__init__(*args, **kwargs)

    subprocess.Popen = PopenSemJanela


def renderizar_paginas(pdf_path, numero_pag_base):
    try:
        doc = fitz.open(pdf_path)

        page_index = numero_pag_base - 1

        if page_index < 0 or page_index >= len(doc):
            return None
        
        page = doc.load_page(page_index)

        zoom = 3
        
        mat = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix = mat)

        img_data = pix.tobytes('png')
        img_pil = Image.open(io.BytesIO(img_data))

        doc.close()
        return img_pil
    except Exception as e:
        print(f'Erro PymuPDF {e}')
        return None
    

def extrair_chave_barcode(img_pil, log_func = print):

    if img_pil is None: return None

    try: 
        codigos = decode(img_pil)

        for code in codigos: 
            dados = code.data.decode('utf-8')
            dados_limpos = re.sub(r'\D', '', dados)

            if len(dados_limpos) == 44:
                return dados_limpos
    except Exception as e:
        pass
    return None

def split_pdf_por_cte(pdf_entrada, pasta_saida, mapa_chaves, log, status_callback=None, stop_event=None):
    """
    Divide o PDF usando Lazy Loading (processa uma página por vez).
    """
    os.makedirs(pasta_saida, exist_ok=True)
    nome_pdf = os.path.basename(pdf_entrada)
    
    if status_callback:
        status_callback(f"Abrindo PDF: {nome_pdf}...")

    try:
        reader = PdfReader(pdf_entrada)
        total_paginas = len(reader.pages)
    except Exception as e:
        log(f"❌ Erro leitura PDF {nome_pdf}: {e}")
        return

    for i in range(total_paginas):
        if stop_event and stop_event.is_set():
            if status_callback: status_callback("Interrompendo leitura...")
            return

        numero_real = i + 1
        
        if status_callback:
            status_callback(f"Lendo página {numero_real} de {total_paginas}.")

        imagem = renderizar_paginas(pdf_entrada, numero_real)
        chave = extrair_chave_barcode(imagem, log)
        
        if imagem:
            imagem.close()
            del imagem 

        if chave and chave in mapa_chaves:
            destino = os.path.join(pasta_saida, f"{chave}-procCTe.pdf")
            if os.path.exists(destino):
                continue

            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            with open(destino, "wb") as f:
                
                writer.write(f)

def localizar_pdf(pasta, chave):
    nome_alvo = f"{chave}-procCTe.pdf"
    for root, _, files in os.walk(pasta):
        if nome_alvo in files:
            return os.path.join(root, nome_alvo)
    return None

def criar_overlay(texto_linhas, caminho_saida):
    c = canvas.Canvas(caminho_saida, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 10) 
    x = 410
    y = 120
    c.setFillColorRGB(0, 0, 0)
    linhas = texto_linhas.split('\n')
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= 12
    c.save()

def sobrepor_pdf(pdf_original, pdf_overlay, pdf_saida):
    """Cola a etiqueta em cima do PDF original"""
    reader_orig = PdfReader(pdf_original)
    reader_over = PdfReader(pdf_overlay)
    
    page_orig = reader_orig.pages[0]
    page_over = reader_over.pages[0]
    
    page_orig.merge_page(page_over)
    
    writer = PdfWriter()
    writer.add_page(page_orig)
    
    with open(pdf_saida, "wb") as f:
        writer.write(f)
        
    try: os.remove(pdf_overlay)
    except: pass