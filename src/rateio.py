import os
import shutil
import time
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from PyPDF2 import PdfReader, PdfWriter

from .pdf_utils import (
    split_pdf_por_cte,
    localizar_pdf,
    criar_overlay,
    sobrepor_pdf,
    debug_chave_no_pdf
)

from .xml_utils import (
    extrair_valor_total_cte,
    chave_cte, extrair_numero_cte_xml,
    extrair_chave_cte, classificar_cte, inf_cte
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
    log,
    progresso=None
):
    """
    Executa o processamento completo de rateio de CT-e.
    """

    tempo_inicial = time.time()

    sucesso = 0
    erros_chave = 0
    erros_pdf = 0

    lista_erros_chave = []
    lista_erros_pdf = []

    cte_complemento_qtd = 0
    cte_complemento_lista = []

    # =====================================================
    # INDEXAÇÃO DE XMLs
    # =====================================================
    mapa_cte = {}

    # =====================================================
    # INDEXAÇÃO DE XMLs
    # =====================================================
    mapa_cte = {}

    if pasta_xml and os.path.isdir(pasta_xml):
        for nome in os.listdir(pasta_xml):
            if not nome.lower().endswith(".xml"):
                continue

            xml_path = os.path.join(pasta_xml, nome)
            chave = extrair_chave_cte(xml_path)
            
            if not chave or not chave_cte(chave):
                continue
                
            numero_xml = extrair_numero_cte_xml(xml_path)
            if not numero_xml:
                continue

            tipo = classificar_cte(xml_path)
            tem_tag_comp = inf_cte(xml_path)
            
            is_complemento = (tipo != '0' or tem_tag_comp)

            if is_complemento:
                log(f"⚠️ Ignorado: {nome} (Tipo: {tipo}, Complemento: {tem_tag_comp})")     
                continue

            if numero_xml in mapa_cte:
                log(f"ℹ️ Número {numero_xml} duplicado ignorado: {nome}")
                continue

            mapa_cte[numero_xml] = {
                'chave': chave,
                'xml': xml_path
            }

    log(f"📌 XMLs Válidos (Normais) indexados: {len(mapa_cte)}")



    # =====================================================
    # RENOMEIO DE PDFs
    # =====================================================
    
    # =====================================================
    # SPLIT DE PDFs
    # =====================================================
    split_temp = os.path.join(pasta_pdfs, "_split_temp")
    pdf_unico_writer = PdfWriter() if pdf_unico else None

    chaves_validas = {info['chave'] for info in mapa_cte.values()}
    for pdf in os.listdir(pasta_pdfs):
        if not pdf.lower().endswith(".pdf"):
            continue

        caminho = os.path.join(pasta_pdfs, pdf)

        try:
            if len(PdfReader(caminho).pages) > 0:
                split_pdf_por_cte(caminho, split_temp, chaves_validas, log)
        except Exception as e:
            log(f'⚠️ Erro ao tentar split no arquivo {pdf}: {e}')
            pass

    pdf_base = split_temp if os.path.isdir(split_temp) else pasta_pdfs

    # =====================================================
    # PLANILHA
    # =====================================================
    df = pd.read_excel(planilha)
    grupos = df.groupby("N° CT-e")

    total_cte = len(grupos)
    if progresso:
        progresso["maximum"] = total_cte

    # =====================================================
    # PROCESSAMENTO PRINCIPAL
    # =====================================================
    for i, (ncte, grupo) in enumerate(grupos, start=1):

        if progresso:
            progresso["value"] = i

        xml_path = None  # ← CORREÇÃO CRÍTICA

        ncte_str = str(int(ncte))
        info_cte = mapa_cte.get(ncte_str)


        if not info_cte:
            erros_chave += 1
            lista_erros_chave.append(ncte_str)
            log(f"❌ CT-e {ncte_str} não encontrado ou ignorado (f)")
            continue
        chave_encontrada = info_cte['chave']
        xml_path = info_cte['xml']


        pdf = localizar_pdf(pdf_base, chave_encontrada)

        debug_chave_no_pdf(pdf, chave_encontrada)

        if not pdf:
            erros_pdf += 1
            lista_erros_pdf.append(ncte_str)
            log(f"❌ PDF não encontrado para CT-e {ncte_str}")
            continue

        reader = PdfReader(pdf)
        
        linhas = []
        valores = []

        valor_cte = extrair_valor_total_cte(xml_path) if xml_path else None

        for _, r in grupo.iterrows():
            base = converter_moeda_para_decimal(r.get("Vlr Contabil"))
            if not base or base <= 0:
                continue

            base = base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            prefixo = identificar_prefixo_oper(str(r.get("Operação", "")))

            if not prefixo:
                continue

            linhas.append({"prefixo": prefixo, "valor": base})
            valores.append(base)

        if valor_cte:
            soma = sum(valores).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            diferenca = (valor_cte - soma).quantize(Decimal("0.01"))

            if diferenca != Decimal("0.00") and abs(diferenca) <= Decimal("0.01"):
                linha_menor = min(linhas, key=lambda x: x["valor"])
                linha_menor["valor"] += diferenca
                log(f"⚠️ Ajuste por arredondamento no CT-e {ncte_str}")

        if not linhas:
            continue

        texto_overlay = [
            f"{l['prefixo']}: R$ {formato_brl(l['valor'])}"
            for l in linhas
        ]

        overlay = os.path.join(pasta_saida, f"{ncte}_overlay.pdf")
        saida = os.path.join(
            pasta_saida,
            os.path.basename(pdf).replace(".pdf", "_rateado.pdf")
        )

        criar_overlay("\n".join(texto_overlay), overlay)

        sobrepor_pdf(pdf, overlay, saida)

        if pdf_unico and pdf_unico_writer:
            reader_temp = PdfReader(saida)
            for p in reader_temp.pages:
                pdf_unico_writer.add_page(p)

        sucesso += 1
        log(f"✔ CT-e {ncte_str} processado")

    # =====================================================
    # PDF ÚNICO
    # =====================================================
    if pdf_unico and pdf_unico_writer:
        caminho_final = os.path.join(pasta_saida, "CTE_RATEIO_UNIFICADO.pdf")
        with open(caminho_final, "wb") as f:
            pdf_unico_writer.write(f)
        log(f"📄 PDF único gerado → {os.path.basename(caminho_final)}")

    # =====================================================
    # RESUMO
    # =====================================================
    log("-" * 30)
    log(f"CT-es processados com sucesso: {sucesso}")
    log(f"Chaves não encontradas: {erros_chave}")
    log(f"PDFs não encontrados: {erros_pdf}")

    if cte_complemento_qtd>0:
        log(f"📌 CT-es de complemento: {cte_complemento_qtd}")

    tempo_final = time.time()
    log(f"⏱️ Tempo total: {round(tempo_final - tempo_inicial, 2)}s")
