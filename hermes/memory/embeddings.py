"""Embedding generation for similar-error recall.

Supports an external provider (Voyage or Gemini) and an offline,
deterministic `hash` fallback so the system runs end-to-end without any
embedding API key. The redacted error text is what gets embedded — real
values never reach the embedding provider either.
"""
from __future__ import annotations

import hashlib
import math

from ..config import get_settings
from ..logging import get_logger

log = get_logger("hermes.memory.embeddings")


def _hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-tokens hashing embedding (offline fallback).

    Not semantically strong, but stable and dependency-free — good enough
    to wire up and test the recall path before an embedding key exists.
    """
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def _voyage_embed(text: str, api_key: str, model: str) -> list[float]:
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": [text], "model": model},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def _gemini_embed(text: str, api_key: str) -> list[float]:
    from google import genai

    client = genai.Client(api_key=api_key)
    resp = await client.aio.models.embed_content(
        model="text-embedding-004", contents=text
    )
    return list(resp.embeddings[0].values)


async def embed(text: str) -> list[float]:
    s = get_settings()
    provider = s.embedding_provider.lower()
    try:
        if provider == "voyage" and s.voyage_api_key:
            return await _voyage_embed(text, s.voyage_api_key, s.voyage_model)
        if provider == "gemini" and s.gemini_api_key:
            return await _gemini_embed(text, s.gemini_api_key)
    except Exception as exc:  # fall back rather than fail the whole pipeline
        log.warning("embedding_provider_failed_falling_back", provider=provider, error=str(exc))
    return _hash_embed(text, s.embedding_dim)
