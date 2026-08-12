"""Interpretador local, por regras — custo zero, sem API, sem internet.

Implementa a mesma interface do `ai.interpretar_com_claude`:
    interpretar(mensagem, hoje) -> [(nome_da_ferramenta, argumentos), ...]

Cobre as frases mais comuns ("gastei 45 no mercado", "almoço 32", "quanto
gastei esse mês"). Não cobre frases criativas — para isso serve o Claude.
Trocar entre os dois é uma variável no .env.
"""

import re
import unicodedata
from datetime import date, timedelta

# --------------------------------------------------------------------------
# Normalização
# --------------------------------------------------------------------------

def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


# --------------------------------------------------------------------------
# Valores monetários
# --------------------------------------------------------------------------

PADRAO_VALOR = re.compile(
    r"""(?:r\$\s*)?
        (
            \d{1,3}(?:\.\d{3})+(?:,\d{1,2})?   # 1.234 | 1.234,56
          | \d+,\d{1,2}                        # 45,90
          | \d+\.\d{2}(?!\d)                   # 45.90  (ponto como decimal)
          | \d+                                # 45
        )""",
    re.VERBOSE | re.IGNORECASE,
)

# Números que NÃO são valores: "dia 5", "às 14", "3x"
CONTEXTO_NAO_VALOR = re.compile(r"(?:\bdia\s+|\bas\s+|\bàs\s+)$", re.IGNORECASE)


def _para_float(bruto: str) -> float:
    t = bruto.strip()
    if "," in t:                                    # 1.234,56 -> 1234.56
        return float(t.replace(".", "").replace(",", "."))
    if t.count(".") == 1:
        inteiro, dec = t.split(".")
        if len(dec) == 3:                           # 1.234 -> milhar
            return float(inteiro + dec)
        return float(t)                             # 45.90 -> decimal
    if t.count(".") > 1:                            # 1.234.567 -> milhar
        return float(t.replace(".", ""))
    return float(t)


def extrair_valores(texto: str) -> list[float]:
    valores = []
    for m in PADRAO_VALOR.finditer(texto):
        antes = texto[: m.start()]
        if CONTEXTO_NAO_VALOR.search(antes):
            continue
        # "3x", "2 vezes" -> quantidade, não valor
        depois = texto[m.end(): m.end() + 2].lower()
        if depois.startswith("x"):
            continue
        valores.append(_para_float(m.group(1)))
    return valores


# --------------------------------------------------------------------------
# Categorias
# --------------------------------------------------------------------------

