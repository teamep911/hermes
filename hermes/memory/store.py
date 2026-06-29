"""Incident memory backed by PostgreSQL + pgvector.

Tables (see infra/sql/schema.sql):
  incident(id, signature, alert_type, target_name, severity, summary,
           root_cause, rca_json, created_at)
  incident_embedding(incident_id, embedding vector)

All text stored here is the REDACTED form — the database never holds raw
IPs / hostnames / secrets.
"""
from __future__ import annotations

import json

from ..config import get_settings
from ..db import pool
from ..logging import get_logger
from ..models import RcaResult
from .embeddings import embed

log = get_logger("hermes.memory.store")


async def is_duplicate(signature: str, window_seconds: int) -> bool:
    """True if an incident with the same signature was seen recently."""
    row = await pool().fetchrow(
        """
        SELECT 1 FROM incident
        WHERE signature = $1
          AND created_at > now() - ($2 || ' seconds')::interval
        LIMIT 1
        """,
        signature,
        str(window_seconds),
    )
    return row is not None


async def recall_similar(redacted_text: str, top_k: int, min_score: float) -> list[dict]:
    """Return up to top_k past incidents above the cosine-similarity floor."""
    vector = await embed(redacted_text)
    rows = await pool().fetch(
        """
        SELECT i.id, i.signature, i.summary, i.root_cause, i.severity,
               1 - (e.embedding <=> $1) AS score
        FROM incident_embedding e
        JOIN incident i ON i.id = e.incident_id
        ORDER BY e.embedding <=> $1
        LIMIT $2
        """,
        vector,
        top_k,
    )
    return [dict(r) for r in rows if r["score"] is not None and r["score"] >= min_score]


def render_memory_block(similar: list[dict]) -> str:
    if not similar:
        return ""
    out = []
    for r in similar:
        out.append(
            f"- [incident #{r['id']} · {r['severity']} · score {r['score']:.2f}] "
            f"{r['summary']} → root cause: {r['root_cause']}"
        )
    return "\n".join(out)


async def persist_incident(
    signature: str,
    alert: dict,
    rca: RcaResult,
    redacted_text: str,
) -> int:
    """Insert the incident and its embedding; returns the new incident id."""
    rca_json = json.dumps(rca.model_dump(), ensure_ascii=False)
    async with pool().acquire() as conn:
        async with conn.transaction():
            incident_id = await conn.fetchval(
                """
                INSERT INTO incident
                    (signature, alert_type, target_name, severity,
                     summary, root_cause, rca_json)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                RETURNING id
                """,
                signature,
                alert.get("alert_type"),
                alert.get("target_name"),
                alert.get("severity"),
                rca.summary,
                rca.root_cause,
                rca_json,
            )
            vector = await embed(redacted_text)
            await conn.execute(
                "INSERT INTO incident_embedding (incident_id, embedding) VALUES ($1,$2)",
                incident_id,
                vector,
            )
    log.info("incident_persisted", incident_id=incident_id, signature=signature)
    return incident_id
