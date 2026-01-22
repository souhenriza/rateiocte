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


def extrair_numero_cte_xml(xml_path: str) -> str | None:
    """
    Retorna o número do CT-e (nCT) do XML.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        ns = {"cte": "http://www.portalfiscal.inf.br/cte"}

        nct = root.find(".//cte:nCT", ns)
        if nct is None:
            return None

        return nct.text.lstrip("0")

    except Exception:
        return None

def extrair_chave_cte(xml_path: str):   
    if not xml_path or not os.path.exists(xml_path):
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {"cte": "http://www.portalfiscal.inf.br/cte"}

        inf_cte = root.find(".//cte:infCte", ns)
        if inf_cte is not None:
            chave = inf_cte.get('Id', '').replace('CTe','')
            return chave 
        return None

    except Exception:
        return None
    

def classificar_cte(xml_path: str) -> str | None:
    if not xml_path or not os.path.exists(xml_path):
        return None
    
    try: 
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Tenta encontrar com o namespace padrão do CT-e
        ns = {"cte": "http://www.portalfiscal.inf.br/cte"}
        tipo = root.find('.//cte:tpCTe', ns)

        if tipo is not None and tipo.text:
            return tipo.text.strip() # .strip() remove espaços e \n
        
        # Fallback: procura em qualquer lugar sem depender de prefixo de namespace
        for elem in root.iter():
            if elem.tag.endswith('tpCTe'):
                return elem.text.strip() if elem.text else None

        return None
    except Exception:
        return None
    
def inf_cte(xml_path:str) -> bool:
    if not xml_path or not os.path.exists(xml_path):
        return False
    
    try: 
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for elem in root.iter():
            if elem.tag.endswith('infCteComp'):
                return True
            
        return False

    except Exception:
        return False