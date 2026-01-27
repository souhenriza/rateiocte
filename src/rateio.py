import os
import shutil
import time
from decimal import Decimal, ROUND_HALF_UP
from pandas import read_excel, Grouper
from PyPDF2 import PdfReader, PdfWriter
import re
import traceback 
import pandas as pd

from .pdf_utils import (
    split_pdf_por_cte,
    localizar_pdf,
    criar_overlay,
    sobrepor_pdf
)

from .xml_utils import (
    extrair_chave_cte,
    extrair_valor_total_cte,
    classificar_cte,
    inf_cte,
    chave_cte,
    extrair_numero_cte_xml
)

from .generalsutils import (
    converter_moeda_para_decimal,
    formato_brl,
    identificar_prefixo_oper
)

def processar(
    planilha: str,
    pasta_pdfs: str,
    pasta_xml: str,
    pasta_saida: str,
    pdf_unico: bool,
    mover_xml: bool,
    logger_func,
    status_func,
    progresso=None,
    stop_event = None
):
    tempo_inicial = time.time()

    # Helpers
    def log_info(msg): logger_func(f"ℹ️  {msg}")
    def log_ok(msg):   logger_func(f"✅ {msg}", tag="sucesso")
    def log_err(msg):  logger_func(f"❌ {msg}", tag="erro")
    def log_warn(msg): logger_func(f"⚠️  {msg}", tag="aviso")
    
    def atualizar_status(msg):
        status_func(msg)

    sucesso = 0
    erros_chave = 0
    erros_pdf = 0
    cte_complemento_qtd = 0
    lista_erros_chave = []
    lista_erros_pdf = []
    dados_excel = []

    def gerar_relatorio(cte, status, valor_xml = 0, valor_planilha = 0, msg = '', arquivos = ''):
        dados_excel.append({'CTE': str(cte),
                            'Status': status,
                            'Valor XML': float(valor_xml) if valor_xml else 0.0,
                            'Valor Planilha': float(valor_planilha) if valor_planilha else 0.0,
                            'Diferença': float(valor_xml-valor_planilha) if valor_xml and valor_planilha else 0.0,
                            'Mensagem': msg,
                            'Arquivo Gerado': arquivos})
    atualizar_status("Iniciando varredura de XMLs")
    
    mapa_cte = {}

    if pasta_xml and os.path.isdir(pasta_xml):
        arquivos_xml = [f for f in os.listdir(pasta_xml) if f.lower().endswith(".xml")]
        log_info(f"Encontrados {len(arquivos_xml)} arquivos XML.")

        for idx, nome in enumerate(arquivos_xml):
            if stop_event and stop_event.is_set():
                log_warn('Cancelado pelo usuário na leitura de XML.')
                return 

            msg_curta = re.sub(r'\D', "", nome)
            if len(msg_curta) > 30: msg_curta = msg_curta[:30] + "..."
            
            atualizar_status(f"Lendo XML ({idx+1}/{len(arquivos_xml)}): {msg_curta}")

            xml_path = os.path.join(pasta_xml, nome)
            
            chave = extrair_chave_cte(xml_path)
            if not chave or not chave_cte(chave):
                continue
                
            numero_xml = extrair_numero_cte_xml(xml_path)
            if not numero_xml:
                continue

            tipo = classificar_cte(xml_path)
            tem_tag_comp = inf_cte(xml_path)
            
            if (tipo != '0' or tem_tag_comp):
                cte_complemento_qtd += 1
                gerar_relatorio(numero_xml, 'Ignorado', msg = 'CTe Identificado como Complemento/Anulação')
                continue

            if numero_xml in mapa_cte:
                continue

            mapa_cte[numero_xml] = {
                'chave': chave,
                'xml': xml_path
            }

    log_ok(f"Indexação concluída: {len(mapa_cte)} CT-es válidos.")

    if stop_event and stop_event.is_set(): return

    # =====================================================
    # FASE 2: SPLIT E ORGANIZAÇÃO DE PDFs
    # =====================================================
    atualizar_status("Iniciando análise de PDFs")

    split_temp = os.path.join(pasta_pdfs, "_split_temp")
    chaves_validas = {info['chave'] for info in mapa_cte.values()}
    arquivos_pdf = [p for p in os.listdir(pasta_pdfs) if p.lower().endswith(".pdf")]
    
    if arquivos_pdf:
        for pdf in arquivos_pdf:
            if stop_event and stop_event.is_set():
                log_warn('Cancelado durante leitura de PDF')
                return 

            caminho = os.path.join(pasta_pdfs, pdf)
            try:
                if len(PdfReader(caminho).pages) > 0:
                    split_pdf_por_cte(
                        caminho, 
                        split_temp, 
                        chaves_validas, 
                        log_info, 
                        status_callback=atualizar_status,
                        stop_event=stop_event
                    )
            except Exception as e:
                log_warn(f'Erro ao abrir PDF {pdf}: {e}')
    else:
        log_warn("Nenhum PDF encontrado na pasta.")

    if stop_event and stop_event.is_set(): return

    pdf_base = split_temp if os.path.isdir(split_temp) else pasta_pdfs

    # =====================================================
    # FASE 3: LEITURA DA PLANILHA
    # =====================================================
    atualizar_status("Carregando Planilha Excel")
    try:
        df = read_excel(planilha)
        grupos = df.groupby("N° CT-e")
        total_cte = len(grupos)
        if progresso: progresso["maximum"] = total_cte
        log_ok(f"Planilha carregada: {total_cte} grupos.")
    except Exception as e:
        log_err(f"Erro no Excel: {e}")
        return

    # =====================================================
    # FASE 4: PROCESSAMENTO
    # =====================================================
    pdf_unico_writer = PdfWriter() if pdf_unico else None

    for i, (ncte, grupo) in enumerate(grupos, start=1):
        if stop_event and stop_event.is_set():
            log_warn('Processamento interrompido pelo usuário')
            if os.path.isdir(split_temp):
                try: shutil.rmtree(split_temp)
                except: pass
            return 


        
        if progresso: progresso["value"] = i
        
        ncte_str = str(int(ncte))
        atualizar_status(f"Rateando CT-e {ncte_str} ({i}/{total_cte})")
        info_cte = mapa_cte.get(ncte_str)

        if not info_cte:
            erros_chave += 1
            lista_erros_chave.append(ncte_str)
            log_err(f"CT-e {ncte_str}: XML ausente.")
            gerar_relatorio(numero_xml, 'Erro', msg = 'XML não encontrado na pasta')
            continue

        chave = info_cte['chave']
        xml_path = info_cte['xml']
        pdf = localizar_pdf(pdf_base, chave)

        if not pdf:
            erros_pdf += 1
            lista_erros_pdf.append(ncte_str)
            log_err(f"CT-e {ncte_str}: PDF ausente (Não encontrado na varredura).")
            gerar_relatorio(numero_xml, 'Erro', msg = 'PDF não encontrado ou código não legível')
            continue

        try:
            valores = []
            linhas = []
            valor_cte = extrair_valor_total_cte(xml_path)

            for _, r in grupo.iterrows():
                base = converter_moeda_para_decimal(r.get("Vlr Contabil"))
                if not base or base <= 0: continue
                
                base = base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                prefixo = identificar_prefixo_oper(str(r.get("Operação", "")))
                
                if prefixo:
                    linhas.append({"prefixo": prefixo, "valor": base})
                    valores.append(base)


            soma_planilha = sum(valores).quantize(Decimal('0.01'), rounding =ROUND_HALF_UP) if valores else Decimal('0.00')

            if valor_cte:
                diferenca = (valor_cte - soma_planilha).quantize(Decimal("0.01"))
                if diferenca != Decimal("0.00") and abs(diferenca) <= Decimal("0.01"):
                    if linhas:
                        min(linhas, key=lambda x: x["valor"])["valor"] += diferenca
                        soma_planilha += diferenca

            if not linhas:
                log_warn(f"CT-e {ncte_str}: Sem linhas válidas na planilha.")
                gerar_relatorio(numero_xml, 'Erro', msg = 'Nenhuma linha válida encontrada')
                continue

            texto = [f"{l['prefixo']}: R$ {formato_brl(l['valor'])}" for l in linhas]
            
            overlay = os.path.join(pasta_saida, f"{ncte}_overlay.pdf")
            nome_final = os.path.basename(pdf).replace(".pdf", "_rateado.pdf").replace("_procCTe_rateado.pdf", "_rateado.pdf")
            saida = os.path.join(pasta_saida, nome_final)

            criar_overlay("\n".join(texto), overlay)
            sobrepor_pdf(pdf, overlay, saida)

            if pdf_unico and pdf_unico_writer:
                rd = PdfReader(saida)
                for p in rd.pages: pdf_unico_writer.add_page(p)

            sucesso += 1
            log_ok(f"CT-e {ncte_str} processado.")
            
            gerar_relatorio(numero_xml,
                             'Sucesso', 
                             valor_xml= valor_cte, 
                             valor_planilha = soma_planilha, 
                             msg= 'Processado com Sucesso!', 
                             arquivos= nome_final)
            
            if mover_xml and xml_path and os.path.exists(xml_path):
                try:
                    pasta_processados = os.path.join(os.path.dirname(xml_path), "XML Processados")
                    os.makedirs(pasta_processados, exist_ok=True)

                    nome_arquivo = os.path.basename(xml_path)
                    destino_xml = os.path.join(pasta_processados, nome_arquivo)

                    shutil.move(xml_path, destino_xml)

                except Exception as e_move:
                    log_warn(f"Não foi possível mover o XML: {e_move}")

        except Exception as e:
            trace = traceback.format_exc()
            log_err(f"Erro CT-e {ncte_str}:\n{trace}")
            gerar_relatorio(ncte_str, 'Erro Crítico', msg = 'str{e}')

    # =====================================================
    # FINALIZAÇÃO
    # =====================================================
    if pdf_unico and pdf_unico_writer and not (stop_event and stop_event.is_set()):
        atualizar_status("Gerando PDF Unificado.")
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nome = f"CTE_UNIFICADO_{ts}.pdf"
        with open(os.path.join(pasta_saida, nome), "wb") as f:
            pdf_unico_writer.write(f)
        log_info(f"PDF Unificado: {nome}")

    if os.path.isdir(split_temp):
        try: shutil.rmtree(split_temp, ignore_errors=True)
        except: pass

    if dados_excel:
        atualizar_status('Gerando arquivo Excel')
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            nome_excel = f'Relatório_Rateio{ts}.xlsx'
            caminho_excel = os.path.join(pasta_saida, nome_excel)


            df_rel = pd.DataFrame(dados_excel)
            df_rel.to_excel(caminho_excel, index = False)
            log_info(f'Arquivo Excel Gerado: {nome_excel}')
        except Exception as f:
            log_err(f'Não foi possível salvar o arquivo {nome_excel}\nNºErr: {f}')

    tempo_total_seg = time.time() - tempo_inicial
    minutos = int(tempo_total_seg // 60)
    segundos = int(tempo_total_seg % 60)
    
    if minutos > 0:
        texto_tempo = f'{minutos}m {segundos}s'
    else:
        texto_tempo = f'{round(tempo_total_seg,2)}s'



    print(mapa_cte)
    atualizar_status("Processamento Concluído!")
    logger_func("-" * 30)
    log_ok(f"SUCESSO: {sucesso} | ERROS: {erros_chave + erros_pdf}")
    if cte_complemento_qtd: log_info(f"Complementos ignorados: {cte_complemento_qtd}")
    logger_func(f"⏱️ Tempo: {texto_tempo}")