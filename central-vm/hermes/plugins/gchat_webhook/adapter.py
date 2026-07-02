"""Send-only Google Chat platform adapter (incoming-webhook URL).

Lets a gateway webhook route deliver the agent's full-text RCA to a Google Chat
space via `deliver: gchat_webhook`, without a GCP project / service account /
Pub/Sub. One-way only — Hermes cannot receive from an incoming webhook.

Config: set GOOGLE_CHAT_WEBHOOK_URL in ~/.hermes/.env. The plugin auto-enables
from that env var (see _env_enablement) and registers a home channel so routes
deliver without needing an explicit chat_id.
"""
import logging
import os
import uuid
from typing import Any, Dict, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult

logger = logging.getLogger("gateway.platforms.gchat_webhook")

MAX_MESSAGE_LENGTH = 4000  # Google Chat text message limit ~4096; keep margin.


def _url_from(config=None) -> str:
    if config is not None:
        url = (getattr(config, "extra", None) or {}).get("webhook_url")
        if url:
            return url
    return os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "").strip()


def check_requirements() -> bool:
    if not HTTPX_AVAILABLE:
        logger.warning("[gchat_webhook] httpx not installed")
        return False
    return bool(_url_from())


def validate_config(config) -> bool:
    return bool(_url_from(config))


def is_connected(config) -> bool:
    return bool(_url_from(config))


class GChatWebhookAdapter(BasePlatformAdapter):
    """Posts agent output to a Google Chat space incoming webhook."""

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config):
        super().__init__(config, Platform("gchat_webhook"))
        self._url = _url_from(config)
        self._http_client: Optional["httpx.AsyncClient"] = None

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not HTTPX_AVAILABLE:
            logger.warning("[gchat_webhook] httpx not installed")
            return False
        if not self._url:
            logger.warning("[gchat_webhook] GOOGLE_CHAT_WEBHOOK_URL not set")
            return False
        self._http_client = httpx.AsyncClient(timeout=15.0)
        self._mark_connected()
        logger.info("[gchat_webhook] Connected (send-only incoming webhook)")
        return True

    async def disconnect(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        if not self._http_client:
            return SendResult(success=False, error="HTTP client not initialized")
        if not self._url:
            return SendResult(success=False, error="GOOGLE_CHAT_WEBHOOK_URL not set")

        text = content if len(content) <= self.MAX_MESSAGE_LENGTH else (
            content[: self.MAX_MESSAGE_LENGTH] + "\n…(cắt bớt)"
        )
        try:
            resp = await self._http_client.post(
                self._url,
                headers={"Content-Type": "application/json; charset=UTF-8"},
                json={"text": text},
            )
            if resp.status_code < 300:
                try:
                    msg_id = resp.json().get("name") or uuid.uuid4().hex[:12]
                except Exception:
                    msg_id = uuid.uuid4().hex[:12]
                return SendResult(success=True, message_id=str(msg_id))
            return SendResult(
                success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}"
            )
        except Exception as e:  # noqa: BLE001
            logger.error("[gchat_webhook] Send error: %s", e)
            return SendResult(success=False, error=str(e))

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"id": chat_id, "type": "space", "title": "Google Chat"}


def _env_enablement() -> Optional[dict]:
    url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "").strip()
    if not url:
        return None
    return {
        "webhook_url": url,
        # Home channel so webhook routes deliver without an explicit chat_id.
        "home_channel": {"chat_id": "space", "name": "Google Chat"},
    }


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system at startup."""
    ctx.register_platform(
        name="gchat_webhook",
        label="Google Chat (webhook)",
        adapter_factory=lambda cfg: GChatWebhookAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["GOOGLE_CHAT_WEBHOOK_URL"],
        install_hint="pip install httpx   # already a Hermes dependency",
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="GOOGLE_CHAT_WEBHOOK_URL",
        max_message_length=MAX_MESSAGE_LENGTH,
        emoji="💬",
        pii_safe=False,
        platform_hint=(
            "You are delivering to a Google Chat space via a one-way incoming "
            "webhook. Use concise Google Chat text markdown (*bold*, `code`)."
        ),
    )
