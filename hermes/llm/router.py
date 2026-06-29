"""Provider router: try primary, fall back through the configured chain."""
from __future__ import annotations

from functools import lru_cache

from ..config import Settings, get_settings
from ..logging import get_logger
from .base import LLMError, LLMProvider, LLMResult
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider

log = get_logger("hermes.llm")


def _build_providers(s: Settings) -> dict[str, LLMProvider]:
    return {
        "claude": ClaudeProvider(
            s.anthropic_api_key, s.claude_model, s.llm_timeout_seconds, s.llm_max_tokens
        ),
        "gemini": GeminiProvider(
            s.gemini_api_key, s.gemini_model, s.llm_timeout_seconds, s.llm_max_tokens
        ),
        "openrouter": OpenRouterProvider(
            s.openrouter_api_key,
            s.openrouter_model,
            s.openrouter_base_url,
            s.llm_timeout_seconds,
            s.llm_max_tokens,
        ),
    }


class LLMRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers = _build_providers(settings)
        self.chain = settings.fallback_chain

    async def complete(self, system: str, user: str) -> LLMResult:
        last_error: Exception | None = None
        attempted = False
        for name in self.chain:
            provider = self.providers.get(name)
            if provider is None:
                log.warning("llm_provider_unknown", provider=name)
                continue
            if not provider.is_configured():
                log.info("llm_provider_skipped_unconfigured", provider=name)
                continue
            attempted = True
            try:
                result = await provider.complete(system, user)
                log.info("llm_complete", provider=name, model=result.model)
                return result
            except LLMError as exc:
                last_error = exc
                log.warning("llm_provider_failed", provider=name, error=str(exc))
                continue
        if not attempted:
            raise LLMError("no LLM provider is configured (set an API key)")
        raise LLMError(f"all LLM providers failed; last error: {last_error}")


@lru_cache
def get_router() -> LLMRouter:
    return LLMRouter(get_settings())
