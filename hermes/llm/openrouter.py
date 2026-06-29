"""OpenRouter provider (OpenAI-compatible chat completions, fallback)."""
from __future__ import annotations

import httpx

from .base import LLMError, LLMProvider, LLMResult


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(
        self, api_key: str, model: str, base_url: str, timeout: float, max_tokens: int
    ) -> None:
        super().__init__(model, timeout, max_tokens)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, system: str, user: str) -> LLMResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "Hermes Agent",
        }
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=body
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise LLMError(f"openrouter call failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            raise LLMError(f"openrouter malformed response: {data}") from exc
        if not text:
            raise LLMError("openrouter returned empty response")
        return LLMResult(text=text, provider=self.name, model=self.model)
