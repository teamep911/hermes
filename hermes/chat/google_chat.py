"""Google Chat outbound toolset (in-process, single-VPS topology).

Posts a Cards v2 message to a Google Chat space via its incoming-webhook
URL. The URL is a secret loaded from the environment and never committed.
"""
from __future__ import annotations

from functools import lru_cache

import httpx

from ..config import get_settings
from ..logging import get_logger

log = get_logger("hermes.chat")


class GoogleChatClient:
    def __init__(self, webhook_url: str, enabled: bool) -> None:
        self.webhook_url = webhook_url
        self.enabled = enabled

    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    async def send_card(self, card_payload: dict) -> bool:
        if not self.is_configured():
            log.info("google_chat_disabled_or_unconfigured")
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.webhook_url, json=card_payload)
                resp.raise_for_status()
            log.info("google_chat_sent")
            return True
        except Exception as exc:
            log.warning("google_chat_send_failed", error=str(exc))
            return False


@lru_cache
def get_chat_client() -> GoogleChatClient:
    s = get_settings()
    return GoogleChatClient(s.google_chat_webhook_url, s.google_chat_enabled)
