"""Hermes Agent — FastAPI application (hermes-gateway systemd service).

Single-VPS topology: webhook receiver + analysis pipeline + Google Chat
delivery all run in this one process.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import ValidationError

from .config import get_settings
from .db import close_pool, init_pool
from .logging import configure_logging, get_logger
from .models import OemAlert, WebhookResponse
from .pipeline import process_alert
from .security.hmac_auth import verify_signature

log = get_logger("hermes.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        await init_pool()
    except Exception as exc:  # allow boot without DB for health checks / debugging
        log.warning("db_init_deferred", error=str(exc))
    log.info("hermes_started", env=settings.hermes_env, port=settings.hermes_port)
    yield
    await close_pool()


app = FastAPI(title="Hermes Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "hermes-gateway"}


@app.post("/webhook/oem", response_model=WebhookResponse)
async def webhook_oem(
    request: Request,
    x_hermes_signature: str | None = Header(default=None),
) -> WebhookResponse:
    settings = get_settings()
    raw = await request.body()

    if not verify_signature(settings.agent_webhook_secret, raw, x_hermes_signature):
        log.warning("invalid_signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        alert = OemAlert.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    return await process_alert(alert)


@app.post("/google-chat/command")
async def google_chat_command(request: Request) -> dict:
    """Inbound slash-command / interaction events from Google Chat.

    Placeholder for the reverse path (chat -> agent). Verify the Google
    Chat bearer token here before dispatching commands.
    """
    payload = await request.json()
    log.info("google_chat_command_received", type=payload.get("type"))
    return {"text": "Hermes đã nhận lệnh (chưa triển khai xử lý)."}
