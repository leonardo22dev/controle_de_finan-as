"""Simulador local do bot — mesma lógica do WhatsApp, sem precisar da Meta.

Rodar com:  python -m app.cli
"""

import sys

from . import db
from .brain import AJUDA, processar
from .config import ANTHROPIC_MODEL, require_anthropic, usando_claude

TELEFONE_TESTE = "5500000000000"


def main() -> None:
    # O console do Windows costuma vir em cp1252 e engasga nos emojis.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    require_anthropic()
    db.init()
    usuario_id = db.obter_ou_criar_usuario(TELEFONE_TESTE, "Teste local")

    motor = f"Claude ({ANTHROPIC_MODEL})" if usando_claude() else "parser local (custo zero)"
    print("=" * 60)
    print(f"  finance-bot · simulador · interpretador: {motor}")
    print("=" * 60)
    print(AJUDA)
    print()
    print("(digite 'sair' para encerrar)")
    print("-" * 60)

    while True:
        try:
            entrada = input("\nvocê › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            return

        if not entrada:
            continue
        if entrada.lower() in {"sair", "exit", "quit"}:
            print("Até mais!")
            return

        try:
            resposta = processar(usuario_id, entrada)
        except Exception as e:  # noqa: BLE001 — no CLI queremos ver o erro
            print(f"\n[erro] {type(e).__name__}: {e}")
            continue

        print()
        for linha in resposta.split("\n"):
            print(f"  bot │ {linha}" if linha else "      │")


if __name__ == "__main__":
    main()
