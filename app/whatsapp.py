"""Cliente da WhatsApp Cloud API (Meta) e verificação de assinatura."""

import hashlib
import hmac
import logging

import httpx

from .config import (
    GRAPH_API_VERSION,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_APP_SECRET,
    WHATSAPP_PHONE_NUMBER_ID,
)

log = logging.getLogger(__name__)

BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def assinatura_valida(corpo: bytes, cabecalho: str | None) -> bool:
    """Confere o header X-Hub-Signature-256 contra o corpo *bruto* da requisição.

    Sem isso qualquer pessoa que descubra a URL do webhook consegue injetar
    lançamentos na conta de outro usuário.
    """
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False

    esperado = hmac.new(
        WHATSAPP_APP_SECRET.encode(), corpo, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(esperado, cabecalho.removeprefix("sha256="))


async def enviar_texto(destino: str, texto: str) -> None:
    """Envia uma mensagem de texto. Dentro da janela de 24h é gratuito."""
    url = f"{BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destino,
        "type": "text",
        "text": {"preview_url": False, "body": texto},
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}

    async with httpx.AsyncClient(timeout=20) as cliente:
        r = await cliente.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            log.error("Falha ao enviar para %s: %s %s", destino, r.status_code, r.text)
        r.raise_for_status()


def extrair_mensagens(payload: dict) -> list[dict]:
    """Achata o payload aninhado da Meta em [{id, de, texto, nome}, ...].

    Mensagens que não são de texto (áudio, imagem, sticker) são ignoradas
    nesta versão.
    """
    mensagens = []

    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            valor = mudanca.get("value", {})

            nomes = {
                c.get("wa_id"): c.get("profile", {}).get("name")
                for c in valor.get("contacts", [])
            }

            for msg in valor.get("messages", []):
                if msg.get("type") != "text":
                    continue
                de = msg.get("from", "")
                mensagens.append(
                    {
                        "id": msg.get("id", ""),
                        "de": de,
                        "texto": msg.get("text", {}).get("body", ""),
                        "nome": nomes.get(de),
                    }
                )

    return mensagens
