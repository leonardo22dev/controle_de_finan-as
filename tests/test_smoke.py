"""Testes de fumaça — rodam sem chave de API e sem WhatsApp.

    python -m tests.test_smoke

Cobrem tudo menos a chamada real ao Claude: banco, formatação de moeda,
resolução de períodos, montagem das respostas e assinatura do webhook.
"""

import hashlib
import hmac
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import brain, db, fmt, whatsapp  # noqa: E402

FALHAS: list[str] = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {nome}")
    else:
        print(f"  FALHA {nome} {detalhe}")
        FALHAS.append(nome)


def testar_formatacao() -> None:
    print("\n[formatação de moeda]")
    checar("zero", fmt.brl(0) == "R$ 0,00", fmt.brl(0))
    checar("centavos", fmt.brl(5) == "R$ 0,05", fmt.brl(5))
    checar("valor simples", fmt.brl(4590) == "R$ 45,90", fmt.brl(4590))
    checar("milhar", fmt.brl(123456) == "R$ 1.234,56", fmt.brl(123456))
    checar("milhão", fmt.brl(123456789) == "R$ 1.234.567,89", fmt.brl(123456789))
    checar("negativo", fmt.brl(-4590) == "-R$ 45,90", fmt.brl(-4590))

    print("\n[reais -> centavos]")
    checar("45.90", fmt.reais_para_centavos(45.90) == 4590)
    checar("0.1 sem erro de float", fmt.reais_para_centavos(0.1) == 10)
    checar("19.99", fmt.reais_para_centavos(19.99) == 1999)
    # Clássico do float: 1.005 * 100 == 100.49999... — round() resolve.
    checar("1.005 arredonda certo", fmt.reais_para_centavos(1.005) == 100 or
           fmt.reais_para_centavos(1.005) == 101,
           str(fmt.reais_para_centavos(1.005)))


def testar_periodos() -> None:
    print("\n[resolução de períodos]")
    hoje = date(2026, 8, 11)  # uma terça-feira

    i, f, r = brain.resolver_periodo("hoje", hoje)
    checar("hoje", (i, f) == ("2026-08-11", "2026-08-11"), f"{i}..{f}")

    i, f, r = brain.resolver_periodo("ontem", hoje)
    checar("ontem", (i, f) == ("2026-08-10", "2026-08-10"), f"{i}..{f}")

    i, f, r = brain.resolver_periodo("semana", hoje)
    checar("semana começa na segunda", i == "2026-08-10", i)

    i, f, r = brain.resolver_periodo("mes", hoje)
    checar("mês corrente", (i, f) == ("2026-08-01", "2026-08-11"), f"{i}..{f}")

    i, f, r = brain.resolver_periodo("mes_passado", hoje)
    checar("mês passado completo", (i, f) == ("2026-07-01", "2026-07-31"), f"{i}..{f}")

    # Virada de ano: mês passado de janeiro é dezembro do ano anterior.
    i, f, r = brain.resolver_periodo("mes_passado", date(2026, 1, 15))
    checar("mês passado na virada", (i, f) == ("2025-12-01", "2025-12-31"), f"{i}..{f}")

    i, f, r = brain.resolver_periodo("ano", hoje)
    checar("ano", i == "2026-01-01", i)


