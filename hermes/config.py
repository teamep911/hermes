"""Runtime configuration loaded from environment (.env.runtime).

No secrets, hostnames, IPs or domains are hard-coded — everything comes
from the environment so the repository stays clean and shareable.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2, "fatal": 3}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.runtime", env_file_encoding="utf-8", extra="ignore"
    )

    # service
    hermes_host: str = "0.0.0.0"
    hermes_port: int = 2020
    hermes_env: str = "production"
    log_level: str = "INFO"

    # inbound auth
    agent_webhook_secret: str = ""

    # database
    pg_dsn: str = ""

    # llm routing
    llm_primary: str = "claude"
    llm_fallbacks: str = "gemini,openrouter"
    llm_timeout_seconds: float = 45.0
    llm_max_tokens: int = 2048

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-8"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"

    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-opus-4-8"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # embeddings / memory
    embedding_provider: str = "hash"
    embedding_dim: int = 1024
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    memory_top_k: int = 5
    memory_min_score: float = 0.78

    # google chat
    google_chat_webhook_url: str = ""
    google_chat_enabled: bool = True

    # cost / latency controls
    dedup_window_seconds: int = 900
    llm_min_severity: str = "warning"

    @property
    def fallback_chain(self) -> list[str]:
        chain = [self.llm_primary.strip()]
        for name in self.llm_fallbacks.split(","):
            name = name.strip()
            if name and name not in chain:
                chain.append(name)
        return chain

    def severity_meets_threshold(self, severity: str) -> bool:
        threshold = SEVERITY_ORDER.get(self.llm_min_severity.lower(), 1)
        return SEVERITY_ORDER.get(severity.lower(), 1) >= threshold


@lru_cache
def get_settings() -> Settings:
    return Settings()
