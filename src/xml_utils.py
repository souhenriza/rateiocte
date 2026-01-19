import os
import re
from decimal import Decimal, ROUND_HALF_UP
import xml.etree.ElementTree as ET


# =====================================================
# CHAVE CT-e
# =====================================================

def chave_cte(chave: str) -> bool:
    """
    Valida se a string é uma chave CT-e válida.
    """
    return (
        chave
        and len(chave) == 44
        and chave.isdigit()
        and chave[20:22] == "57"
    )


# =====================================================
# EXTRAÇÃO DE INFORMAÇÕES DO NOME DO XML
# =====================================================

def extract_chave_from_xml_filename(nome_arquivo: str):
    """
    Extrai a chave CT-e (44 dígitos) do nome do arquivo XML.
    """
    match = re.search(r"(\d{44})", nome_arquivo)
    return match.group(1) if match else None


def extract_cte_number_from_chave(chave: str):
    """
    Extrai o número do CT-e a partir da chave.
    """
    return chave[25:34] if chave else None


# =====================================================
# LOCALIZAÇÃO DE XML
# =====================================================

def localizar_xml_por_chave(chave: str, pasta: str):
    """
    Localiza o arquivo XML correspondente à chave CT-e.
    """
    if not chave or not os.path.isdir(pasta):
        return None

    for nome in os.listdir(pasta):
        if nome.lower().endswith(".xml") and chave in nome:
            return os.path.join(pasta, nome)

    return None


# =====================================================
# EXTRAÇÃO DE VALOR TOTAL DO CT-e
# =====================================================

def extrair_valor_total_cte(xml_path: str):
    """
    Extrai o valor total do CT-e (vTPrest) do XML.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        ns = {"cte": "http://www.portalfiscal.inf.br/cte"}

        v_prest = root.find(".//cte:vPrest", ns)
        if v_prest is None:
            return None

        v_tprest = v_prest.find("cte:vTPrest", ns)
        if v_tprest is None:
            return None

        return Decimal(v_tprest.text).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    except Exception:
        return None
