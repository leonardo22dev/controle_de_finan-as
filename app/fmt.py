"""Formatação de valores, datas e blocos de texto para o WhatsApp."""

from datetime import date

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def brl(centavos: int) -> str:
    """123456 -> 'R$ 1.234,56'"""
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    milhar = f"{inteiro:,}".replace(",", ".")
    return f"{sinal}R$ {milhar},{resto:02d}"


def reais_para_centavos(valor: float) -> int:
    """Converte reais (float vindo do modelo) para centavos inteiros.

    Dinheiro é sempre guardado como int no banco — float acumula erro de
    arredondamento e some com centavos ao longo de centenas de lançamentos.
    """
    return int(round(valor * 100))


def data_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"


def barra(fracao: float, largura: int = 10) -> str:
    """Mini-gráfico de barras com blocos, para o resumo por categoria."""
    cheios = max(0, min(largura, round(fracao * largura)))
    return "█" * cheios + "░" * (largura - cheios)
