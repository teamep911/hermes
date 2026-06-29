"""Google Gemini provider (fallback)."""
from __future__ import annotations

from .base import LLMError, LLMProvider, LLMResult


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float, max_tokens: int) -> None:
        super().__init__(model, timeout, max_tokens)
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, system: str, user: str) -> LLMResult:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise LLMError("google-genai SDK not installed") from exc

        client = genai.Client(api_key=self.api_key)
        try:
            resp = await client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=self.max_tokens,
                ),
            )
        except Exception as exc:
            raise LLMError(f"gemini call failed: {exc}") from exc

        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            raise LLMError("gemini returned empty response")
        return LLMResult(text=text, provider=self.name, model=self.model)
