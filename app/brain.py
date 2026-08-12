"""Regras de negócio: transforma intenções em ações no banco e redige a resposta.

Toda resposta enviada ao usuário nasce aqui, a partir de dados lidos do banco —
o modelo nunca gera números.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from . import db
from .ai import interpretar
from .config import TIMEZONE
from .fmt import barra, brl, data_extenso, reais_para_centavos

AJUDA = """Oi! Sou seu controle de gastos. É só falar naturalmente:

*Registrar*
· gastei 45 no mercado
· almoço 32
· paguei 120 de luz ontem
· recebi 3000 de salário

*Consultar*
· quanto gastei esse mês?
· quanto foi de transporte?
· resumo da semana

*Corrigir*
· apaga o último
· meus últimos gastos

Pode mandar vários de uma vez: _"gastei 30 no almoço e 15 no uber"_."""


def hoje_local() -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo(TIMEZONE)).date()


# --------------------------------------------------------------------------
# Períodos
# --------------------------------------------------------------------------

def resolver_periodo(periodo: str, hoje: date) -> tuple[str, str, str]:
    """Devolve (data_inicio, data_fim, rótulo legível)."""
    if periodo == "hoje":
        return hoje.isoformat(), hoje.isoformat(), "hoje"

    if periodo == "ontem":
        d = hoje - timedelta(days=1)
        return d.isoformat(), d.isoformat(), "ontem"

    if periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())  # segunda-feira
        return inicio.isoformat(), hoje.isoformat(), "esta semana"

    if periodo == "mes":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), "este mês"

    if periodo == "mes_passado":
        fim = hoje.replace(day=1) - timedelta(days=1)
        inicio = fim.replace(day=1)
        return inicio.isoformat(), fim.isoformat(), "o mês passado"

    if periodo == "ano":
        return hoje.replace(month=1, day=1).isoformat(), hoje.isoformat(), "este ano"

    return "1900-01-01", hoje.isoformat(), "todo o período"


# --------------------------------------------------------------------------
# Handlers por intenção
# --------------------------------------------------------------------------

def _registrar(usuario_id: int, tipo: str, args: dict, bruto: str, hoje: date) -> str:
    try:
        valor = float(args["valor"])
    except (TypeError, ValueError, KeyError):
        return "Não consegui identificar o valor. Tenta assim: _gastei 45 no mercado_"

    if valor <= 0:
        return "O valor precisa ser maior que zero."

    centavos = reais_para_centavos(valor)
    categoria = args.get("categoria", "outros")
    descricao = (args.get("descricao") or "").strip() or "sem descrição"
    ocorrido = args.get("data") or hoje.isoformat()

    db.inserir_lancamento(
        usuario_id, tipo, centavos, categoria, descricao, ocorrido, bruto
    )

    rotulo = db.ROTULOS.get(categoria, categoria.title())
    icone = "💸" if tipo == "gasto" else "💰"

    try:
        d = date.fromisoformat(ocorrido)
        quando = "hoje" if d == hoje else data_extenso(d)
    except ValueError:
        quando = "hoje"

    return f"{icone} {brl(centavos)} · {rotulo} — {descricao} ({quando})"


def _consultar(usuario_id: int, args: dict, hoje: date) -> str:
    periodo = args.get("periodo", "mes")
    categoria = args.get("categoria", "todas")
    inicio, fim, rotulo_periodo = resolver_periodo(periodo, hoje)

    if categoria != "todas":
        total = db.total_periodo(usuario_id, "gasto", inicio, fim, categoria)
        nome = db.ROTULOS.get(categoria, categoria.title())
        if total == 0:
            return f"Nenhum gasto com *{nome}* {rotulo_periodo}."
        return f"*{nome}* {rotulo_periodo}: {brl(total)}"

    linhas = db.total_por_categoria(usuario_id, "gasto", inicio, fim)
    if not linhas:
        return f"Nenhum gasto registrado {rotulo_periodo}."

    total = sum(l["total"] for l in linhas)
    partes = [f"*Gastos {rotulo_periodo}: {brl(total)}*", ""]

    for l in linhas:
        nome = db.ROTULOS.get(l["categoria"], l["categoria"].title())
        fracao = l["total"] / total if total else 0
        partes.append(
            f"{barra(fracao)} {brl(l['total'])}\n"
            f"    {nome} · {l['qtd']}x · {fracao * 100:.0f}%"
        )

    receitas = db.total_periodo(usuario_id, "receita", inicio, fim)
    if receitas:
        saldo = receitas - total
        sinal = "🟢" if saldo >= 0 else "🔴"
        partes.append("")
        partes.append(f"Entradas: {brl(receitas)}")
        partes.append(f"{sinal} Saldo: {brl(saldo)}")

    return "\n".join(partes)


def _listar(usuario_id: int, args: dict) -> str:
    try:
        qtd = int(args.get("quantidade", 10))
    except (TypeError, ValueError):
        qtd = 10
    qtd = max(1, min(30, qtd))

    linhas = db.listar_recentes(usuario_id, qtd)
    if not linhas:
        return "Você ainda não tem nenhum lançamento."

    partes = [f"*Últimos {len(linhas)} lançamentos*", ""]
    for l in linhas:
        icone = "💸" if l["tipo"] == "gasto" else "💰"
        nome = db.ROTULOS.get(l["categoria"], l["categoria"].title())
        try:
            quando = data_extenso(date.fromisoformat(l["ocorrido_em"]))
        except ValueError:
            quando = l["ocorrido_em"]
        partes.append(f"{icone} {brl(l['valor_centavos'])} · {nome}")
        partes.append(f"    {l['descricao']} — {quando}")

    return "\n".join(partes)


def _apagar(usuario_id: int) -> str:
    linha = db.apagar_ultimo(usuario_id)
    if linha is None:
        return "Não há nada para apagar."
    nome = db.ROTULOS.get(linha["categoria"], linha["categoria"].title())
    return f"🗑️ Apagado: {brl(linha['valor_centavos'])} · {nome} — {linha['descricao']}"


def _ajuda(args: dict) -> str:
    motivo = args.get("motivo", "pedido_de_ajuda")
    if motivo == "saudacao":
        return "Oi! 👋\n\n" + AJUDA
    if motivo == "nao_entendi":
        return "Não entendi essa. 🤔\n\n" + AJUDA
    return AJUDA


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def processar(usuario_id: int, mensagem: str, hoje: date | None = None) -> str:
    """Interpreta a mensagem, aplica os efeitos e devolve o texto de resposta."""
    hoje = hoje or hoje_local()
    chamadas = interpretar(mensagem, hoje)

    respostas: list[str] = []
    houve_registro = False

    for nome, args in chamadas:
        if nome == "registrar_gasto":
            respostas.append(_registrar(usuario_id, "gasto", args, mensagem, hoje))
            houve_registro = True
        elif nome == "registrar_receita":
            respostas.append(_registrar(usuario_id, "receita", args, mensagem, hoje))
            houve_registro = True
        elif nome == "consultar":
            respostas.append(_consultar(usuario_id, args, hoje))
        elif nome == "listar_ultimos":
            respostas.append(_listar(usuario_id, args))
        elif nome == "apagar_ultimo":
            respostas.append(_apagar(usuario_id))
        else:
            respostas.append(_ajuda(args))

    # Depois de registrar, mostra o acumulado do mês — o dado que a pessoa
    # realmente quer saber depois de anotar um gasto.
    if houve_registro:
        inicio = hoje.replace(day=1).isoformat()
        total_mes = db.total_periodo(usuario_id, "gasto", inicio, hoje.isoformat())
        respostas.append(f"\n_Total do mês: {brl(total_mes)}_")

    return "\n".join(respostas)
