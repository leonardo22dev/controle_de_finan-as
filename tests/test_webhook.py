"""Teste ponta a ponta do webhook, sem tocar na Meta nem na API do Claude.

    python -m tests.test_webhook

Confirma o handshake de verificação, a rejeição de assinatura inválida, o
caminho feliz (mensagem -> lançamento gravado -> resposta enviada) e a
proteção contra reentrega duplicada.
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# As variáveis precisam existir ANTES de importar app.config, que as lê no
# momento do import.
_TMP = tempfile.mkdtemp()
os.environ.update(
    {
        "ANTHROPIC_API_KEY": "sk-teste-nao-usada",
        "DB_PATH": str(Path(_TMP) / "webhook.db"),
        "WHATSAPP_PHONE_NUMBER_ID": "1234567890",
        "WHATSAPP_ACCESS_TOKEN": "token-de-teste",
        "WHATSAPP_VERIFY_TOKEN": "verify-de-teste",
        "WHATSAPP_APP_SECRET": "segredo-de-teste",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app import db, server, whatsapp  # noqa: E402

FALHAS: list[str] = []
ENVIADAS: list[tuple[str, str]] = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        print(f"  ok   {nome}")
    else:
        print(f"  FALHA {nome} {detalhe}")
        FALHAS.append(nome)


# --- dublês: nada sai para a rede ------------------------------------------

async def _enviar_falso(destino: str, texto: str) -> None:
    ENVIADAS.append((destino, texto))


def _processar_falso(usuario_id: int, mensagem: str, hoje=None) -> str:
    """Substitui o Claude: grava um gasto fixo e devolve a confirmação."""
    db.inserir_lancamento(
        usuario_id, "gasto", 4590, "mercado", "mercado", "2026-08-11", mensagem
    )
    return "💸 R$ 45,90 · Mercado — mercado (hoje)"


server.whatsapp.enviar_texto = _enviar_falso
server.processar = _processar_falso


def assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(
        b"segredo-de-teste", corpo, hashlib.sha256
    ).hexdigest()


PAYLOAD = {
    "entry": [{
        "changes": [{
            "value": {
                "contacts": [{"wa_id": "5511988887777",
                              "profile": {"name": "Leonardo"}}],
                "messages": [{
                    "id": "wamid.TESTE1",
                    "from": "5511988887777",
                    "type": "text",
                    "text": {"body": "gastei 45,90 no mercado"},
                }],
            }
        }]
    }]
}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  finance-bot · teste do webhook")
    print("=" * 60)

    with TestClient(server.app) as cliente:
        # O TestClient dispara o lifespan; se db.init() não rodasse, a próxima
        # consulta estouraria com "no such table".
        print("\n[startup]")
        with db.conectar() as conn:
            tabelas = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        checar("lifespan criou as tabelas",
               {"usuarios", "lancamentos", "mensagens_processadas"} <= tabelas,
               str(sorted(tabelas)))

        print("\n[GET /webhook — handshake da Meta]")
        r = cliente.get("/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-de-teste",
            "hub.challenge": "desafio-123",
        })
        checar("token correto devolve o challenge",
               r.status_code == 200 and r.text == "desafio-123",
               f"{r.status_code} {r.text!r}")

        r = cliente.get("/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "errado",
            "hub.challenge": "desafio-123",
        })
        checar("token errado é rejeitado", r.status_code == 403, str(r.status_code))

        print("\n[POST /webhook — segurança]")
        corpo = json.dumps(PAYLOAD).encode()
        r = cliente.post("/webhook", content=corpo,
                         headers={"content-type": "application/json"})
        checar("sem assinatura -> 403", r.status_code == 403, str(r.status_code))

        r = cliente.post("/webhook", content=corpo, headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256=" + "0" * 64,
        })
        checar("assinatura falsa -> 403", r.status_code == 403, str(r.status_code))
        checar("nada foi gravado com assinatura inválida", len(ENVIADAS) == 0)

        print("\n[POST /webhook — caminho feliz]")
        r = cliente.post("/webhook", content=corpo, headers={
            "content-type": "application/json",
            "x-hub-signature-256": assinar(corpo),
        })
        checar("assinatura válida -> 200", r.status_code == 200, str(r.status_code))
        checar("respondeu ao usuário", len(ENVIADAS) == 1, str(ENVIADAS))
        checar("respondeu para o número certo",
               ENVIADAS and ENVIADAS[0][0] == "5511988887777")
        checar("resposta tem o valor",
               ENVIADAS and "R$ 45,90" in ENVIADAS[0][1])

        with db.conectar() as conn:
            qtd = conn.execute("SELECT COUNT(*) c FROM lancamentos").fetchone()["c"]
            usuario = conn.execute(
                "SELECT nome FROM usuarios WHERE telefone = ?", ("5511988887777",)
            ).fetchone()
        checar("gravou 1 lançamento", qtd == 1, str(qtd))
        checar("salvou o nome do contato", usuario and usuario["nome"] == "Leonardo")

        print("\n[POST /webhook — reentrega duplicada]")
        r = cliente.post("/webhook", content=corpo, headers={
            "content-type": "application/json",
            "x-hub-signature-256": assinar(corpo),
        })
        with db.conectar() as conn:
            qtd2 = conn.execute("SELECT COUNT(*) c FROM lancamentos").fetchone()["c"]
        checar("reentrega ainda devolve 200", r.status_code == 200)
        checar("reentrega NÃO duplica o gasto", qtd2 == 1, str(qtd2))
        checar("reentrega não responde de novo", len(ENVIADAS) == 1, str(len(ENVIADAS)))

    print("\n" + "=" * 60)
    if FALHAS:
        print(f"  {len(FALHAS)} FALHA(S): {', '.join(FALHAS)}")
        return 1
    print("  Tudo passou.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
