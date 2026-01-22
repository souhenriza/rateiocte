import os
import sys
import subprocess
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

def get_poppler_path():
    """
    Tenta localizar a pasta do Poppler automaticamente.
    Funciona tanto no VS Code quanto no Executável (PyInstaller).
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
            
    return None # Não encontrou

def converter_pdf_em_imagens(pdf_path, log_func=print):
    """
    Converte PDF para imagens usando o caminho explícito do Poppler.
    """
    path_poppler = get_poppler_path()
    
    original_oppen = subprocess.Popen

    def processar_sem_janela(*args, **kwargs):
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            kwargs['startupinfo'] = startupinfo
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        return original_oppen(*args, **kwargs)
    
    subprocess.Popen = processar_sem_janela
    try:
        if path_poppler:
            # Usa o caminho encontrado
            return convert_from_path(pdf_path, dpi=200, poppler_path=path_poppler)
        else:
            # Tenta usar o PATH do sistema (última esperança)
            return convert_from_path(pdf_path, dpi=200)
        
    except Exception as e:
        if "poppler" in str(e).lower():
            log_func(f"❌ ERRO POPPLER: Não foi possível localizar a pasta 'poppler' junto ao executável.\nCaminho tentado: {path_poppler}")
        raise e
    
    finally:
        subprocess.Popen = original_oppen

def extrair_chave_somente_barcode(imagem, log_func=print):
    """
    Recebe uma imagem (PIL), tenta ler barcode/QR code.
    Retorna a chave (string de 44 dígitos) ou None.
    """
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

def split_pdf_por_cte(pdf_entrada, pasta_saida, mapa_chaves, log, status_callback=None):
    """
    Lê o PDF de entrada, converte em imagens para achar a chave,
    e salva cada página individualmente com o nome da chave.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    
    if status_callback:
        status_callback(f"Abrindo PDF: {os.path.basename(pdf_entrada)}")

    try:
        if status_callback: status_callback("Renderizando páginas")
        imagens = converter_pdf_em_imagens(pdf_entrada, log)
    except Exception as e:
        log(f"❌ Erro crítico ao processar imagens do PDF: {e}")
        return 


    try:
        reader = PdfReader(pdf_entrada)
    except Exception as e:
        log(f"❌ Erro ao abrir PDF para leitura: {e}")
        return


    if len(imagens) != len(reader.pages):
        log(f"⚠️ Aviso: O PDF tem {len(reader.pages)} páginas, mas conseguimos renderizar {len(imagens)} imagens. O processamento pode falhar.")

    total_paginas = len(reader.pages)


    for i, page in enumerate(reader.pages):
        if status_callback:
            status_callback(f"Processando página {i + 1} de {total_paginas}")

        if i >= len(imagens):
            break

        imagem = imagens[i]
        chave = extrair_chave_somente_barcode(imagem, log)

        if chave and chave in mapa_chaves:
            destino = os.path.join(pasta_saida, f"{chave}-procCTe.pdf")
            
            if os.path.exists(destino):
                continue

            writer = PdfWriter()
            writer.add_page(page)
            with open(destino, "wb") as f:
                writer.write(f)
            
        else:
            pass

def localizar_pdf(pasta, chave):
    nome_alvo = f"{chave}-procCTe.pdf"
    for root, _, files in os.walk(pasta):
        if nome_alvo in files:
            return os.path.join(root, nome_alvo)
    return None

def criar_overlay(texto_linhas, caminho_saida):
    """Cria um PDF transparente com o texto do rateio"""
    c = canvas.Canvas(caminho_saida, pagesize=A4)
    width, height = A4
    
    c.setFont("", 10)
    
    x = 50
    y = height - 50 
    
    c.setFillColorRGB(0, 0, 0)
    
    # Quebra o texto em linhas
    linhas = texto_linhas.split('\n')
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= 12 
        
    c.save()

def sobrepor_pdf(pdf_original, pdf_overlay, pdf_saida):
    """Mescla o overlay no original"""
    reader_orig = PdfReader(pdf_original)
    reader_over = PdfReader(pdf_overlay)
    
    page_orig = reader_orig.pages[0]
    page_over = reader_over.pages[0]
    
    page_orig.merge_page(page_over)
    
    writer = PdfWriter()
    writer.add_page(page_orig)
    
    with open(pdf_saida, "wb") as f:
        writer.write(f)
        

    try:
        os.remove(pdf_overlay)
    except:
        pass
