"""Testes do interpretador local (regras) — sem API, sem internet.

    python -m tests.test_parser
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import parser_local as p  # noqa: E402

HOJE = date(2026, 8, 11)  # terça-feira
FALHAS: list[str] = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {nome}")
    else:
        print(f"  FALHA {nome} {detalhe}")
        FALHAS.append(nome)


def testar_valores() -> None:
    print("\n[extração de valores]")
    casos = [
        ("gastei 45 no mercado", [45.0]),
        ("gastei 45,90 no mercado", [45.90]),
        ("gastei R$ 45,90 no mercado", [45.90]),
        ("gastei r$45,90", [45.90]),
        ("paguei 1.234,56 de aluguel", [1234.56]),
        ("recebi 3.200 de salário", [3200.0]),
        ("almoço 32.50", [32.50]),
        ("50 reais de uber", [50.0]),
        ("30 pila no lanche", [30.0]),
        ("almoço 32 e uber 18", [32.0, 18.0]),
    ]
    for texto, esperado in casos:
        obtido = p.extrair_valores(texto)
        checar(f"{texto!r}", obtido == esperado, f"-> {obtido}, esperado {esperado}")

    # Números que não são valores
    checar("'dia 5' não vira valor", p.extrair_valores("mercado dia 5") == [],
           str(p.extrair_valores("mercado dia 5")))
    checar("'3x' não vira valor", p.extrair_valores("parcelei em 3x") == [],
           str(p.extrair_valores("parcelei em 3x")))


def testar_categorias() -> None:
    print("\n[categorias]")
    casos = [
        ("gastei 45 no mercado", "mercado"),
        ("almoço 32", "alimentacao"),
        ("ifood 48", "alimentacao"),
        ("uber 18", "transporte"),
        ("gasolina 200", "transporte"),
        ("paguei 120 de luz", "moradia"),
        ("aluguel 1500", "moradia"),
        ("farmácia 60", "saude"),
        ("netflix 55", "assinaturas"),
        ("cinema 40", "lazer"),
        ("cabeleireiro 80", "servicos"),
        ("comprei um tênis 300", "compras"),
        ("gastei 25 com sei lá o quê", "outros"),
    ]
    for texto, esperado in casos:
        obtido = p.detectar_categoria(texto, p.PALAVRAS_GASTO, "outros")
        checar(f"{texto!r} -> {esperado}", obtido == esperado, f"deu {obtido}")

    # Armadilha: "mercado livre" é compras, não mercado
    obtido = p.detectar_categoria("comprei no mercado livre 200", p.PALAVRAS_GASTO, "outros")
    checar("'mercado livre' -> compras", obtido == "compras", f"deu {obtido}")


def testar_datas() -> None:
    print("\n[datas]")
    checar("sem menção = hoje",
           p.detectar_data("gastei 45 no mercado", HOJE) == "2026-08-11")
    checar("ontem", p.detectar_data("paguei 120 de luz ontem", HOJE) == "2026-08-10")
    checar("anteontem", p.detectar_data("gastei 30 anteontem", HOJE) == "2026-08-09")
    checar("semana passada",
           p.detectar_data("comprei semana passada 90", HOJE) == "2026-08-04")
    checar("dia 5 (passado, mês corrente)",
           p.detectar_data("paguei dia 5", HOJE) == "2026-08-05")
    # Hoje é terça (11/08). "sexta" = a sexta anterior, 07/08.
    checar("sexta -> última sexta",
           p.detectar_data("jantei sexta 80", HOJE) == "2026-08-07",
           p.detectar_data("jantei sexta 80", HOJE))
    # "terça" numa terça = a terça anterior, não hoje.
    checar("terça numa terça -> semana anterior",
           p.detectar_data("terça 40", HOJE) == "2026-08-04",
           p.detectar_data("terça 40", HOJE))
    # Dia futuro no mês corrente vira mês passado.
    checar("dia 28 -> mês passado",
           p.detectar_data("paguei dia 28", HOJE) == "2026-07-28",
           p.detectar_data("paguei dia 28", HOJE))


def testar_intencoes() -> None:
    print("\n[intenções]")
    casos = [
        ("gastei 45 no mercado", "registrar_gasto"),
        ("almoço 32", "registrar_gasto"),
        ("netflix 55", "registrar_gasto"),
        ("recebi 3000 de salário", "registrar_receita"),
        ("vendi a bicicleta por 800", "registrar_receita"),
        ("caiu 500 do freela", "registrar_receita"),
        ("quanto gastei esse mês?", "consultar"),
        ("resumo do mês", "consultar"),
        ("quanto foi de transporte?", "consultar"),
        ("meus últimos gastos", "listar_ultimos"),
        ("extrato", "listar_ultimos"),
        ("apaga o último", "apagar_ultimo"),
        ("errei, cancela", "apagar_ultimo"),
        ("oi", "ajuda"),
        ("bom dia", "ajuda"),
        ("ajuda", "ajuda"),
        ("asdfgh", "ajuda"),
    ]
    for texto, esperado in casos:
        obtido = p.interpretar(texto, HOJE)[0][0]
        checar(f"{texto!r} -> {esperado}", obtido == esperado, f"deu {obtido}")


def testar_periodos() -> None:
    print("\n[períodos da consulta]")
    casos = [
        ("quanto gastei hoje?", "hoje"),
        ("quanto gastei ontem?", "ontem"),
        ("quanto gastei essa semana?", "semana"),
        ("quanto gastei esse mês?", "mes"),
        ("quanto gastei mês passado?", "mes_passado"),
        ("quanto gastei esse ano?", "ano"),
        ("quanto gastei no total geral?", "tudo"),
        ("quanto gastei?", "mes"),
    ]
    for texto, esperado in casos:
        args = p.interpretar(texto, HOJE)[0][1]
        checar(f"{texto!r} -> {esperado}", args["periodo"] == esperado,
               f"deu {args['periodo']}")

    args = p.interpretar("quanto gastei com transporte esse mês?", HOJE)[0][1]
    checar("consulta filtra categoria", args["categoria"] == "transporte",
           str(args))


def testar_multiplos() -> None:
    print("\n[vários lançamentos numa mensagem]")
    chamadas = p.interpretar("almoço 32 e uber 18", HOJE)
    checar("divide em dois", len(chamadas) == 2, str(len(chamadas)))
    if len(chamadas) == 2:
        checar("primeiro é o almoço",
               chamadas[0][1]["valor"] == 32.0
               and chamadas[0][1]["categoria"] == "alimentacao",
               str(chamadas[0][1]))
        checar("segundo é o uber",
               chamadas[1][1]["valor"] == 18.0
               and chamadas[1][1]["categoria"] == "transporte",
               str(chamadas[1][1]))

    tres = p.interpretar("mercado 100 + farmácia 50 + uber 20", HOJE)
    checar("divide em três", len(tres) == 3, str(len(tres)))

    # Uma frase só com um valor não deve ser dividida
    uma = p.interpretar("paguei 45 de conta de luz e água", HOJE)
    checar("não divide sem dois valores", len(uma) == 1, str(len(uma)))


def testar_descricoes() -> None:
    print("\n[descrições]")
    d = p.interpretar("gastei 45,90 no mercado", HOJE)[0][1]["descricao"]
    checar("limpa verbo e valor", "mercado" in d and "45" not in d, repr(d))
    d = p.interpretar("paguei 120 de luz ontem", HOJE)[0][1]["descricao"]
    checar("remove 'ontem' da descrição", "ontem" not in d, repr(d))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 64)
    print("  finance-bot · interpretador local (regras)")
    print("=" * 64)

    testar_valores()
    testar_categorias()
    testar_datas()
    testar_intencoes()
    testar_periodos()
    testar_multiplos()
    testar_descricoes()

    print("\n" + "=" * 64)
    if FALHAS:
        print(f"  {len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"    - {f}")
        return 1
    print("  Tudo passou.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
