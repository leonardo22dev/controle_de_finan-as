"""Interpretação de linguagem natural via Claude.

O modelo não escreve a resposta ao usuário — ele apenas classifica a intenção e
extrai os campos, sempre chamando uma ferramenta. Quem redige a resposta é o
`brain.py`, a partir de dados reais do banco. Isso evita que o bot invente
valores ou totais.
"""

from datetime import date

import anthropic

from . import parser_local
from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, usando_claude
from .db import CATEGORIAS_GASTO, CATEGORIAS_RECEITA

PERIODOS = [
    "hoje",
    "ontem",
    "semana",
    "mes",
    "mes_passado",
    "ano",
    "tudo",
]

FERRAMENTAS = [
    {
        "name": "registrar_gasto",
        "description": (
            "Registra uma saída de dinheiro. Use quando a pessoa relata algo que "
            "gastou, comprou ou pagou. Exemplos: 'gastei 45 no mercado', "
            "'almoço 32', 'paguei 120 de luz ontem', '50 uber'."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "valor": {
                    "type": "number",
                    "description": "Valor em reais, sempre positivo. Ex: 45.9",
                },
                "categoria": {
                    "type": "string",
                    "enum": CATEGORIAS_GASTO,
                    "description": (
                        "Categoria mais adequada. 'alimentacao' é comer fora "
                        "(restaurante, lanche, delivery); 'mercado' é compra de "
                        "supermercado. Use 'outros' apenas se nenhuma servir."
                    ),
                },
                "descricao": {
                    "type": "string",
                    "description": "Descrição curta, em minúsculas. Ex: 'almoço no shopping'",
                },
                "data": {
                    "type": "string",
                    "description": (
                        "Data do gasto em YYYY-MM-DD. Resolva termos relativos "
                        "('ontem', 'sexta passada') com base na data de hoje "
                        "informada. Sem menção de data, use hoje."
                    ),
                },
            },
            "required": ["valor", "categoria", "descricao", "data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "registrar_receita",
        "description": (
            "Registra uma entrada de dinheiro. Use quando a pessoa relata algo "
            "que recebeu. Exemplos: 'recebi 3000 de salário', 'entrou 500 do "
            "freela', 'vendi a bicicleta por 800'."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "valor": {"type": "number", "description": "Valor em reais, positivo."},
                "categoria": {"type": "string", "enum": CATEGORIAS_RECEITA},
                "descricao": {"type": "string", "description": "Descrição curta."},
                "data": {"type": "string", "description": "Data em YYYY-MM-DD."},
            },
            "required": ["valor", "categoria", "descricao", "data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "consultar",
        "description": (
            "Consulta quanto foi gasto num período, opcionalmente filtrando por "
            "categoria. Use para 'quanto gastei esse mês?', 'quanto foi de "
            "transporte?', 'gastei muito com comida essa semana?'. Também use "
            "para pedidos genéricos de resumo/relatório."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                    "description": "Período consultado. Sem menção explícita, use 'mes'.",
                },
                "categoria": {
                    "type": "string",
                    "enum": CATEGORIAS_GASTO + ["todas"],
                    "description": (
                        "Categoria a filtrar, ou 'todas' para o resumo completo "
                        "por categoria."
                    ),
                },
            },
            "required": ["periodo", "categoria"],
            "additionalProperties": False,
        },
    },
    {
        "name": "listar_ultimos",
        "description": (
            "Lista os lançamentos mais recentes. Use para 'meus últimos gastos', "
            "'o que eu lancei hoje', 'mostra o histórico'."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "quantidade": {
                    "type": "integer",
                    "description": "Quantos lançamentos listar. Padrão 10, máximo 30.",
                }
            },
            "required": ["quantidade"],
            "additionalProperties": False,
        },
    },
    {
        "name": "apagar_ultimo",
        "description": (
            "Apaga o lançamento mais recente. Use para 'apaga o último', "
            "'errei', 'desfaz isso', 'cancela'."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "ajuda",
        "description": (
            "Use quando a mensagem não é nenhuma das opções acima: saudações, "
            "pedidos de ajuda, ou mensagens ambíguas demais para virar um "
            "lançamento (ex.: valor ausente)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "enum": ["saudacao", "pedido_de_ajuda", "nao_entendi"],
                }
            },
            "required": ["motivo"],
            "additionalProperties": False,
        },
    },
]

SISTEMA = """Você é o interpretador de um bot de controle de gastos pessoais \
que conversa por WhatsApp, em português do Brasil.

Sua única função é traduzir a mensagem do usuário em chamadas de ferramenta. \
Você nunca escreve a resposta ao usuário — outro componente faz isso a partir \
dos dados reais do banco.

Regras:
- Sempre chame ao menos uma ferramenta. Nunca responda só com texto.
- Se a mensagem contiver vários lançamentos ("gastei 30 no almoço e 15 no uber"), \
chame a ferramenta uma vez para cada lançamento.
- Valores vêm em reais e podem aparecer como "45", "45,90", "R$ 45,90", "45 reais", \
"45 pila". Converta para número decimal com ponto.
- Mensagens sem verbo costumam ser gastos: "uber 25" é um gasto de 25.
- Se houver um valor mas nenhuma pista de categoria, use 'outros' — não peça \
esclarecimento por causa disso.
- Só use a ferramenta 'ajuda' quando realmente não houver um lançamento ou \
consulta possível (por exemplo, quando não há valor algum)."""


_cliente: anthropic.Anthropic | None = None


def _obter_cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _cliente


def _parametros_extras(modelo: str) -> dict:
    """`effort` reduz custo/latência, mas não existe em Haiku 4.5 / Sonnet 4.5
    (enviar lá retorna 400). Só mandamos onde é suportado."""
    sem_effort = ("claude-haiku-4-5", "claude-sonnet-4-5", "claude-haiku-3")
    if any(modelo.startswith(p) for p in sem_effort):
        return {}
    return {"output_config": {"effort": "low"}}


def interpretar(mensagem: str, hoje: date) -> list[tuple[str, dict]]:
    """Interpreta a mensagem com o motor configurado (Claude ou regras locais).

    Ambos devolvem exatamente o mesmo formato, então o resto do app não sabe
    (nem precisa saber) qual dos dois está em uso.
    """
    if usando_claude():
        return interpretar_com_claude(mensagem, hoje)
    return parser_local.interpretar(mensagem, hoje)


def interpretar_com_claude(mensagem: str, hoje: date) -> list[tuple[str, dict]]:
    """Devolve [(nome_da_ferramenta, argumentos), ...] na ordem em que vieram."""
    cliente = _obter_cliente()

    resposta = cliente.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        system=SISTEMA,
        tools=FERRAMENTAS,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Data de hoje: {hoje.isoformat()} "
                    f"({['segunda','terça','quarta','quinta','sexta','sábado','domingo'][hoje.weekday()]}-feira).\n\n"
                    f"Mensagem do usuário:\n{mensagem}"
                ),
            }
        ],
        **_parametros_extras(ANTHROPIC_MODEL),
    )

    chamadas = [
        (bloco.name, bloco.input)
        for bloco in resposta.content
        if bloco.type == "tool_use"
    ]

    # Rede de segurança: se o modelo não chamou nenhuma ferramenta, tratamos
    # como "não entendi" em vez de devolver texto cru ao usuário.
    if not chamadas:
        return [("ajuda", {"motivo": "nao_entendi"})]

    return chamadas
