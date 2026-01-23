import os
import sys
import subprocess
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

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
    LAZY LOADING: Converte APENAS UMA página específica do PDF em imagem.
    numero_pagina: Inteiro começando em 1.
    """
    path_poppler = get_poppler_path()
    
    # === PATCH ANTI-FLASH (CMD) ===
    original_popen = subprocess.Popen

    def p_open_sem_janela(*args, **kwargs):
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        
        # Redireciona saídas para evitar erros
        kwargs['stdin'] = subprocess.DEVNULL
        kwargs['stdout'] = subprocess.DEVNULL
        kwargs['stderr'] = subprocess.DEVNULL
        return original_popen(*args, **kwargs)
    
    subprocess.Popen = p_open_sem_janela
    # ==============================

    try:
        if path_poppler:
            # first_page e last_page garantem que só renderizamos O NECESSÁRIO
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
        # Não lançamos erro fatal aqui para tentar continuar outras páginas se for algo pontual
        return None
    finally:
        subprocess.Popen = original_popen

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

    # 1. Abre o PDF apenas para contar páginas e extrair conteúdo
    try:
        reader = PdfReader(pdf_entrada)
        total_paginas = len(reader.pages)
    except Exception as e:
        log(f"❌ Erro leitura PDF {nome_pdf}: {e}")
        return

    # 2. Loop com Lazy Loading
    for i in range(total_paginas):
        # Verifica Cancelamento
        if stop_event and stop_event.is_set():
            if status_callback: status_callback("Interrompendo leitura...")
            return

        numero_real = i + 1  # Poppler usa base 1, Python base 0
        
        if status_callback:
            status_callback(f"Processando página {numero_real} de {total_paginas}...")

        # AQUI ACONTECE A MÁGICA: Renderiza só a página atual
        imagem_atual = renderizar_pagina_unica(pdf_entrada, numero_real, log)
        
        # Tenta ler a chave
        chave = extrair_chave_somente_barcode(imagem_atual, log)

        # Libera a memória da imagem explicitamente (opcional, mas boa prática)
        del imagem_atual 

        if chave and chave in mapa_chaves:
            destino = os.path.join(pasta_saida, f"{chave}-procCTe.pdf")
            
            # Evita re-trabalho se arquivo já existe
            if os.path.exists(destino):
                continue

            # Salva a página isolada
            writer = PdfWriter()
            writer.add_page(reader.pages[i]) # Pega a página do PyPDF2 original
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
    # Fonte corrigida
    c.setFont("Helvetica-Bold", 10)
    x = 50
    y = height - 50 
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