# Chaves mais específicas primeiro — "mercado livre" precisa vencer "mercado".
PALAVRAS_GASTO: list[tuple[str, str]] = [
    # compras (antes de mercado, por causa de "mercado livre")
    ("mercado livre", "compras"),
    ("mercadolivre", "compras"),
    ("shopee", "compras"), ("amazon", "compras"), ("aliexpress", "compras"),
    ("shopping", "compras"), ("roupa", "compras"), ("tenis", "compras"),
    ("sapato", "compras"), ("camiseta", "compras"), ("calca", "compras"),
    ("presente", "compras"), ("celular", "compras"), ("notebook", "compras"),

    # mercado
    ("supermercado", "mercado"), ("mercado", "mercado"), ("feira", "mercado"),
    ("hortifruti", "mercado"), ("atacadao", "mercado"), ("acougue", "mercado"),
    ("carrefour", "mercado"), ("assai", "mercado"), ("pao de acucar", "mercado"),

    # alimentação
    ("almoco", "alimentacao"), ("janta", "alimentacao"), ("jantar", "alimentacao"),
    ("lanche", "alimentacao"), ("restaurante", "alimentacao"),
    ("ifood", "alimentacao"), ("delivery", "alimentacao"), ("pizza", "alimentacao"),
    ("hamburguer", "alimentacao"), ("burger", "alimentacao"),
    ("padaria", "alimentacao"), ("cafe", "alimentacao"), ("comida", "alimentacao"),
    ("marmita", "alimentacao"), ("sorvete", "alimentacao"), ("acai", "alimentacao"),
    ("cerveja", "alimentacao"), ("bar", "alimentacao"), ("pastel", "alimentacao"),
    ("salgado", "alimentacao"), ("doce", "alimentacao"), ("churrasco", "alimentacao"),

    # transporte
    # "99" sozinho não serve como palavra-chave: "gastei 99 no lanche" casaria
    # com o app de corrida. Só as formas escritas por extenso.
    ("uber", "transporte"), ("99pop", "transporte"), ("99 pop", "transporte"),
    ("taxi", "transporte"),
    ("onibus", "transporte"), ("metro", "transporte"), ("trem", "transporte"),
    ("gasolina", "transporte"), ("combustivel", "transporte"),
    ("alcool", "transporte"), ("etanol", "transporte"), ("posto", "transporte"),
    ("estacionamento", "transporte"), ("pedagio", "transporte"),
    ("passagem", "transporte"), ("bilhete", "transporte"),
    ("mecanico", "transporte"), ("oficina", "transporte"), ("pneu", "transporte"),

    # moradia
    ("aluguel", "moradia"), ("condominio", "moradia"), ("iptu", "moradia"),
    ("luz", "moradia"), ("energia", "moradia"), ("agua", "moradia"),
    ("gas", "moradia"), ("internet", "moradia"), ("wifi", "moradia"),
    ("faxina", "moradia"), ("diarista", "moradia"), ("reforma", "moradia"),
    ("movel", "moradia"), ("moveis", "moradia"),

    # saúde
    ("farmacia", "saude"), ("remedio", "saude"), ("medico", "saude"),
    ("dentista", "saude"), ("consulta", "saude"), ("exame", "saude"),
    ("psicologo", "saude"), ("terapia", "saude"), ("academia", "saude"),
    ("plano de saude", "saude"), ("oculos", "saude"), ("vacina", "saude"),

    # educação
    ("faculdade", "educacao"), ("mensalidade", "educacao"), ("curso", "educacao"),
    ("livro", "educacao"), ("escola", "educacao"), ("apostila", "educacao"),
    ("material escolar", "educacao"),

    # assinaturas
    ("netflix", "assinaturas"), ("spotify", "assinaturas"),
    ("disney", "assinaturas"), ("hbo", "assinaturas"), ("prime", "assinaturas"),
    ("youtube", "assinaturas"), ("icloud", "assinaturas"),
    ("assinatura", "assinaturas"), ("chatgpt", "assinaturas"),

    # lazer
    ("cinema", "lazer"), ("show", "lazer"), ("teatro", "lazer"),
    ("viagem", "lazer"), ("hotel", "lazer"), ("passeio", "lazer"),
    ("jogo", "lazer"), ("balada", "lazer"), ("festa", "lazer"),

    # serviços
    ("cabeleireiro", "servicos"), ("barbeiro", "servicos"),
    ("salao", "servicos"), ("manicure", "servicos"),
    ("lavanderia", "servicos"), ("conserto", "servicos"),
    ("correio", "servicos"), ("cartorio", "servicos"),

    # Nomes das próprias categorias, por último para não roubar de termos
    # mais específicos. Essenciais nas consultas: "quanto gastei com
    # transporte?" precisa casar com a categoria, não com um estabelecimento.
    ("transporte", "transporte"), ("carro", "transporte"),
    ("alimentacao", "alimentacao"),
    ("moradia", "moradia"), ("contas de casa", "moradia"),
    ("saude", "saude"),
    ("educacao", "educacao"),
    ("lazer", "lazer"),
    ("assinaturas", "assinaturas"),
    ("servicos", "servicos"),
    ("compras", "compras"),
]

PALAVRAS_RECEITA: list[tuple[str, str]] = [
    ("salario", "salario"), ("pagamento", "salario"), ("holerite", "salario"),
    ("decimo terceiro", "salario"), ("13o", "salario"),
    ("freela", "freelance"), ("freelance", "freelance"), ("bico", "freelance"),
    ("vendi", "vendas"), ("venda", "vendas"),
    ("rendimento", "rendimentos"), ("dividendo", "rendimentos"),
    ("juros", "rendimentos"), ("cdb", "rendimentos"), ("tesouro", "rendimentos"),
]


def detectar_categoria(texto: str, tabela: list[tuple[str, str]], padrao: str) -> str:
    t = _sem_acento(texto)
    for palavra, categoria in tabela:
        if re.search(rf"\b{re.escape(palavra)}\b", t):
            return categoria
    return padrao


# --------------------------------------------------------------------------
# Datas
# --------------------------------------------------------------------------

DIAS_SEMANA = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "domingo": 6,
}


def detectar_data(texto: str, hoje: date) -> str:
    t = _sem_acento(texto)

    if "anteontem" in t:
        return (hoje - timedelta(days=2)).isoformat()
    if "ontem" in t:
        return (hoje - timedelta(days=1)).isoformat()
    if "semana passada" in t:
        return (hoje - timedelta(days=7)).isoformat()

    # "dia 5", "dia 23"
    m = re.search(r"\bdia\s+(\d{1,2})\b", t)
    if m:
        dia = int(m.group(1))
        try:
            candidato = hoje.replace(day=dia)
        except ValueError:
            return hoje.isoformat()
        # Dia futuro no mês corrente provavelmente é do mês passado.
        if candidato > hoje:
            fim_mes_passado = hoje.replace(day=1) - timedelta(days=1)
            try:
                candidato = fim_mes_passado.replace(day=dia)
            except ValueError:
                return hoje.isoformat()
        return candidato.isoformat()

    # "sexta", "na terça" -> ocorrência mais recente no passado
    for nome, idx in DIAS_SEMANA.items():
        if re.search(rf"\b{nome}(?:-feira)?\b", t):
            delta = (hoje.weekday() - idx) % 7
            delta = delta or 7          # "sexta" numa sexta = sexta passada
            return (hoje - timedelta(days=delta)).isoformat()

    return hoje.isoformat()