def testar_banco_e_respostas() -> None:
    print("\n[banco + respostas]")
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / "teste.db"
        db.init()

        uid = db.obter_ou_criar_usuario("5511999999999", "Leonardo")
        checar("cria usuário", isinstance(uid, int) and uid > 0)
        checar("não duplica usuário", db.obter_ou_criar_usuario("5511999999999") == uid)

        hoje = date(2026, 8, 11)

        # Registra alguns lançamentos pelo caminho real (handler do brain).
        r1 = brain._registrar(
            uid, "gasto",
            {"valor": 45.90, "categoria": "mercado", "descricao": "compra da semana",
             "data": "2026-08-11"},
            "gastei 45,90 no mercado", hoje,
        )
        checar("confirmação de gasto tem o valor", "R$ 45,90" in r1, r1)
        checar("confirmação de gasto tem a categoria", "Mercado" in r1, r1)

        brain._registrar(
            uid, "gasto",
            {"valor": 32.00, "categoria": "alimentacao", "descricao": "almoço",
             "data": "2026-08-11"},
            "almoço 32", hoje,
        )
        brain._registrar(
            uid, "gasto",
            {"valor": 25.50, "categoria": "transporte", "descricao": "uber",
             "data": "2026-08-10"},
            "uber 25,50", hoje,
        )
        brain._registrar(
            uid, "receita",
            {"valor": 3000.00, "categoria": "salario", "descricao": "salário",
             "data": "2026-08-05"},
            "recebi 3000 de salário", hoje,
        )

        # Rejeita valores inválidos em vez de gravar lixo.
        r_zero = brain._registrar(
            uid, "gasto",
            {"valor": 0, "categoria": "outros", "descricao": "x", "data": "2026-08-11"},
            "", hoje,
        )
        checar("rejeita valor zero", "maior que zero" in r_zero, r_zero)

        r_nulo = brain._registrar(
            uid, "gasto",
            {"categoria": "outros", "descricao": "x", "data": "2026-08-11"},
            "", hoje,
        )
        checar("rejeita valor ausente", "valor" in r_nulo.lower(), r_nulo)

        # Totais
        total_mes = db.total_periodo(uid, "gasto", "2026-08-01", "2026-08-11")
        checar("total do mês soma certo", total_mes == 4590 + 3200 + 2550,
               str(total_mes))

        total_hoje = db.total_periodo(uid, "gasto", "2026-08-11", "2026-08-11")
        checar("total de hoje exclui ontem", total_hoje == 4590 + 3200, str(total_hoje))

        total_transp = db.total_periodo(
            uid, "gasto", "2026-08-01", "2026-08-11", "transporte"
        )
        checar("filtro por categoria", total_transp == 2550, str(total_transp))

        # Resumo completo
        resumo = brain._consultar(uid, {"periodo": "mes", "categoria": "todas"}, hoje)
        checar("resumo traz o total", "R$ 103,40" in resumo, resumo)
        checar("resumo lista categorias", "Mercado" in resumo and "Transporte" in resumo)
        checar("resumo mostra saldo", "Saldo" in resumo)
        checar("saldo correto", "R$ 2.896,60" in resumo, resumo)

        # Consulta por categoria específica
        r_cat = brain._consultar(
            uid, {"periodo": "mes", "categoria": "transporte"}, hoje
        )
        checar("consulta de categoria", "R$ 25,50" in r_cat, r_cat)

        # Categoria sem gastos
        r_vazio = brain._consultar(uid, {"periodo": "mes", "categoria": "saude"}, hoje)
        checar("categoria vazia responde bem", "Nenhum gasto" in r_vazio, r_vazio)

        # Listagem
        lista = brain._listar(uid, {"quantidade": 5})
        checar("listagem mostra lançamentos", "R$ 45,90" in lista, lista)

        # Apagar o último — LIFO, independente do tipo. O último inserido foi
        # a receita do salário, então é ela que sai primeiro.
        apagou = brain._apagar(uid)
        checar("apagar confirma o que saiu", "Apagado" in apagou, apagou)
        checar("apagar remove o mais recente (a receita)",
               "R$ 3.000,00" in apagou, apagou)
        checar("receita sumiu do total",
               db.total_periodo(uid, "receita", "1900-01-01", "2026-12-31") == 0)

        # LIFO é por ordem de INSERÇÃO, não por data do gasto: o uber foi o
        # terceiro lançado (mesmo sendo datado de ontem), então sai agora.
        antes = db.total_periodo(uid, "gasto", "1900-01-01", "2026-12-31")
        apagou2 = brain._apagar(uid)
        depois = db.total_periodo(uid, "gasto", "1900-01-01", "2026-12-31")
        checar("segundo apagar remove o último inserido (uber)",
               depois == antes - 2550, f"{antes} -> {depois}")
        checar("apagar informa o item removido", "Transporte" in apagou2, apagou2)

        # Esvaziar e conferir o caso "não há nada"
        while "Apagado" in brain._apagar(uid):
            pass
        checar("apagar com banco vazio avisa",
               "Não há nada" in brain._apagar(uid))

        # Idempotência de webhook
        checar("mensagem nova é aceita", db.marcar_processada("wamid.ABC") is True)
        checar("reentrega é rejeitada", db.marcar_processada("wamid.ABC") is False)


def testar_whatsapp() -> None:
    print("\n[webhook do WhatsApp]")
    whatsapp.WHATSAPP_APP_SECRET = "segredo-de-teste"

    corpo = b'{"entry":[]}'
    assinatura = "sha256=" + hmac.new(
        b"segredo-de-teste", corpo, hashlib.sha256
    ).hexdigest()

    checar("assinatura válida passa", whatsapp.assinatura_valida(corpo, assinatura))
    checar("assinatura errada falha",
           not whatsapp.assinatura_valida(corpo, "sha256=" + "0" * 64))
    checar("sem cabeçalho falha", not whatsapp.assinatura_valida(corpo, None))
    checar("corpo adulterado falha",
           not whatsapp.assinatura_valida(b'{"entry":[1]}', assinatura))

    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": "5511999999999",
                                  "profile": {"name": "Leonardo"}}],
                    "messages": [
                        {"id": "wamid.1", "from": "5511999999999", "type": "text",
                         "text": {"body": "gastei 45 no mercado"}},
                        {"id": "wamid.2", "from": "5511999999999", "type": "audio"},
                    ],
                }
            }]
        }]
    }
    msgs = whatsapp.extrair_mensagens(payload)
    checar("extrai só mensagens de texto", len(msgs) == 1, str(len(msgs)))
    checar("extrai o corpo", msgs[0]["texto"] == "gastei 45 no mercado")
    checar("extrai o nome do contato", msgs[0]["nome"] == "Leonardo")

    checar("payload vazio não quebra", whatsapp.extrair_mensagens({}) == [])
    checar("payload de status não quebra",
           whatsapp.extrair_mensagens(
               {"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == [])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  finance-bot · testes de fumaça")
    print("=" * 60)

    testar_formatacao()
    testar_periodos()
    testar_banco_e_respostas()
    testar_whatsapp()

    print("\n" + "=" * 60)
    if FALHAS:
        print(f"  {len(FALHAS)} FALHA(S): {', '.join(FALHAS)}")
        return 1
    print("  Tudo passou.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
