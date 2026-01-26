import os
import sys
import subprocess
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

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




def get_poppler_path():
    """
    Tenta localizar a pasta do Poppler automaticamente.
    """
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    caminhos_possiveis = [
        os.path.join(base_dir, "poppler", "Library", "bin"), 
        os.path.join(base_dir, "poppler", "bin"),           
        os.path.join(base_dir, "poppler"),                  
        os.path.join(base_dir, "assets", "poppler", "Library", "bin"), 
        os.path.join(base_dir, "assets", "poppler", "bin"),
    ]

    for caminho in caminhos_possiveis:
        if os.path.exists(caminho) and ("pdftoppm.exe" in os.listdir(caminho) or "pdftoppm" in os.listdir(caminho)):
            return caminho
    return None

def renderizar_pagina_unica(pdf_path, numero_pagina, log_func=print):
    """
    Converte APENAS UMA página específica do PDF em imagem.
    numero_pagina: Inteiro começando em 1.
    """
    path_poppler = get_poppler_path()
    
    try:
        if path_poppler:
            imagens = convert_from_path(
                pdf_path, 
                dpi=300, 
                first_page=numero_pagina, 
                last_page=numero_pagina, 
                poppler_path=path_poppler
            )
        else:
            imagens = convert_from_path(
                pdf_path, 
                dpi=300, 
                first_page=numero_pagina, 
                last_page=numero_pagina
            )
        
        return imagens[0] if imagens else None

    except Exception as e:
        if "poppler" in str(e).lower():
            log_func(f"❌ ERRO POPPLER: Não encontrado em {path_poppler}")
        return None

def extrair_chave_somente_barcode(imagem, log_func=print):
    """Lê barcode/QR code da imagem e retorna a chave."""
    if imagem is None: return None
    try:
        codigos = decode(imagem)
        for code in codigos:
            dados = code.data.decode("utf-8")
            dados_limpos = dados.replace("CFe", "").strip()
            if len(dados_limpos) == 44 and dados_limpos.isdigit():
                return dados_limpos
    except Exception:
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

        imagem_atual = renderizar_pagina_unica(pdf_entrada, numero_real, log)
        chave = extrair_chave_somente_barcode(imagem_atual, log)
        
        if imagem_atual:
            del imagem_atual 

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