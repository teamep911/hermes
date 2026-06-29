"""Common LLM provider interface."""
from __future__ import annotations

import abc
from dataclasses import dataclass


class LLMError(RuntimeError):
    """Raised when a provider call fails (network, auth, timeout, bad key)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


class LLMProvider(abc.ABC):
    name: str = "base"

    def __init__(self, model: str, timeout: float, max_tokens: int) -> None:
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has the credentials it needs."""

    @abc.abstractmethod
    async def complete(self, system: str, user: str) -> LLMResult:
        """Run a single completion. Raise LLMError on failure."""
