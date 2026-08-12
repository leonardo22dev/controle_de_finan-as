"""Carregamento e validação das variáveis de ambiente."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

# Quem interpreta as mensagens:
#   auto   -> Claude se houver chave, senão o parser local (padrão)
#   claude -> força o Claude (falha sem chave)
#   local  -> força o parser por regras (custo zero)
INTERPRETADOR = os.getenv("INTERPRETADOR", "auto").strip().lower()


def usando_claude() -> bool:
    if INTERPRETADOR == "local":
        return False
    if INTERPRETADOR == "claude":
        return True
    return bool(ANTHROPIC_API_KEY)

DB_PATH = ROOT / os.getenv("DB_PATH", "finance.db")

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

# Fuso usado para resolver "hoje", "ontem", "esse mês".
TIMEZONE = "America/Sao_Paulo"


def require_anthropic() -> None:
    """Só exige a chave quando o Claude é realmente o interpretador escolhido."""
    if usando_claude() and not ANTHROPIC_API_KEY:
        raise SystemExit(
            "INTERPRETADOR=claude exige ANTHROPIC_API_KEY.\n"
            "Preencha a chave no .env, ou use INTERPRETADOR=local "
            "para rodar sem custo com o parser por regras."
        )


def require_whatsapp() -> None:
    faltando = [
        nome
        for nome, valor in [
            ("WHATSAPP_PHONE_NUMBER_ID", WHATSAPP_PHONE_NUMBER_ID),
            ("WHATSAPP_ACCESS_TOKEN", WHATSAPP_ACCESS_TOKEN),
            ("WHATSAPP_VERIFY_TOKEN", WHATSAPP_VERIFY_TOKEN),
            ("WHATSAPP_APP_SECRET", WHATSAPP_APP_SECRET),
        ]
        if not valor
    ]
    if faltando:
        raise SystemExit(
            "Faltam variáveis do WhatsApp no .env: " + ", ".join(faltando)
        )
