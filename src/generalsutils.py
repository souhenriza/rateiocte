import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


# =====================================================
# CONVERSÃO MONETÁRIA
# =====================================================

def converter_moeda_para_decimal(valor):
    """
    Converte valores monetários (str, int, float) para Decimal.
    Aceita formatos brasileiros (R$, ponto, vírgula).
    """
    if valor is None:
        return None

    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
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
    """
    Formata Decimal para padrão brasileiro (1.234,56).
    """
    if valor is None:
        return "0,00"

    valor = Decimal(valor).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    s = f"{valor:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# =====================================================
# IDENTIFICAÇÃO DE OPERAÇÃO
# =====================================================

def identificar_prefixo_oper(operacao: str):
    """
    Identifica o prefixo da operação (V, B, A).
    """
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
# VERIFICAÇÕES DE TEXTO
# =====================================================

def verificar_complemento(texto_pdf: str) -> bool:
    """
    Verifica se o CT-e é do tipo COMPLEMENTO.
    """
    if not texto_pdf:
        return False

    return "COMPLEMENTO" in texto_pdf.upper()


# =====================================================
# AJUSTES DE VALOR
# =====================================================

def ajustar_por_arredondamento(linhas, diferenca, log=None):
    """
    Aplica ajuste de arredondamento na menor linha.
    """
    if not linhas or diferenca == Decimal("0.00"):
        return False

    linha_menor = min(linhas, key=lambda x: x["valor"])
    valor_original = linha_menor["valor"]

    linha_menor["valor"] += diferenca

    if log:
        log(
            f"⚠️ Ajuste por arredondamento: "
            f"{formato_brl(valor_original)} → "
            f"{formato_brl(linha_menor['valor'])}"
        )

    return True
