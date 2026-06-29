"""Anthropic Claude provider (default)."""
from __future__ import annotations

from .base import LLMError, LLMProvider, LLMResult


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str, timeout: float, max_tokens: int) -> None:
        super().__init__(model, timeout, max_tokens)
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, system: str, user: str) -> LLMResult:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic SDK not installed") from exc

        client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        try:
            resp = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # network / auth / rate limit / timeout
            raise LLMError(f"claude call failed: {exc}") from exc

        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = "\n".join(parts).strip()
        if not text:
            raise LLMError("claude returned empty response")
        return LLMResult(text=text, provider=self.name, model=self.model)
