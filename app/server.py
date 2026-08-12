"""Servidor webhook da WhatsApp Cloud API.

Rodar com:  uvicorn app.server:app --port 8000
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response

from . import db, whatsapp
from .brain import processar
from .config import WHATSAPP_VERIFY_TOKEN, require_anthropic, require_whatsapp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("finance-bot")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    require_anthropic()
    require_whatsapp()
    db.init()
    log.info("Pronto. Webhook em /webhook")
    yield


app = FastAPI(title="finance-bot", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/webhook")
def verificar(request: Request) -> Response:
    """Handshake de verificação que a Meta faz ao cadastrar a URL."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")

    log.warning("Verificação de webhook rejeitada (verify_token incorreto)")
    return Response(status_code=403)


@app.post("/webhook")
async def receber(request: Request, tarefas: BackgroundTasks) -> Response:
    corpo = await request.body()

    if not whatsapp.assinatura_valida(
        corpo, request.headers.get("x-hub-signature-256")
    ):
        log.warning("Assinatura inválida — requisição descartada")
        return Response(status_code=403)

    payload = await request.json()

    # A Meta reentrega o webhook se não receber 200 em ~20s. Processamos em
    # background e respondemos imediatamente.
    for msg in whatsapp.extrair_mensagens(payload):
        if not msg["id"] or not msg["texto"].strip():
            continue
        if not db.marcar_processada(msg["id"]):
            log.info("Mensagem %s já processada — ignorando reentrega", msg["id"])
            continue
        tarefas.add_task(_atender, msg)

    return Response(status_code=200)


async def _atender(msg: dict) -> None:
    try:
        usuario_id = db.obter_ou_criar_usuario(msg["de"], msg["nome"])
        resposta = processar(usuario_id, msg["texto"])
    except Exception:
        log.exception("Erro ao processar mensagem de %s", msg["de"])
        resposta = "Deu um problema aqui do meu lado. Tenta de novo em instantes."

    try:
        await whatsapp.enviar_texto(msg["de"], resposta)
    except Exception:
        log.exception("Erro ao responder %s", msg["de"])
