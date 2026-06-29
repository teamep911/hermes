"""Async PostgreSQL connection pool (asyncpg) with pgvector registration."""
from __future__ import annotations

from typing import Optional

import asyncpg

from .config import get_settings
from .logging import get_logger

log = get_logger("hermes.db")

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Register the pgvector type codec so we can pass python lists as vectors.
    try:
        from pgvector.asyncpg import register_vector

        await register_vector(conn)
    except Exception as exc:  # pragma: no cover - optional until extension installed
        log.warning("pgvector_register_failed", error=str(exc))


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = get_settings().pg_dsn
        if not dsn:
            raise RuntimeError("PG_DSN is not configured")
        _pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=10, init=_init_connection
        )
        log.info("db_pool_initialised")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised; call init_pool() at startup")
    return _pool