# --------------------------------------------------------------------------
# Intenções
# --------------------------------------------------------------------------

GATILHOS_APAGAR = [
    "apaga", "apagar", "deleta", "deletar", "remove", "remover",
    "cancela", "cancelar", "desfaz", "desfazer", "errei", "me enganei",
]
GATILHOS_LISTAR = [
    "ultimos", "ultimas", "historico", "extrato", "lista", "listar", "lancamentos",
]
GATILHOS_CONSULTA = [
    "quanto", "resumo", "relatorio", "balanco", "total", "quanto foi", "gastei com",
]
GATILHOS_AJUDA = [
    "ajuda", "help", "menu", "como funciona", "o que voce faz", "comandos",
]
GATILHOS_SAUDACAO = [
    "oi", "ola", "opa", "eae", "e ai", "bom dia", "boa tarde", "boa noite", "hey",
]
GATILHOS_RECEITA = [
    "recebi", "ganhei", "entrou", "caiu", "vendi", "recebimento",
]


def _tem(texto: str, gatilhos: list[str]) -> bool:
    t = _sem_acento(texto)
    return any(re.search(rf"\b{re.escape(g)}\b", t) for g in gatilhos)


def detectar_periodo(texto: str) -> str:
    t = _sem_acento(texto)
    if "mes passado" in t:
        return "mes_passado"
    if "hoje" in t:
        return "hoje"
    if "ontem" in t:
        return "ontem"
    if "semana" in t:
        return "semana"
    if "ano" in t:
        return "ano"
    if "sempre" in t or "tudo" in t or "geral" in t:
        return "tudo"
    return "mes"


def _limpar_descricao(trecho: str) -> str:
    t = trecho.strip()
    t = PADRAO_VALOR.sub("", t)
    t = re.sub(
        r"\b(gastei|paguei|comprei|torrei|recebi|ganhei|de|no|na|em|com|"
        r"reais|real|pila|conto|contos|mangos|hoje|ontem|anteontem|r\$)\b",
        " ", t, flags=re.IGNORECASE,
    )
    t = re.sub(r"\s+", " ", t).strip(" .,-")
    return t.lower() or "sem descrição"


def _dividir_lancamentos(texto: str) -> list[str]:
    """Quebra 'almoço 32 e uber 18' em dois trechos, cada um com um valor."""
    partes = re.split(r"\s+e\s+|\s*\+\s*|\s*;\s*", texto)
    com_valor = [p for p in partes if extrair_valores(p)]
    return com_valor if len(com_valor) > 1 else [texto]


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def interpretar(mensagem: str, hoje: date) -> list[tuple[str, dict]]:
    texto = mensagem.strip()
    if not texto:
        return [("ajuda", {"motivo": "nao_entendi"})]

    valores = extrair_valores(texto)

    # Ordem importa: apagar e listar vencem, mesmo que haja um número solto.
    if _tem(texto, GATILHOS_APAGAR):
        return [("apagar_ultimo", {})]

    if _tem(texto, GATILHOS_LISTAR):
        qtd = int(valores[0]) if valores and 1 <= valores[0] <= 30 else 10
        return [("listar_ultimos", {"quantidade": qtd})]

    if _tem(texto, GATILHOS_AJUDA):
        return [("ajuda", {"motivo": "pedido_de_ajuda"})]

    # Consulta: gatilho explícito, ou pergunta sem valor.
    if _tem(texto, GATILHOS_CONSULTA) or ("?" in texto and not valores):
        categoria = detectar_categoria(texto, PALAVRAS_GASTO, "todas")
        return [("consultar", {
            "periodo": detectar_periodo(texto),
            "categoria": categoria,
        })]

    if not valores:
        if _tem(texto, GATILHOS_SAUDACAO):
            return [("ajuda", {"motivo": "saudacao"})]
        return [("ajuda", {"motivo": "nao_entendi"})]

    # Registro: um ou vários lançamentos.
    eh_receita = _tem(texto, GATILHOS_RECEITA)
    ferramenta = "registrar_receita" if eh_receita else "registrar_gasto"
    tabela = PALAVRAS_RECEITA if eh_receita else PALAVRAS_GASTO
    padrao = "outros"

    chamadas = []
    for trecho in _dividir_lancamentos(texto):
        vals = extrair_valores(trecho)
        if not vals:
            continue
        chamadas.append((ferramenta, {
            "valor": vals[0],
            "categoria": detectar_categoria(trecho, tabela, padrao),
            "descricao": _limpar_descricao(trecho),
            "data": detectar_data(texto, hoje),
        }))

    return chamadas or [("ajuda", {"motivo": "nao_entendi"})]
